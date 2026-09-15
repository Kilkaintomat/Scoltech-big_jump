"""Replay the five original main-run disagreements under a frozen verifier."""

import argparse
from pathlib import Path

from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.stages import rows
from onebigjump.e1.verification import verify_one
from onebigjump.lean import LeanREPL, discover

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
parser.add_argument("output", type=Path)
a = parser.parse_args()
source = Path(__file__).resolve().parents[2] / "source-manifest.json"
verify_manifest(source)
config_path = a.root / "main/protocol.json"
config = read_json(config_path)
settings = config["lean"]
problems_path = a.root / "inputs/problems.json"
problems = {p["problem_id"]: p for p in read_json(problems_path)}
manifest = a.root / "main/generation/shard-002-of-008/manifest.json"
verify_manifest(manifest)
ids = {
    "main:aime_1990_p15:T0.6:a06",
    "main:aime_1990_p15:T1.0:a01",
    "main:imo_1964_p2:T1.0:a04",
    "main:mathd_numbertheory_495:T0.6:a05",
    "main:mathd_algebra_107:T1.0:a05",
}
samples = [r for r in rows(manifest.parent / "samples.jsonl") if r["trace_id"] in ids]
if {r["trace_id"] for r in samples} != ids:
    raise ValueError("regression must include every originally observed disagreement")
results = []
with LeanREPL(
    discover(settings["workspace"]),
    imports="import Mathlib\nimport Aesop",
    startup_timeout_s=settings["startup_timeout_s"],
) as repl:
    for sample in samples:
        row = verify_one(repl, sample, problems[sample["problem_id"]], settings)
        results.append(row)
        print(row["trace_id"], row["category"], row["unexplained_disagreement"], flush=True)
    startup = repl.startup_diagnostics
metrics = {
    "cases": len(results),
    "unexplained_disagreements": sum(r["unexplained_disagreement"] for r in results),
    "categories": {r["trace_id"]: r["category"] for r in results},
    "startup_diagnostics": startup,
    "old_generation_unchanged": True,
}
path = write_once(a.output / "results.json", results)
summary = write_once(a.output / "metrics.json", metrics)
finish(
    a.output,
    stage="saved-completion-verifier-regression",
    context={"source": digest(source)},
    inputs=[source, config_path, problems_path, manifest],
    outputs=[path, summary],
    metrics=metrics,
)
if metrics["unexplained_disagreements"] or any(
    r["category"] not in {"verified", "timeout_resource"} for r in results
):
    raise RuntimeError("original disagreement regression failed")
if next(r for r in results if r["problem_id"] == "mathd_algebra_107")["category"] != "verified":
    raise RuntimeError("original parenthesis segmentation regression did not verify")

for row in results:
    for step in row.get("steps", []):
        if "(200000)" in step.get("message", "") and "heartbeat" in step["message"].lower():
            raise RuntimeError("replay still used the old heartbeat budget")
