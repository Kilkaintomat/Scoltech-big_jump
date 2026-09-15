"""Validate the continuation code and its inherited evidence on a Slurm node."""
import ast
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.stages import pilot_gate

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/revision_2026_09_13/saved-continuation-v1"
OLD = BASE / "audit/revision_2026_09_13/speedup-v2"
SOURCE = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"


def test_count(path):
    suites = list(ET.parse(path).getroot().iter("testsuite"))
    assert suites and all(int(s.get(k, "0")) == 0 for s in suites
                          for k in ("failures", "errors", "skipped"))
    return sum(int(s.get("tests", "0")) for s in suites)


def main():
    capture = HERE / "authorization-and-prior-jobs.json"
    data = read_json(capture)
    for job in ("8466207", "8466211", "8466227", "8466226"):
        assert data["jobs"][job] == ["COMPLETED", "0:0"]
    assert data["user_authorized_automatic_continuation"] is True
    assert test_count(OLD / "tests-8466207.xml") == 731
    assert test_count(OLD / "io-tests-8466227.xml") == 734
    current_tests = HERE / ("tests-" + os.environ["SLURM_JOB_ID"] + ".xml")
    focused = test_count(current_tests)
    assert focused >= 12
    verify_manifest(SOURCE)
    accept = OLD / "acceptance/manifest.json"
    verify_manifest(accept)
    assert read_json(accept)["metrics"]["passed"]
    gates = [pilot_gate(BASE / "runs/lean_reverification_20260913_local" / model, SOURCE)
             for model in ("deepseek", "goedel", "kimina")]
    for name in ("policy.py", "controller.py"):
        ast.parse((HERE / name).read_text(), feature_version=(3, 6))
    code = [p for p in HERE.iterdir() if p.suffix in (".py", ".sh", ".sbatch")]
    code += [OLD / "repair.py",
             BASE / "audit/revision_2026_09_13/statistical-fitness-v1/resource_guard.py",
             BASE / "audit/revision_2026_09_13/snapshots/lean-local-toolchain-v7/scripts/campaign/dispatch.py"]
    metrics = dict(passed=True, job_id=os.environ["SLURM_JOB_ID"], source=str(SOURCE.parent),
        source_sha256=digest(SOURCE), focused_tests=focused, full_source_tests=734,
        operational_code={str(p): digest(p) for p in code}, scope="saved population only",
        gpu_release="6672 attempts/model, all planned IDs, immutable digests, zero unexplained disagreements",
        live_gate_manifests=[str(p) for p in gates])
    out = HERE / "preflight"
    metric = write_once(out / "metrics.json", metrics)
    finish(out, stage="saved-continuation-preflight", context=dict(source=digest(SOURCE)),
           inputs=[SOURCE, accept, capture, current_tests, *code, *gates,
                   OLD / "tests-8466207.xml", OLD / "io-tests-8466227.xml"],
           outputs=[metric], metrics=metrics)
    print("PREFLIGHT_PASSED", metrics, flush=True)


if __name__ == "__main__":
    main()
