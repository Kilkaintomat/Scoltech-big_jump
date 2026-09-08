"""The two stages that need a model: sampling proofs, and reading their residual streams.

Both write a manifest, so a table of deviations can be traced back to the weights, the prompts
and the temperature that produced it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..lean.problems import Problem, load_problems
from ..logging import get_logger
from ..manifests import run_manifest
from ..reproducibility import write_json

__all__ = ["run_extraction", "run_generation"]

log = get_logger(__name__)


def run_generation(
    problems_source: str | Path,
    model_id: str,
    out_dir: Path | str,
    *,
    backend: str = "auto",
    samples_per_problem: int = 4,
    temperatures: tuple[float, ...] = (0.6, 1.0),
    max_new_tokens: int = 512,
    limit: int | None = None,
    split: str | None = None,
    device: str = "auto",
    dtype: str = "auto",
    trust_remote_code: bool = False,
    batch_size: int = 1,
    name: str = "generate",
    keep_completion: bool = False,
) -> dict[str, Any]:
    """Sample whole proofs and write the JSONL that `lean-verify` reads."""
    from ..models.generation import generate, make_backend, write_samples

    out = Path(out_dir)
    problems: list[Problem] = load_problems(problems_source, split=split, limit=limit)
    if not problems:
        raise ValueError(f"no problems loaded from {problems_source!r}")

    config = {
        "problems_source": str(problems_source),
        "model_id": model_id,
        "backend": backend,
        "samples_per_problem": samples_per_problem,
        "temperatures": list(temperatures),
        "max_new_tokens": max_new_tokens,
        "n_problems": len(problems),
        "split": split,
        "dtype": dtype,
    }
    with run_manifest(name, "generate", out, config=config) as man:
        # Every backend option is passed; `make_backend` keeps what its chosen backend accepts.
        engine = make_backend(
            model_id,
            backend,
            trust_remote_code=trust_remote_code,
            device=device,
            dtype=dtype,
            batch_size=batch_size,
        )

        samples = generate(
            problems,
            engine,
            samples_per_problem=samples_per_problem,
            temperatures=temperatures,
            max_new_tokens=max_new_tokens,
            keep_completion=keep_completion,
        )
        path, count = write_samples(samples, out / "samples.jsonl", keep_completion=keep_completion)
        man.add_output(path, "samples")
        man.add_output(
            write_json(out / "problems.json", [p.as_dict() for p in problems]), "problems"
        )
        man.add_metric("n_problems", len(problems))
        man.add_metric("n_samples", count)
        man.add_metric("backend", type(engine).__name__)
        expected = len(problems) * samples_per_problem * len(temperatures)
        if count != expected:  # pragma: no cover - a backend that returned the wrong shape
            man.note(f"expected {expected} samples, wrote {count}")
        log.info("wrote %d samples to %s", count, path)
        return {"n_problems": len(problems), "n_samples": count, "path": str(path)}


def run_extraction(
    traces_path: Path | str,
    model_id: str,
    out_dir: Path | str,
    *,
    layer_fractions: tuple[float, ...] = (0.25, 0.5, 0.75),
    statistics: tuple[str, ...] = ("raw", "whitened", "innovation"),
    calibration_frac: float = 0.5,
    device: str = "auto",
    dtype: str = "bfloat16",
    trust_remote_code: bool = False,
    max_tokens: int | None = 4096,
    seed: int = 0,
    name: str = "activations",
    analyse: bool = True,
) -> dict[str, Any]:
    """Read residual streams for labelled traces, build the table, and optionally analyse it."""
    from ..models.extraction import (
        extract_table,
        load_extraction_model,
        read_traces,
        stratified_calibration_split,
    )

    out = Path(out_dir)
    traces = read_traces(traces_path)
    if not traces:
        raise ValueError(f"no traces in {traces_path!r}")

    config = {
        "traces": str(traces_path),
        "model_id": model_id,
        "layer_fractions": list(layer_fractions),
        "statistics": list(statistics),
        "calibration_frac": calibration_frac,
        "dtype": dtype,
        "max_tokens": max_tokens,
        "seed": seed,
    }
    with run_manifest(name, "activations", out, config=config, seed=seed) as man:
        model, tokenizer, resolved = load_extraction_model(
            model_id, device=device, dtype=dtype, trust_remote_code=trust_remote_code
        )
        man.add_metric("device", resolved)

        calibration = stratified_calibration_split(traces, frac=calibration_frac, seed=seed)
        result = extract_table(
            traces,
            model,
            tokenizer,
            calibration_problems=calibration,
            layer_fractions=layer_fractions,
            statistics=statistics,
            max_tokens=max_tokens,
            model_name=model_id,
        )

        table_path = out / "deviations.parquet"
        result.table.to_parquet(table_path, index=False)
        man.add_output(table_path, "table")
        man.add_output(write_json(out / "extraction_summary.json", result.summary()), "summary")

        calib_dir = out / "calibration"
        for layer, calibration_obj in result.calibrations.items():
            man.add_output(
                calibration_obj.save(calib_dir / f"calibration_layer{layer:03d}.npz"), "calibration"
            )

        for key, value in result.summary().items():
            if key != "calibration":
                man.add_metric(key, value)

        missing = [s for s in statistics if s not in set(result.table["statistic"].unique())]
        if missing:
            man.note(
                "statistics unavailable on this run (the calibration was refused or empty): "
                + ", ".join(missing)
            )
        if result.skipped.get("unalignable"):
            man.note(f"{result.skipped['unalignable']} traces could not be aligned to tokens")

        log.info(
            "table: %d rows, %d traces, statistics %s",
            len(result.table),
            result.table["trace_id"].nunique(),
            sorted(result.table["statistic"].unique()),
        )

        payload: dict[str, Any] = {"extraction": result.summary(), "table": str(table_path)}
        if analyse:
            from .analysis import run_analysis

            payload["analysis"] = run_analysis(
                result.table, out_dir=out / "analysis", name=f"{name}-analysis"
            )
        return payload
