"""Derive deterministic ID splits and a machine-readable version of the E1 protocol."""

import sys
from collections import Counter, defaultdict
from pathlib import Path

from onebigjump.e1.artifacts import digest, identity, read_json, write_once
from onebigjump.e1.spans import lexical_tokens

root = Path(sys.argv[1])
rows = read_json(root / "inputs/benchmark-inventory.json")
seed = 20260908
if len({x["problem_id"] for x in rows}) != len(rows):
    raise ValueError("duplicate source IDs")
validation = sorted(
    [x["problem_id"] for x in rows if x["split"] == "validation"],
    key=lambda x: __import__("hashlib").sha256(f"{seed}:development:{x}".encode()).hexdigest(),
)
development = validation[:40]
calibration = validation[40:]
evaluation = sorted(x["problem_id"] for x in rows if x["split"] == "test")
lookup = {x["problem_id"]: x for x in rows}
duplicates = defaultdict(list)
for x in rows:
    if x["eligible"]:
        tokens = lexical_tokens(x["statement"])
        duplicates[identity(tokens[2:])].append(x["problem_id"])
cross = []
for ids in duplicates.values():
    splits = {
        ("development" if p in development else "calibration")
        if lookup[p]["split"] == "validation"
        else "evaluation"
        for p in ids
    }
    if len(splits) > 1:
        cross.append(ids)
        for pid in ids:
            lookup[pid]["eligible"] = False
            lookup[pid]["exclusion"] = "cross_split_lexical_duplicate"
pilot = [p for p in development if lookup[p]["eligible"]][:20]
assert len(pilot) == 20
for x in rows:
    pid = x["problem_id"]
    x["role"] = (
        "development"
        if pid in development
        else "calibration"
        if pid in calibration
        else "evaluation"
    )
    x["task_family"] = (
        "_".join(pid.split("_")[:2]) if pid.startswith("mathd_") else pid.split("_")[0]
    )
write_once(root / "inputs/problems.json", rows)
splits = {
    "development": development,
    "calibration": calibration,
    "evaluation": evaluation,
    "pilot_calibration": pilot[:10],
    "pilot_evaluation": pilot[10:],
    "cross_split_duplicates": cross,
    "same_split_duplicate_groups": [
        v for v in duplicates.values() if len(v) > 1 and v not in cross
    ],
}
write_once(root / "inputs/splits.json", splits)
config = {
    "version": "pilot-v0",
    "run_id": root.name,
    "seed": seed,
    "model_id": "deepseek-ai/DeepSeek-Prover-V2-7B",
    "revision": "a8d9e14432b2e8dd9df2a4d4e70f1ba9bc8d9b7b",
    "tokenizer_revision": "a8d9e14432b2e8dd9df2a4d4e70f1ba9bc8d9b7b",
    "model_path": "/gpfs/gpfs0/denis.rakhmankin/hf_cache/hub/models--deepseek-ai--DeepSeek-Prover-V2-7B/snapshots/a8d9e14432b2e8dd9df2a4d4e70f1ba9bc8d9b7b",
    "temperatures": [0.6, 1.0],
    "pilot_attempts": 2,
    "main_attempts": 8,
    "max_new_tokens": 8192,
    "backend": "vllm",
    "top_p": 1.0,
    "top_k": -1,
    "layers": [6, 14, 21],
    "primary_layer": 14,
    "primary_temperature": 0.6,
    "primary_statistic": "whitened",
    "whitening": {
        "shrinkage": 0.1,
        "target": "isotropic",
        "min_main_tasks": 20,
        "min_main_increments": 200,
        "min_pilot_tasks": 2,
        "min_pilot_increments": 8,
        "ridge": 1.0,
    },
    "lean": {
        "workspace": "/beegfs/home/denis.rakhmankin/onebigjump/lean_workspace",
        "step_timeout_s": 60,
        "whole_timeout_s": 180,
        "startup_timeout_s": 900,
        "max_heartbeats": 400000,
    },
    "statistics": {
        "bootstrap": 500,
        "inner_bootstrap": 200,
        "permutations": 999,
        "min_tasks": 20,
        "min_steps": 200,
        "min_k": 20,
        "min_tail_tasks": 20,
        "valid_fraction": 0.9,
        "q": 0.01,
    },
    "inputs": {
        name: digest(root / "inputs" / name)
        for name in ("problems.json", "splits.json", "input-versions.json")
    },
    "protocol_sha256": digest("docs/e1/PROTOCOL.md"),
}
write_once(root / "pilot/protocol.json", config)
print("SPLITS", {k: len(v) for k, v in splits.items()})
print("ELIGIBLE", Counter((x["role"], x["eligible"]) for x in rows))
print("DUPLICATES", cross)
print("PILOT", pilot)
