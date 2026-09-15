"""Run one bounded saved-label repair, then produce a release receipt on a Slurm node."""
from pathlib import Path
import importlib.util
import os
from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/revision_2026_09_13/saved-continuation-v1"
OLD = BASE / "audit/revision_2026_09_13/speedup-v2"
ROOT = BASE / "runs/lean_reverification_20260913_local"
SOURCE = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
spec = importlib.util.spec_from_file_location("accepted_repair_runner", OLD / "repair.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main():
    verify_manifest(HERE / "preflight/manifest.json")
    preflight = read_json(HERE / "preflight/metrics.json")
    assert preflight["passed"] and preflight["source_sha256"] == digest(SOURCE)
    for path, expected in preflight["operational_code"].items():
        assert digest(path) == expected
    runner.main()
    accepted = {}
    inputs = [SOURCE, Path(__file__), OLD / "repair.py", HERE / "preflight/manifest.json"]
    shard_metrics = {}
    for model in ("deepseek", "goedel", "kimina"):
        paths = sorted((OLD / "repaired" / model).glob("shard-*/manifest.json"))
        shard_metrics[model] = [read_json(p)["metrics"] for p in paths]
        inputs.extend(paths)
        manifest = ROOT / model / "main/verification/manifest.json"
        if not manifest.exists():
            continue
        verify_manifest(manifest)
        meta = read_json(manifest)
        assert meta["stage"] == "gather-verification-repaired"
        assert meta["metrics"]["attempts"] == 6672
        assert meta["metrics"]["unexplained_disagreements"] == 0
        assert meta["metrics"]["all_planned_attempts_accounted"]
        assert len(paths) == 8
        accepted[model] = dict(manifest=str(manifest), manifest_sha256=digest(manifest),
                               stage=meta["stage"], metrics=meta["metrics"])
        inputs.append(manifest)
    metrics = dict(passed=True, accepted_models=accepted, repaired_shards=shard_metrics)
    out = HERE / ("pass-" + os.environ["SLURM_JOB_ID"])
    metric = write_once(out / "metrics.json", metrics)
    finish(out, stage="saved-continuation-pass", context=dict(source=digest(SOURCE)),
           inputs=inputs, outputs=[metric], metrics=metrics)
    print("PASS_ACCEPTED", metrics, flush=True)


if __name__ == "__main__":
    main()
