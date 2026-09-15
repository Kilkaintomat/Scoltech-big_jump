"""Checked stage inputs and task-level accounting for the first real prover pilot."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .artifacts import Journal, digest, finish, identity, read_json, verify_manifest
from .generation import planned_requests


def configuration(root: Path, phase: str) -> dict[str, Any]:
    config = read_json(root / phase / "protocol.json")
    for name, expected in config["inputs"].items():
        if digest(root / "inputs" / name) != expected:
            raise ValueError(f"frozen protocol input changed: {name}")
    return dict(config)


def completed(directory: Path) -> bool:
    manifest = directory / "manifest.json"
    if not manifest.exists():
        return False
    verify_manifest(manifest)
    return True


def rows(path: Path) -> list[dict[str, Any]]:
    context = identity(read_json(path.with_suffix(".identity.json")))
    found: set[str] = set()
    result = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                raise ValueError(f"incomplete upstream journal: {path}")
            row = json.loads(line)
            expected = row.pop("row_sha256")
            if identity(row) != expected or row["context_sha256"] != context:
                raise ValueError(f"corrupt upstream journal: {path}")
            if row["trace_id"] in found:
                raise ValueError(f"duplicate trace ID: {row['trace_id']}")
            found.add(row["trace_id"])
            result.append(row)
    return result


def generation_inputs(root: Path, phase: str) -> tuple[list[dict[str, Any]], list[Path]]:
    config = configuration(root, phase)
    manifests = sorted((root / phase / "generation").glob("shard-*/manifest.json"))
    if not manifests:
        raise ValueError("no completed generation shards")
    samples = []
    for manifest in manifests:
        verify_manifest(manifest)
        samples.extend(rows(manifest.parent / "samples.jsonl"))
    expected = {r["trace_id"] for r in planned_requests(root, phase, config)}
    ids = [r["trace_id"] for r in samples]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("generation shards have duplicate, missing or unexpected attempts")
    return samples, manifests


def check_model(root: Path, config: dict[str, Any]) -> None:
    for name, expected in read_json(root / "checks/model-digests.json").items():
        if digest(Path(config["model_path"]) / name) != expected:
            raise ValueError(f"model/tokenizer digest changed: {name}")
    container = read_json(root / "checks/container-digest.json")
    if digest(container["path"]) != container["sha256"]:
        raise ValueError("execution container digest changed")


def verify(root: Path, phase: str, source: Path, shard: int = 0, n_shards: int = 1) -> None:
    from ..lean.environment import discover
    from ..lean.verifier import LeanREPL
    from .verification import verify_one

    config = configuration(root, phase)
    directory = root / phase / "verification"
    if n_shards != 1:
        directory = directory / f"shard-{shard:03d}-of-{n_shards:03d}"
    if completed(directory):
        if read_json(directory / "manifest.json")["metrics"]["unexplained_disagreements"]:
            raise RuntimeError("recorded verification disagreements block this run")
        return
    gate = pilot_gate(root, source)
    samples, manifests = generation_inputs(root, phase)
    selected = {r["trace_id"] for r in planned_requests(root, phase, config, shard, n_shards)}
    samples = [r for r in samples if r["trace_id"] in selected]
    problems = {p["problem_id"]: p for p in read_json(root / "inputs/problems.json")}
    settings = config["lean"]
    context = {
        "source": digest(source),
        "config": digest(root / phase / "protocol.json"),
        "generation": {str(p): digest(p) for p in manifests},
    }
    with Journal(directory / "labels.jsonl", context) as journal:
        with LeanREPL(
            discover(settings["workspace"]),
            imports="import Mathlib\nimport Aesop",
            startup_timeout_s=settings["startup_timeout_s"],
        ) as repl:
            for sample in samples:
                if journal.existing(sample["trace_id"], identity(sample)) is not None:
                    continue
                result = verify_one(repl, sample, problems[sample["problem_id"]], settings)
                result["role"] = sample["role"]
                result["task_family"] = sample["task_family"]
                journal.append(result, identity(sample))
                print(
                    "verified",
                    len(journal.rows),
                    "/",
                    len(samples),
                    result["trace_id"],
                    result["category"],
                    flush=True,
                )
        values = list(journal.rows.values())
    metrics = {
        "attempts": len(values),
        "categories": dict(Counter(v["category"] for v in values)),
        "unexplained_disagreements": sum(v["unexplained_disagreement"] for v in values),
    }
    finish(
        directory,
        stage="verification",
        context=context,
        inputs=[source, gate, root / phase / "protocol.json", *manifests],
        outputs=[directory / "labels.jsonl", directory / "labels.identity.json"],
        metrics=metrics,
    )
    if metrics["unexplained_disagreements"]:
        raise RuntimeError("whole-proof/replay disagreements block downstream analysis")


def pilot_gate(root: Path, source: Path) -> Path:
    """Use a passed live-kernel check for exactly this verifier code and pilot population."""
    config = configuration(root, "pilot")
    requested = {r["problem_id"] for r in planned_requests(root, "pilot", config)}
    current = read_json(source)["outputs"]
    required = (
        "lean/verifier.py",
        "lean/environment.py",
        "lean/segmentation.py",
        "lean/lexical.py",
        "e1/verification.py",
        "e1/spans.py",
        "e1/smoke.py",
    )
    for manifest in sorted((root / "checks").glob("lean-smoke-*/manifest.json"), reverse=True):
        verify_manifest(manifest)
        meta = read_json(manifest)
        if meta["context"]["config_sha256"] != digest(root / "pilot/protocol.json"):
            continue
        previous_source = next(
            Path(p) for p in meta["inputs"] if p.endswith("source-manifest.json")
        )
        previous = read_json(previous_source)["outputs"]
        compatible = all(
            [v for p, v in previous.items() if p.endswith("/onebigjump/" + suffix)]
            == [v for p, v in current.items() if p.endswith("/onebigjump/" + suffix)]
            for suffix in required
        )
        if not compatible:
            continue
        if not (manifest.parent / "lean-environment.json").is_file():
            continue
        summary = read_json(manifest.parent / "summary.json")
        checked = read_json(manifest.parent / "statement-checks.json")
        eligible = {
            r["problem_id"] for r in checked if r["elaborates"] and not r["already_imported"]
        }
        if (
            summary["passed"]
            and not summary["imported_answers"]
            and requested <= eligible
            and read_json(manifest.parent / "lean-environment.json")
            == lean_fingerprint(config["lean"])
        ):
            return manifest
    raise ValueError("no passed live Lean gate for the current verifier and every pilot problem")


def lean_fingerprint(settings: dict[str, Any]) -> dict[str, Any]:
    """Pin the installed kernel/REPL independently of the Python source snapshot."""
    import subprocess

    from ..lean.environment import discover

    env = discover(settings["workspace"]).require()
    workspace = Path(settings["workspace"])
    expected_toolchain = "leanprover/lean4:v4.34.0-rc2"
    expected_mathlib = "85e3a25e006c35636f0e53b0e9296caca2685bc0"
    expected_repl = "5d5c49d13dfc0c1d2df43a27c3e56e02ad81b9c3"

    def git(path: Path, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()

    repl = workspace / "repl"
    mathlib = workspace / "mathlib_project/.lake/packages/mathlib"
    if env.toolchain != expected_toolchain or env.mathlib_rev != expected_mathlib:
        raise ValueError("installed Lean/Mathlib revision differs from the pilot pin")
    if git(repl, "rev-parse", "HEAD") != expected_repl:
        raise ValueError("installed REPL revision differs from the pilot pin")
    for path in (repl, mathlib):
        if git(path, "status", "--porcelain", "--untracked-files=no"):
            raise ValueError(f"modified installed Lean dependency: {path}")
    assert env.repl_binary is not None
    return {
        "toolchain": env.toolchain,
        "mathlib_revision": env.mathlib_rev,
        "repl_revision": expected_repl,
        "repl_binary_sha256": digest(env.repl_binary),
        "project_manifest_sha256": digest(workspace / "mathlib_project/lake-manifest.json"),
        "mathlib_manifest_sha256": digest(mathlib / "lake-manifest.json"),
    }
