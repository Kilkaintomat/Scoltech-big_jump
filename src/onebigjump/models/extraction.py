"""From labelled traces and a model to the deviations table P1-P5 read.

This is the loop the pipeline was missing. Everything on either side of it already existed and
was tested: `lean-verify` produces labelled traces, `extract_trajectory` reads the residual
stream, `fit_calibration` fits the whitening, `from_traces` builds the table, `run_analysis` runs
the predictions. What was absent was the driver that puts a model on a device and walks the
traces through it.

The one thing it must get right, and the reason it is not a for-loop the caller could write:
**the calibration split is disjoint by problem.** Appendix B.1 fits `(mu, Sigma)` and
`(A_hat, c_hat)` on verified traces of a disjoint problem *split*. Splitting by trace instead
would leave several samples of the same theorem on both sides, and the whitening would be fitted
partly on the distribution it is then applied to -- which would put some of P1's separation into
the fit rather than into the model.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from ..experiments.dataset import from_traces
from ..lean.schemas import ProofTrace
from ..logging import get_logger
from .activations import Calibration, Trajectory, extract_trajectory, fit_calibration
from .hooks import block_modules, layer_indices
from .token_alignment import TokenAlignment, align_steps, step_char_spans

__all__ = ["ExtractionResult", "extract_table", "load_extraction_model", "trace_alignment"]

log = get_logger(__name__)


@dataclass
class ExtractionResult:
    """The table, the calibrations it used, and what had to be dropped along the way."""

    table: pd.DataFrame
    calibrations: dict[int, Calibration]
    n_traces: int
    n_extracted: int
    skipped: dict[str, int] = field(default_factory=dict)
    calibration_problems: list[str] = field(default_factory=list)
    analysis_problems: list[str] = field(default_factory=list)
    layers: list[int] = field(default_factory=list)
    elapsed_s: float = 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "n_traces": self.n_traces,
            "n_extracted": self.n_extracted,
            "skipped": self.skipped,
            "n_calibration_problems": len(self.calibration_problems),
            "n_analysis_problems": len(self.analysis_problems),
            "layers": self.layers,
            "rows": len(self.table),
            "elapsed_s": round(self.elapsed_s, 1),
            "calibration": {str(k): v.summary() for k, v in self.calibrations.items()},
        }


def load_extraction_model(
    model_id: str, *, device: str = "auto", dtype: str = "bfloat16", trust_remote_code: bool = False
) -> tuple[Any, Any, str]:
    """Load the model used for *activations*, which Appendix B.3 keeps separate from sampling.

    bfloat16 weights with float32 accumulation of the norms: the hooks promote the captured states
    before anything is computed from them, because an 8-bit mantissa cannot carry a norm to the
    precision a tail index needs.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if device == "auto":
        device = (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
    torch_dtype = {
        "auto": torch.bfloat16 if device != "cpu" else torch.float32,
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[dtype]

    log.info("loading %s for extraction onto %s in %s", model_id, device, torch_dtype)
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=trust_remote_code)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, dtype=torch_dtype, trust_remote_code=trust_remote_code
    )
    # The transformers stubs reject a device string here; see the same cast in generation.py.
    model = cast(Any, model).to(device)
    model.eval()
    return model, tokenizer, device


def trace_alignment(
    trace: ProofTrace, tokenizer: Any, *, prompt: str | None = None
) -> tuple[str, TokenAlignment] | None:
    """The teacher-forcing text for one trace, and where each step ends in it.

    Returns `None` when the trace cannot be aligned -- no header, or a step whose characters land
    on no token. A trace that cannot be aligned is dropped and counted, never silently given
    partial readouts.
    """
    if not trace.steps or not trace.header:
        return None
    # The body is rebuilt from the original source, not from the segments' `tactic` text: that
    # text has been dedented and re-joined, so its character offsets no longer match the line
    # spans the segmenter recorded, and the readouts would land on the wrong tokens.
    lines = trace.proof_text.split("\n")
    first = min(s.line_start for s in trace.steps)
    last = max(s.line_end for s in trace.steps)
    header_lines = trace.header.count("\n") + 1
    body_lines = lines[header_lines:]
    if not body_lines:
        return None
    body = "\n".join(body_lines)

    steps = [
        {"index": s.index, "line_start": s.line_start, "line_end": s.line_end}
        for s in trace.steps
        if 0 <= s.line_start < len(body_lines) and first <= s.line_end <= max(last, 0)
    ]
    if not steps:
        return None

    head = (prompt or "") + trace.header + "\n"
    text = head + body
    spans = step_char_spans(body, steps, base_offset=len(head))
    if not spans:
        return None
    enc = tokenizer(text, return_offsets_mapping=True, add_special_tokens=True)
    try:
        alignment = align_steps(enc["offset_mapping"], spans, prompt_char_end=len(head))
    except ValueError:
        return None
    return text, alignment


