"""Collection gates and complete shard accounting for the three-model Lean campaign."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .artifacts import Journal, digest, finish, identity, read_json, verify_manifest, write_once
from .generation import planned_requests
from .stages import completed, configuration, generation_inputs, rows


def gather(root: Path, phase: str, source: Path, stage: str, n_shards: int) -> None:
    if stage not in {"verification", "extraction"} or n_shards < 2:
        raise ValueError("gather requires verification/extraction and multiple shards")
    directory = root / phase / stage
    if completed(directory):
        if stage == "verification" and read_json(directory / "manifest.json")["metrics"].get(
            "unexplained_disagreements"
        ):
            raise ValueError("recorded verifier disagreements block gathered stage reuse")
        return
    filename = "labels.jsonl" if stage == "verification" else "trajectories.jsonl"
    manifests, records = [], []
    for shard in range(n_shards):
        part = directory / f"shard-{shard:03d}-of-{n_shards:03d}"
        if not completed(part):
            raise ValueError(f"incomplete shard: {part}")
        manifests.append(part / "manifest.json")
        records.extend(rows(part / filename))
    samples, _ = generation_inputs(root, phase)
    ids = [r["trace_id"] for r in records]
    if len(ids) != len(set(ids)) or set(ids) != {s["trace_id"] for s in samples}:
        raise ValueError("duplicate, missing or unexpected shard attempts")
    context = {"source": digest(source), "shards": {str(p): digest(p) for p in manifests}}
    with Journal(directory / filename, context) as journal:
        for original in sorted(records, key=lambda r: r["trace_id"]):
            request = identity(original)
            if journal.existing(original["trace_id"], request) is not None:
                continue
            row = {
                k: v for k, v in original.items() if k not in {"request_sha256", "context_sha256"}
            }
            journal.append(row, request)
    metrics: dict[str, Any] = {"attempts": len(records), "n_shards": n_shards}
    if stage == "verification":
        metrics["unexplained_disagreements"] = sum(r["unexplained_disagreement"] for r in records)
        metrics["categories"] = dict(Counter(r["category"] for r in records))
    else:
        metrics["extracted"] = sum(r["extraction_status"] == "extracted" for r in records)
    finish(
        directory,
        stage="gather-" + stage,
        context=context,
        inputs=[source, *manifests],
        outputs=[directory / filename, (directory / filename).with_suffix(".identity.json")],
        metrics=metrics,
    )
    if metrics.get("unexplained_disagreements"):
        raise ValueError("unexplained verifier disagreements")


def collection_gate(root: Path, source: Path) -> None:
    """Release data acquisition on technical evidence, never on a favourable hypothesis result."""
    config = configuration(root, "main")
    directory = root / "main/collection-gate"
    if completed(directory):
        require_collection_gate(root, source)
        return
    pilot = root / "pilot"
    for stage in ("verification", "extraction", "measurement", "analysis"):
        if not completed(pilot / stage):
            raise ValueError("pilot stage incomplete: " + stage)
    samples, generation_manifests = generation_inputs(root, "pilot")
    labels = rows(pilot / "verification/labels.jsonl")
    extracted = rows(pilot / "extraction/trajectories.jsonl")
    sets = [{r["trace_id"] for r in group} for group in (samples, labels, extracted)]
    if not all(s == sets[0] for s in sets):
        raise ValueError("pilot attempt accounting mismatch")
    if any(r["unexplained_disagreement"] for r in labels):
        raise ValueError("pilot verifier disagreement")
    if any(r["category"] in {"infrastructure_error", "infrastructure_failure"} for r in labels):
        raise ValueError("pilot infrastructure failure")
    measured = [r for r in extracted if r["extraction_status"] == "extracted"]
    if not measured or not any(r.get("forward_check") for r in measured):
        raise ValueError("no real model activation validation")
    alignable = [
        r
        for r in labels
        if r.get("steps")
        and r["category"]
        in {
            "verified",
            "localized_tactic_failure",
            "terminal_unsolved_goals",
            "sorry_invalid_proof",
            "timeout_resource",
        }
    ]
    if {r["trace_id"] for r in alignable} != {r["trace_id"] for r in measured}:
        raise ValueError("pilot contains unresolved token alignment exclusions")
    for row in measured:
        if digest(row["states_path"]) != row["states_sha256"]:
            raise ValueError("pilot state file changed")
        if row.get("forward_check") and not all(v["passed"] for v in row["forward_check"].values()):
            raise ValueError("pilot forward check failed")
    lean_checks = Path(config["statement_checks"])
    lean_manifest = lean_checks.parent / "manifest.json"
    verify_manifest(lean_manifest)
    good = {
        r["problem_id"]
        for r in read_json(lean_checks)
        if r["elaborates"] and not r["already_imported"]
    }
    requested = {r["problem_id"] for r in planned_requests(root, "main", config)}
    if not requested <= good:
        raise ValueError("main includes unchecked or incompatible theorem statements")
    # The source used for pilot labels/hooks must match the corresponding campaign components.
    required = ("lean/", "e1/verification.py", "e1/spans.py", "e1/extraction.py", "models/hooks.py")
    current = read_json(source)["outputs"]

    def relevant(outputs: dict[str, str]) -> dict[str, str]:
        return {
            p.split("/src/onebigjump/")[-1]: h
            for p, h in outputs.items()
            if "/src/onebigjump/" in p
            and any(p.split("/src/onebigjump/")[-1].startswith(s) for s in required)
        }

    if (
        not {
            "lean/verifier.py",
            "lean/lexical.py",
            "e1/verification.py",
            "e1/spans.py",
            "e1/extraction.py",
            "models/hooks.py",
        }
        <= relevant(current).keys()
    ):
        raise ValueError("source manifest omits verifier/hook components")
    for stage in ("verification", "extraction"):
        man = read_json(pilot / stage / "manifest.json")
        old = next(Path(p) for p in man["inputs"] if p.endswith("source-manifest.json"))
        if relevant(read_json(old)["outputs"]) != relevant(current):
            raise ValueError("pilot verifier/hook code differs from campaign")
    review = []
    by_category: dict[str, list[dict[str, Any]]] = {}
    sample_lookup = {r["trace_id"]: r for r in samples}
    for row in labels:
        by_category.setdefault(row["category"], []).append(row)
    for group in by_category.values():
        review.extend(group[: max(1, 12 // len(by_category))])
    for row in labels:
        if len(review) >= min(12, len(labels)):
            break
        if row not in review:
            review.append(row)
    review_path = write_once(
        directory / "review-samples.json",
        [{"sample": sample_lookup[r["trace_id"]], "verification": r} for r in review],
    )
    result = {
        "passed": True,
        "purpose": "full-scale data acquisition only",
        "config_sha256": digest(root / "main/protocol.json"),
        "source_sha256": digest(source),
        "pilot_attempts": len(samples),
        "pilot_categories": dict(Counter(r["category"] for r in labels)),
        "pilot_extracted": len(measured),
        "main_attempts": len(planned_requests(root, "main", config)),
        "manual_review": "pending; review packet saved; mandatory before scientific claims/publication",
        "statistical_calibration": "pending; cannot report supported scientific claims",
    }
    receipt = write_once(directory / "result.json", result)
    finish(
        directory,
        stage="main-collection-gate",
        context=result,
        inputs=[
            source,
            root / "main/protocol.json",
            lean_manifest,
            *generation_manifests,
            *[
                pilot / stage / "manifest.json"
                for stage in ("verification", "extraction", "measurement", "analysis")
            ],
        ],
        outputs=[receipt, review_path],
        metrics=result,
    )


def require_collection_gate(root: Path, source: Path) -> Path:
    path = root / "main/collection-gate/manifest.json"
    verify_manifest(path)
    result = read_json(path.parent / "result.json")
    if (
        not result["passed"]
        or result["config_sha256"] != digest(root / "main/protocol.json")
        or result["source_sha256"] != digest(source)
    ):
        raise ValueError("main collection gate does not match source/config")
    return path
