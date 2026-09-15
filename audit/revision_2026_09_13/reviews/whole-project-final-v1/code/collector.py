"""Generate a reviewable status report from immutable experiment artifacts, on Slurm."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import json, os, shutil, hashlib
from onebigjump.e1.artifacts import read_json, verify_manifest, write_once, finish, digest
from onebigjump.e1.stages import generation_inputs, rows

base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
audit = base / "audit/revision_2026_09_13"
out = Path(os.environ["REVIEW_OUTPUT"])
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
started = read_json(out / "inputs/capture.json")["captured_utc"]
inputs = [source, Path(__file__), out / "inputs/capture.json", out / "inputs/squeue.txt", out / "inputs/sacct.txt"]
artifacts = []
verified_seen=set()
def attach(path, recursive=True):
    path = Path(path)
    if not path.exists(): return None
    if recursive and path.name.endswith("manifest.json"): verify_manifest(path,verified_seen)
    relative = path.relative_to(base) if path.is_relative_to(base) else Path("external") / str(path).lstrip("/")
    target = out / "artifacts" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    target.write_bytes(data)
    artifacts.append({"remote": str(path), "relative": str(target.relative_to(out)), "sha256": hashlib.sha256(data).hexdigest()})
    inputs.append(path)
    return read_json(path) if path.suffix == ".json" else None
def completed_stage(folder):
    manifest = folder / "manifest.json"
    if not manifest.exists(): return None
    m = attach(manifest)
    data = attach(folder / "metrics.json")
    return {"manifest": str(manifest), "stage_metrics": m["metrics"], "data": data}
def capture_progress(folder, pattern):
    result = []
    for p in sorted(folder.glob(pattern)):
        raw = p.read_bytes()
        complete_lines = raw.splitlines(keepends=True)
        count = sum(bool(line.strip()) for line in complete_lines if line.endswith(b"\n"))
        result.append({"path": str(p), "complete_records": count, "bytes": len(raw), "sha256_at_read": hashlib.sha256(raw).hexdigest(),
                       "manifest_complete": (p.parent / "manifest.json").exists()})
    return result

print("COLLECT_BASE_EVIDENCE",flush=True)
acceptance = attach(audit / "acceptance/manifest.json")["metrics"]
ded_review = attach(audit / "8465954-deduction-review/manifest.json")["metrics"]
queues = {}
for name in ("lean_reverification_20260913_local", "development_20260913", "controls_20260913_local", "lean_reverification_20260913", "development_20260913_exactlength"):
    p = out / "inputs" / (name + "-queue.json")
    q = read_json(p)
    inputs.append(p)
    queues[name] = {"counts": dict(Counter(t["state"] for t in q["tasks"].values())),
                    "last_poll_utc": q.get("last_poll_utc"), "source": q["source"],
                    "failures": {k: t for k,t in q["tasks"].items() if t["state"] in ("FAILED","BLOCKED")},
                    "active": {k: t for k,t in q["tasks"].items() if t["state"] in ("PENDING","RUNNING")}}
attach(base / "audit/status_2026_09_13/final-v2/REPORT.md", recursive=False)
for queue_name, queue_state in queues.items():
    for task in queue_state["failures"].values():
        for path in (base / "runs" / queue_name / "logs").glob("*-"+str(task.get("job_id"))+".log"):
            attach(path, recursive=False)
main = {}
for model in ("deepseek", "goedel", "kimina"):
    root = base / "runs/lean_reverification_20260913_local" / model
    samples, manifests = generation_inputs(root, "main")
    for p in manifests: attach(p)
    main[model] = {"saved_attempts": len(samples), "unique_ids": len({s["trace_id"] for s in samples}),
                   "complete_planned_ids": True, "distinct_tasks": len({s["problem_id"] for s in samples}),
                   "pilot": {}, "main": {},
                   "verification_progress": capture_progress(root / "main/verification", "shard-*/labels.jsonl")}
    for phase in ("pilot","main"):
        attach(root / phase / "protocol.json")
        for stage in ("verification","extraction","measurement","analysis"):
            main[model][phase][stage] = completed_stage(root / phase / stage)
    for p in (root / "collection-gate/manifest.json", root / "main/collection-gate/manifest.json"):
        if p.exists(): attach(p)
ded_root = base / "runs/development_20260913/deduction"
ded = {s: completed_stage(ded_root / "pilot" / s) for s in ("verification","extraction","measurement","analysis","gate")}
attach(ded_root / "protocol.json")
for name in ("inputs/problems.json","pilot/generation/shard-000-of-001/samples.jsonl","pilot/verification/labels.jsonl","pilot/extraction/trajectories.jsonl"):
    attach(ded_root / name, recursive=False)
ded_generations = rows(ded_root / "pilot/generation/shard-000-of-001/samples.jsonl")
assigned = {r["trace_id"]:r["problem"]["length"] for r in ded_generations}
format_labels = [r for r in rows(ded_root / "pilot/verification/labels.jsonl") if r["category"]=="format_error"]
format_breakdown = {"attempts":len(format_labels), "with_unknown_lines":sum(bool(r["unknown_lines"]) for r in format_labels),
                    "step_count_delta":dict(Counter(str(r["observed_steps"]-assigned[r["trace_id"]]) for r in format_labels))}
ded_review["format_breakdown"] = format_breakdown

p3_root = base / "runs/p3_validation_20260913"
p3 = {"protocol": attach(p3_root / "protocol.json"), "summary": completed_stage(p3_root / "summary"),
      "progress": capture_progress(p3_root, "shard-*/replicates.jsonl")}
for p in sorted(p3_root.glob("shard-*/manifest.json")):
    attach(p)
    attach(p.parent / "replicates.jsonl", recursive=False)
if p3["summary"]:
    from onebigjump.readiness.p3_validation import proportion
    records = [r for file in sorted(p3_root.glob("shard-*/replicates.jsonl")) for r in rows(file)]
    assert len(records) == p3["summary"]["data"]["datasets"]
    paired = {}
    for scenario in p3["protocol"]["scenarios"]:
        sample = [r for r in records if r["request"]["scenario"] == scenario]
        paired[scenario] = {}
        for method in ("percentile","basic"):
            common = [r for r in sample if all(r["methods"][c][method]["ci95"] is not None for c in ("original","observed_support"))]
            def covers(r,c):
                interval = r["methods"][c][method]["ci95"]
                return interval is not None and interval[0] <= r["truth"] <= interval[1]
            old_cov = [covers(r,"original") for r in common]
            new_cov = [covers(r,"observed_support") for r in common]
            dropped = [r for r in sample if r["methods"]["original"][method]["ci95"] is not None and r["methods"]["observed_support"][method]["ci95"] is None]
            paired[scenario][method] = {
                "both_available":len(common), "original_coverage_on_common":proportion(old_cov),
                "candidate_coverage_on_common":proportion(new_cov),
                "candidate_gains":sum(b and not a for a,b in zip(old_cov,new_cov)),
                "candidate_losses":sum(a and not b for a,b in zip(old_cov,new_cov)),
                "original_only":len(dropped),
                "original_coverage_on_dropped":proportion([covers(r,"original") for r in dropped])}
    p3["paired_review"] = paired
for queue_name in queues:
    for receipt in sorted((base / "runs" / queue_name / "controller").glob("*.json")):
        if receipt.name != "identity.json": attach(receipt, recursive=False)
controls_root = base / "runs/controls_20260913_local"
controls = []
for p in sorted((controls_root / "main").rglob("manifest.json")):
    m = attach(p); data = attach(p.parent / "metrics.json")
    controls.append({"path": str(p), "metrics": m["metrics"], "data": data})
for name in ("all-8465920.xml","all-8465920.log","cleanup-fixed-8465927.xml","cleanup-fixed-8465927.log",
             "8465921-preflight/metrics.json","8465921-preflight/results-server-only.json",
             "8465923-stress/metrics.json","8465954-deduction-review/metrics.json",
             "acceptance/metrics.json"):
    attach(audit / name, recursive=False)
for name in ("config.json","manifest.json","Snapshots.lean","Frontend.lean","build_scoped_repl.py"):
    attach(base / "runs/repl_runtime_20260913_sealed" / name)
attach(base / "configs/repl_runtime.json")
attach(out / "inputs/STATUS-before.md", recursive=False)
attach(audit / "snapshots/lean-scopes-v3/source-manifest.json")
attach(audit / "snapshots/lean-scopes-v3/tests/unit/test_repl_process_cleanup.py")
snapshot_copy = out / "source"
snapshot_copy.mkdir(exist_ok=True)
for folder in ("src","scripts","tests","configs","docs"):
    shutil.copytree(source.parent / folder, snapshot_copy / folder,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "._*"), dirs_exist_ok=True)
shutil.copy2(source, snapshot_copy / "source-manifest.json")
for name in ("pyproject.toml","Makefile","AGENTS.md"):
    shutil.copy2(source.parent / name, snapshot_copy / name)

# Read-only incident and repaired runtime evidence, retained beside scientific outputs.
io_incident = attach(audit / "io-audit-8466023/manifest.json")["metrics"]
attach(audit / "io-audit-8466023/metrics.json")
attach(audit / "io-audit-8466023/suspect-labels.json")
for name in ("io_audit_v2.py","io-unit-8466025.xml","io-unit-8466025.log","hashseed-unit-8466030.log","all-8466027.xml","local-validation-8466027.log",
             "all-8466032.xml","local-validation-8466032.log",
             "8466032-preflight/manifest.json","8466032-preflight/metrics.json",
             "8466032-preflight/results-server-only.json"):
    attach(audit / name)
toolchain_config = attach(source.parent / "configs/lean_toolchain_runtime.json")
toolchain_manifest = Path(toolchain_config["manifest"])
attach(toolchain_manifest)
attach(toolchain_manifest.parent / "metrics.json")
attach(toolchain_manifest.parent / "inventory.json")
validation = {"job_id":"8466032","preflight":None,"test_counts":None}
if (audit/"8466032-preflight/metrics.json").exists():
    validation["preflight"] = read_json(audit/"8466032-preflight/metrics.json")
if (audit/"all-8466032.xml").exists():
    import xml.etree.ElementTree as ET
    suites=list(ET.parse(audit/"all-8466032.xml").getroot().iter("testsuite"))
    validation["test_counts"]={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ("tests","failures","errors","skipped")}

# Additive reviews from the current continuation.
compiler_review = completed_stage(audit / "8466072-compiler-review")
pilot_attestation = completed_stage(audit / "8466083-review-attestation")
p3_availability = completed_stage(audit / "8466076-p3-availability")
for directory in (audit / "8466072-compiler-review", audit / "8466083-review-attestation", audit / "8466076-p3-availability"):
    if (directory / "manifest.json").exists():
        for p in sorted(directory.rglob("*")):
            if p.is_file() and p.name not in ("manifest.json","metrics.json"):
                attach(p, recursive=False)
exact_root = base / "runs/development_20260913_exactlength"
deduction_exact_review = completed_stage(audit / "8466088-deduction-review")
deduction_exact = {"protocol": attach(exact_root / "deduction/protocol.json"),
                   "review": deduction_exact_review,
                   "validation": completed_stage(exact_root / "validation"),
                   "stages": {stage: completed_stage(exact_root / "deduction/pilot" / stage)
                              for stage in ("verification","extraction","measurement","analysis","gate")}}
for p in (exact_root / "deduction/inputs/problems.json",
          exact_root / "validation/prompts.json",
          exact_root / "deduction/pilot/generation/shard-000-of-001/samples.jsonl",
          exact_root / "deduction/pilot/verification/labels.jsonl"):
    if p.exists() and (p.parent / "manifest.json").exists(): attach(p, recursive=False)
if deduction_exact["stages"]["verification"]:
    labels = rows(exact_root / "deduction/pilot/verification/labels.jsonl")
    deduction_exact["label_summary"] = {"attempts":len(labels),"categories":dict(Counter(r["category"] for r in labels)),
                                       "format_eligible":sum(r["format_eligible"] for r in labels)}
attach(audit / "snapshots/deduction-numbered-v3/source-manifest.json")
attach(audit / "snapshots/deduction-numbered-v3/src/onebigjump/readiness/deduction.py")
attach(audit / "deduction_exact_preflight.py", recursive=False)
attach(audit / "8466088-deduction-review/examples-server-only.json", recursive=False)
attach(audit / "deduction_exact_review.py", recursive=False)
attach(exact_root / "deduction/pilot/measurement/calibration.json", recursive=False)
attach(audit / "exact-preflight-8466080.xml", recursive=False)

# Future completion reports also audit axiom-policy exclusions on the full main labels.
from onebigjump.e1.verification import ALLOWED_AXIOMS
from onebigjump.e1.spans import mask_comments
import re
def native_policy_inventory(path):
    data = rows(path)
    native_only = []
    for r in data:
        live = mask_comments(r.get("body",""), mask_strings=True)
        live = re.sub(r"«[^»]*»", "", live)
        hole = bool(re.search(r"\b(?:sorry|admit|sorryAx)\b", live))
        unexpected = [name for name in r.get("axioms",[]) if name not in ALLOWED_AXIOMS]
        native = [name for name in unexpected if re.search(r"\._native\.native_decide\.ax(?:_\d+)?$", name)]
        if r.get("whole_proof_ok") is True and r.get("replay_ok") is True and not hole and native and set(native)==set(unexpected):
            native_only.append(r["trace_id"])
    return {"attempts":len(data),"primary_categories":dict(Counter(r["category"] for r in data)),
            "native_policy_only_count":len(native_only),"native_policy_only_ids":native_only,
            "primary_labels_changed":False}
full_native_policy = {}
for model in ("deepseek","goedel","kimina"):
    model_root = base / "runs/lean_reverification_20260913_local" / model
    pilot_check = native_policy_inventory(model_root / "pilot/verification/labels.jsonl")
    if compiler_review:
        assert pilot_check["native_policy_only_count"] == compiler_review["data"]["pilot_inventory"][model]["native_policy_only"]
    final_labels = model_root / "main/verification/labels.jsonl"
    if (final_labels.parent / "manifest.json").exists():
        attach(final_labels.parent / "manifest.json")
        full_native_policy[model] = native_policy_inventory(final_labels)
    else:
        full_native_policy[model] = {"available":False,"reason":"main verification manifest not complete"}

