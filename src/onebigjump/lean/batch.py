"""Verify a batch of sampled proofs and write labelled traces.

Input is JSONL, one sampled proof per line; output is JSONL of `ProofTrace` records plus the
category counts Appendix B.2 asks to be reported. The Mathlib import costs about two minutes, so
one REPL serves the whole batch, and its environment is snapshotted so that a restart after a
timeout costs seconds rather than another two minutes.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from ..logging import get_logger
from ..manifests import run_manifest
from ..reproducibility import write_json
from .environment import discover
from .schemas import ProofTrace, StepStatus, VerificationSummary
from .verifier import LeanREPL, verify_trace

__all__ = ["ProofRequest", "read_requests", "verify_batch"]

log = get_logger(__name__)


class ProofRequest(dict[str, Any]):
    """One sampled proof to verify. A thin dict so the input format stays open."""

    @property
    def trace_id(self) -> str:
        return str(self.get("trace_id") or self.get("id") or "")

    @property
    def problem_id(self) -> str:
        return str(self.get("problem_id") or self.get("problem") or "")

    @property
    def proof(self) -> str:
        return str(self.get("proof") or self.get("proof_text") or self.get("text") or "")

    @property
    def directives(self) -> str:
        """`open` and `set_option` lines the statement needs but the proof text does not carry."""
        return str(self.get("directives") or "")

    @property
    def source(self) -> str:
        """What to hand the kernel: the directives, then the proof.

        Prepending rather than passing them separately keeps the header, the line spans the
        segmenter records and the token alignment all consistent with one text.
        """
        directives = self.directives.strip()
        proof = self.proof
        return f"{directives}\n{proof}" if directives and proof else proof


def read_requests(path: Path | str) -> Iterator[ProofRequest]:
    """Read a JSONL file of sampled proofs, skipping blank lines."""
    with Path(path).open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if not line.strip():
                continue
            obj = json.loads(line)
            obj.setdefault("trace_id", f"trace-{i:06d}")
            yield ProofRequest(obj)


def verify_batch(
    requests: Iterable[ProofRequest] | Iterable[dict[str, Any]],
    out_dir: Path | str,
    *,
    workspace: Path | str = "lean_workspace",
    per_step_timeout_s: float = 60.0,
    whole_proof_timeout_s: float = 180.0,
    max_traces: int | None = None,
    name: str = "lean-verify",
    shard: int = 0,
    n_shards: int = 1,
    resume: bool = True,
) -> tuple[list[ProofTrace], VerificationSummary]:
    """Label every proof in `requests`, writing traces, a summary and a manifest into `out_dir`.

    Two concessions to the length of a real run. The Lean kernel is single-threaded per REPL and
    this is usually the slowest stage of the pipeline, so `shard`/`n_shards` splits the input
    deterministically by trace id and several processes can work on disjoint parts. And `resume`
    skips traces already present in the output, so an interrupted run of several hours continues
    rather than starting again -- with a full Mathlib import costing two minutes on each restart,
    losing the work is not a small thing.
    """
    out = Path(out_dir)
    env = discover(workspace)
    items = [ProofRequest(r) for r in requests]
    if n_shards > 1:
        items = [
            r
            for r in items
            if hashlib.sha1(r.trace_id.encode()).digest()[0] % n_shards == shard % n_shards
        ]
    if max_traces is not None:
        items = items[:max_traces]

    trace_path = out / ("traces.jsonl" if n_shards == 1 else f"traces.shard{shard:02d}.jsonl")
    done: set[str] = set()
    if resume and trace_path.is_file():
        with trace_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    done.add(str(json.loads(line).get("trace_id", "")))
        items = [r for r in items if r.trace_id not in done]
        log.info("resuming: %d already verified, %d to go", len(done), len(items))

    with run_manifest(
        name,
        "lean",
        out,
        config={
            "workspace": str(workspace),
            "per_step_timeout_s": per_step_timeout_s,
            "whole_proof_timeout_s": whole_proof_timeout_s,
            "n_requested": len(items),
        },
    ) as man:
        man.add_metric("lean_environment", env.as_dict())
        man.add_metric("shard", {"index": shard, "of": n_shards})
        man.add_metric("resumed_from", len(done))
        env.require()

        traces: list[ProofTrace] = []
        t0 = time.time()
        with LeanREPL(env) as repl:
            with trace_path.open("a" if done else "w", encoding="utf-8") as fh:
                for i, req in enumerate(items):
                    tr = verify_trace(
                        repl,
                        req.source,
                        trace_id=req.trace_id,
                        problem_id=req.problem_id,
                        model_id=str(req.get("model_id", "")),
                        temperature=req.get("temperature"),
                        sample_index=int(req.get("sample_index", 0)),
                        per_step_timeout_s=per_step_timeout_s,
                        whole_proof_timeout_s=whole_proof_timeout_s,
                    )
                    if not tr.check_absorbing():  # pragma: no cover - guarded by construction
                        raise AssertionError(f"non-absorbing labels on trace {tr.trace_id}")
                    traces.append(tr)
                    fh.write(tr.model_dump_json() + "\n")
                    fh.flush()  # so an interrupted run can resume from what it finished
                    if (i + 1) % 25 == 0:
                        log.info(
                            "verified %d/%d traces (%.1fs, %d REPL restarts)",
                            i + 1,
                            len(items),
                            time.time() - t0,
                            repl.restarts,
                        )
            man.add_metric("repl_restarts", repl.restarts)
            man.add_metric("repl_recoveries", repl.recoveries)

        if done:
            # The summary must describe the whole file, not only this session's additions.
            traces = read_traces(trace_path)
        summary = VerificationSummary.from_traces(traces)
        man.add_output(trace_path, "traces")
        man.add_output(write_json(out / "summary.json", summary.model_dump()), "summary")
        for key, value in summary.model_dump().items():
            man.add_metric(key, value)

        # Disagreement between whole-proof compilation and step replay should be empty by
        # construction; if it is not, the labels are not trustworthy and the run says so.
        # A trace closed by `sorry` compiles (with a warning) but is not a proof, so it is the
        # one expected disagreement and is excluded rather than reported as a labelling fault.
        disagree = [
            t.trace_id
            for t in traces
            if t.labelled
            and t.whole_proof_ok is not None
            and t.whole_proof_ok != t.verified
            and not (t.t_star is not None and t.steps[t.t_star].status == StepStatus.SORRY)
        ]
        man.add_metric("whole_proof_vs_replay_disagreements", len(disagree))
        if disagree:
            man.note(
                f"{len(disagree)} traces where whole-proof compilation and step replay disagree "
                f"on chain validity: {disagree[:20]}"
            )
            log.warning("%d traces disagree between whole-proof and step replay", len(disagree))

        log.info(
            "verified %d traces: %d verified, %d refuted, %d discarded (parse error), "
            "%d timeout, %d REPL failure",
            summary.n_traces,
            summary.verified,
            summary.refuted,
            summary.parse_error_discarded,
            summary.timeout,
            summary.repl_failure,
        )
        return traces, summary


def read_traces(path: Path | str) -> list[ProofTrace]:
    """Read back a traces JSONL, for resuming or for the extraction stage."""
    out: list[ProofTrace] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(ProofTrace.model_validate(json.loads(line)))
    return out