def extract_table(
    traces: Sequence[ProofTrace],
    model: Any,
    tokenizer: Any,
    *,
    calibration_problems: Sequence[str],
    layer_fractions: Sequence[float] = (0.25, 0.5, 0.75),
    statistics: Sequence[str] = ("raw", "whitened", "innovation"),
    shrinkage: float | None = None,
    ridge_alpha: float = 1.0,
    max_tokens: int | None = 4096,
    model_name: str = "",
) -> ExtractionResult:
    """Walk labelled traces through the model and build the deviations table.

    `calibration_problems` names the disjoint split the whitening is fitted on. Its traces are
    extracted and used for the fit, then excluded from the table; the analysis is run on the rest.
    """
    t0 = time.time()
    n_layers = len(block_modules(model))
    layers = layer_indices(n_layers, list(layer_fractions))
    calib_ids = set(calibration_problems)

    skipped = {"unlabelled": 0, "unalignable": 0, "too_long": 0, "failed": 0}
    trajectories: dict[str, dict[int, Trajectory]] = {}
    calibration_pool: dict[int, list[Trajectory]] = {layer: [] for layer in layers}
    analysis: list[ProofTrace] = []

    for i, trace in enumerate(traces):
        if not trace.labelled:
            skipped["unlabelled"] += 1
            continue
        prepared = trace_alignment(trace, tokenizer)
        if prepared is None:
            skipped["unalignable"] += 1
            continue
        text, alignment = prepared
        if max_tokens is not None and alignment.n_tokens > max_tokens:
            skipped["too_long"] += 1
            continue
        try:
            per_layer = extract_trajectory(
                model, tokenizer, text, alignment, trace_id=trace.trace_id, layers=layers
            )
        except (ValueError, RuntimeError) as exc:
            log.warning("extraction failed on %s: %s", trace.trace_id, exc)
            skipped["failed"] += 1
            continue

        if trace.problem_id in calib_ids:
            if trace.verified:
                for layer, traj in per_layer.items():
                    calibration_pool[layer].append(traj)
            continue  # calibration traces never enter the analysed table

        trajectories[trace.trace_id] = per_layer
        analysis.append(trace)
        if (i + 1) % 50 == 0:
            log.info("extracted %d/%d traces (%.0fs)", i + 1, len(traces), time.time() - t0)

    calibrations: dict[int, Calibration] = {}
    for layer, pool in calibration_pool.items():
        if not pool:
            log.warning(
                "no verified calibration traces at layer %d; the whitened and innovation "
                "statistics will be unavailable there",
                layer,
            )
            continue
        try:
            calibrations[layer] = fit_calibration(
                pool,
                shrinkage=shrinkage,
                ridge_alpha=ridge_alpha,
                source=f"{len(pool)} verified traces from {len(calib_ids)} held-out problems",
            )
        except ValueError as exc:
            # An under-determined whitening is refused rather than returned flat; see
            # `fit_calibration`. The raw statistic is still available and the table says so.
            log.warning("calibration at layer %d refused: %s", layer, exc)

    available = ["raw", *(s for s in statistics if s != "raw" and calibrations)]
    table = from_traces(
        analysis,
        trajectories,
        calibrations or None,
        statistics=available,
        model=model_name,
    )

    return ExtractionResult(
        table=table,
        calibrations=calibrations,
        n_traces=len(traces),
        n_extracted=len(analysis),
        skipped=skipped,
        calibration_problems=sorted(calib_ids),
        analysis_problems=sorted({t.problem_id for t in analysis}),
        layers=layers,
        elapsed_s=time.time() - t0,
    )


def read_traces(path: Path | str) -> list[ProofTrace]:
    """Read the JSONL that `onebigjump lean-verify` wrote."""
    import json

    out = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(ProofTrace.model_validate(json.loads(line)))
    return out


def stratified_calibration_split(
    traces: Sequence[ProofTrace], frac: float = 0.5, seed: int = 0
) -> list[str]:
    """Choose the held-out problems, preferring ones that actually have verified traces.

    A calibration split made of problems the model never proved contributes nothing to the fit,
    so problems with at least one verified trace are drawn first.
    """
    verified_problems = sorted({t.problem_id for t in traces if t.verified})
    others = sorted({t.problem_id for t in traces} - set(verified_problems))
    rng = np.random.default_rng(seed)
    target = max(1, round(frac * len({t.problem_id for t in traces})))

    chosen = [verified_problems[int(i)] for i in rng.permutation(len(verified_problems))]
    if len(chosen) < target:
        extra = [others[int(i)] for i in rng.permutation(len(others))]
        chosen += extra[: target - len(chosen)]
    return sorted(chosen[:target])
