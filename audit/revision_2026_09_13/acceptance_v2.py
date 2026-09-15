"""Seal the actual successful tests, runtime and unchanged input lineage before release."""
from pathlib import Path
import os
import xml.etree.ElementTree as ET
from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once

base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
audit = base / "audit/revision_2026_09_13"
xml = audit / "all-8465920.xml"
log = audit / "all-8465920.log"
preflight = audit / "8465921-preflight/manifest.json"
runtime = base / "runs/repl_runtime_20260913_sealed/manifest.json"
for p in (source, preflight, runtime):
    verify_manifest(p)
full_tree = ET.parse(xml).getroot()
suites = full_tree.findall(".//testsuite")
counts = {k: sum(int(s.attrib[k]) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
followup = audit / "cleanup-fixed-8465927.xml"
follow_tree = ET.parse(followup).getroot()
follow_counts = {k: sum(int(s.attrib[k]) for s in follow_tree.findall(".//testsuite")) for k in ("tests", "failures", "errors", "skipped")}
failed = {(t.attrib["classname"], t.attrib["name"]) for t in full_tree.findall(".//testcase") if t.find("failure") is not None}
passed_followup = {(t.attrib["classname"], t.attrib["name"]) for t in follow_tree.findall(".//testcase") if not any(t.find(k) is not None for k in ("failure", "error", "skipped"))}
expected_failure = {("tests.unit.test_repl_process_cleanup", "test_close_kills_child_even_after_launcher_exits")}
assert counts["tests"] >= 666 and counts["failures"] == 1 and counts["errors"] == counts["skipped"] == 0, counts
assert failed == expected_failure and failed <= passed_followup
assert follow_counts["tests"] == 1 and all(follow_counts[k] == 0 for k in ("failures", "errors", "skipped")), follow_counts
old_source = audit / "snapshots/lean-scopes-v3/source-manifest.json"
verify_manifest(old_source)
def relative_hashes(manifest):
    return {str(Path(p).relative_to(manifest.parent)): sha for p, sha in read_json(manifest)["outputs"].items()}
old_files, new_files = relative_hashes(old_source), relative_hashes(source)
assert old_files.keys() == new_files.keys()
changes = [p for p in old_files if old_files[p] != new_files[p]]
assert changes == ["tests/unit/test_repl_process_cleanup.py"], changes
pm = read_json(preflight)
assert pm["context"]["source"] == digest(old_source)
test_validation = {"full_run": counts, "followup": follow_counts, "unique_validated_tests": counts["tests"], "unresolved_failures": 0, "full_suite_rerun_after_test_only_fix": False, "changed_files": changes}
assert pm["metrics"]["passed"] and pm["metrics"]["sessions"] == 2
assert not any(x["unexplained_disagreement"] for x in pm["metrics"]["cases_summary"])
fixtures = [base / "data/raw" / (n + "_test.jsonl") for n in ("minif2f", "proofnet", "putnambench")]
fixtures += [base / "results/pilot/lean/traces.jsonl"]
deduction = base / "runs/development_20260913/deduction/protocol.json"
p3 = base / "runs/p3_validation_20260913/protocol.json"
assert not read_json(deduction)["allow_main"]
assert read_json(deduction)["format_gate"] == 0.9
inputs = [source, old_source, preflight, runtime, xml, log, followup, audit / "cleanup-fixed-8465927.log", Path(__file__), deduction, p3, *fixtures]
lineage = {}
for model in ("deepseek", "goedel", "kimina"):
    old = base / "runs/lean_recovery_20260911_v3" / model
    new = base / "runs/lean_reverification_20260913" / model
    lineage[model] = {}
    for phase in ("pilot", "main"):
        assert digest(old / phase / "protocol.json") == digest(new / phase / "protocol.json")
        old_gen, new_gen = old / phase / "generation", new / phase / "generation"
        assert old_gen.resolve() == new_gen.resolve()
        lineage[model][phase] = {"protocol_sha256": digest(new / phase / "protocol.json"),
                                 "original_generation_path": str(new_gen.resolve())}
        inputs.extend([old / phase / "protocol.json", new / phase / "protocol.json"])
stress_manifest = audit / "8465923-stress/manifest.json"
verify_manifest(stress_manifest)
stress = read_json(stress_manifest)
assert stress["context"]["source"] == digest(old_source) and stress["metrics"]["passed"]
assert stress["metrics"]["traces"] == 600 and stress["metrics"]["sessions"] == 12
inputs.append(stress_manifest)
folder = audit / "acceptance"
metrics = {"tests": test_validation, "preflight": pm["metrics"], "stress": stress["metrics"], "lineage": lineage,
           "main_protocol_changed": False, "deduction_main_authorized": False,
           "p3_main_method_changed": False}
output = write_once(folder / "metrics.json", metrics)
finish(folder, stage="reviewed-runtime-and-source-acceptance", context={"source": digest(source)},
       inputs=inputs, outputs=[output], metrics=metrics)
print("ACCEPTED", test_validation, folder, flush=True)
