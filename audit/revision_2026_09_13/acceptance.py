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
suites = ET.parse(xml).getroot().findall(".//testsuite")
counts = {k: sum(int(s.attrib[k]) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
assert counts["tests"] >= 666 and all(counts[k] == 0 for k in ("failures", "errors", "skipped")), counts
pm = read_json(preflight)
assert pm["context"]["source"] == digest(source)
assert pm["metrics"]["passed"] and pm["metrics"]["sessions"] == 2
assert not any(x["unexplained_disagreement"] for x in pm["metrics"]["cases_summary"])
fixtures = [base / "data/raw" / (n + "_test.jsonl") for n in ("minif2f", "proofnet", "putnambench")]
fixtures += [base / "results/pilot/lean/traces.jsonl"]
deduction = base / "runs/development_20260913/deduction/protocol.json"
p3 = base / "runs/p3_validation_20260913/protocol.json"
assert not read_json(deduction)["allow_main"]
assert read_json(deduction)["format_gate"] == 0.9
inputs = [source, preflight, runtime, xml, log, Path(__file__), deduction, p3, *fixtures]
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
folder = audit / "acceptance"
metrics = {"tests": counts, "preflight": pm["metrics"], "lineage": lineage,
           "main_protocol_changed": False, "deduction_main_authorized": False,
           "p3_main_method_changed": False}
output = write_once(folder / "metrics.json", metrics)
finish(folder, stage="reviewed-runtime-and-source-acceptance", context={"source": digest(source)},
       inputs=inputs, outputs=[output], metrics=metrics)
print("ACCEPTED", counts, folder, flush=True)
