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



# Additional independent calibration and whole-project audit.
from onebigjump.e1.artifacts import identity
import numpy as np
from scipy import stats
print("COLLECT_NEW_P3", flush=True)
selection_root = base / "runs/p3_selection_validation_20260913"
selection = completed_stage(selection_root)["data"]
selection_protocol = attach(audit/"p3_selection_v1/validation_protocol.json")
for p in sorted((audit/"p3_selection_v1").glob("code/*.py")): attach(p, recursive=False)
for name in ("protocol.json","method-freeze.json","validation.sbatch","preflight.sbatch",
             "validation-submission.json","preflight-submission.json"):
    attach(audit/"p3_selection_v1"/name, recursive=False)
selection_preflight = completed_stage(audit/"p3_selection_v1/preflight")
attach(selection_root/"replicates.jsonl", recursive=False)
attach(selection_root/"replicates.identity.json", recursive=False)
p3_candidate = completed_stage(audit/"reviews/p3-constrained-validation-v3")["data"]
for name in ("REPORT.md","fresh-point-audit.json","coverage-availability.png"):
    attach(audit/"reviews/p3-constrained-validation-v3"/name, recursive=False)
for p in sorted((audit/"p3_constrained_v1").glob("code/*.py")): attach(p,recursive=False)
for name in ("method-freeze.json","protocol.json"):
    attach(audit/"p3_constrained_v1"/name,recursive=False)
records = rows(selection_root/"replicates.jsonl")
expected = {name+":"+str(i) for name in selection_protocol["scenarios"]
            for i in range(selection_protocol["datasets_per_scenario"])}
assert len(records)==len(expected) and {r["trace_id"] for r in records}==expected
checks = Counter()
all_intervals = []
for ri,r in enumerate(records):
    path=Path(r["bootstrap_file"])
    assert digest(path)==r["bootstrap_sha256"]
    attach(path, recursive=False)
    with np.load(path,allow_pickle=False) as arr:
        for budget in selection_protocol["calibration_budgets"]:
            for j,method in enumerate(selection_protocol["methods"]):
                c=r["methods"][budget][method]
                if not c["applicable"]: continue
                draws=arr[budget+"_shape"][:,j]
                good=draws[np.isfinite(draws)]
                assert len(good)==c["percentile"]["valid"]
                assert dict(Counter(arr[budget+"_reason"][:,j]))==c["bootstrap_fit_reasons"]
                failures=[key+"_insufficient" for key,n in c["counts"].items()
                          if n<selection_protocol["eligibility"][key]]
                if len(good)/len(draws)<selection_protocol["statistics"]["valid_fraction"]:
                    failures.append("too_few_finite_bootstrap_fits")
                if c["point"] is None: failures.append("point_unusable")
                if min(selection_protocol["calibration_budgets"][budget],c["counts"]["failure_tail_tasks"])<selection_protocol["statistics"]["min_tasks"]:
                    failures.append("too_few_independent_tasks")
                assert failures==c["unavailable_reasons"]
                available=not failures
                assert (c["percentile"]["ci95"] is not None)==available
                for kind in selection_protocol["interval_kinds"]:
                    interval=c[kind]["ci95"]
                    if available:
                        expected_ci=np.quantile(good,[.025,.975])
                        if kind=="basic": expected_ci=2*c["point"]-expected_ci[::-1]
                        assert np.allclose(interval,expected_ci,rtol=1e-12,atol=1e-12)
                        checks["interval_endpoints"]+=2
                    all_intervals.append({"scenario":r["request"]["scenario"],"budget":budget,"method":method,
                                          "kind":kind,"available":available,
                                          "covered":available and interval[0]<=r["truth"]<=interval[1]})
                if r["selection"]=="hard":
                    assert int((arr[budget+"_threshold"][:,j]<r["true_support_diagnostic_only"]).sum())==c["bootstrap_threshold_below_true_support"]
                checks["gates_and_arrays"]+=1
    if (ri+1)%200==0: print("P3_RECHECK",ri+1,len(records),flush=True)
for scenario,item in selection["scenarios"].items():
    for key,c in item["cells"].items():
        if not c["applicable"]: continue
        budget,method,kind=key.split("/")
        selected=[x for x in all_intervals if x["scenario"]==scenario and x["budget"]==budget and x["method"]==method and x["kind"]==kind]
        a=sum(x["available"] for x in selected)
        hit=sum(x["covered"] for x in selected)
        assert c["availability"]["successes"]==a
        assert c["coverage_conditional"]["successes"]==hit and c["coverage_conditional"]["datasets"]==a
        assert c["coverage_counting_unavailable_as_failure"]["successes"]==hit
        assert c["coverage_counting_unavailable_as_failure"]["datasets"]==len(selected)
        checks["summary_cells"]+=1
selection_audit={"datasets":len(records),"checks":dict(checks),"mismatches":0,
                 "scope":"independent reconstruction of eligibility, percentile/basic ci95 and all summary denominators from saved arrays; not a second independent simulator",
                 "primary_changed":False}
write_once(out/"selection-integrity.json",selection_audit)

print("COLLECT_P4_CONTROLS",flush=True)
p4=[]
for arm in ("real","null"):
    for seed in range(5):
        root=base/"runs/expansion_20260911/p4"/(arm+"-"+str(seed))
        train=attach(root/"training/manifest.json")
        measurement=completed_stage(root/"measurement")
        tail=attach(root/"tail/manifest.json")
        first=attach(root/"measurement/step-000000.json")
        last=attach(root/"measurement/step-040000.json")
        grid=[attach(p) for p in sorted((root/"tail").glob("step-*.json"))]
        p4.append({"arm":arm,"seed":seed,"training":train["metrics"],"measurement":measurement["data"],
                   "first":first,"final":last,"tail_grid":grid})
pilot_controls={}
pilot_lineage={}
for model in main:
    directory=controls_root/"pilot"/model
    pilot_controls[model]={}
    for manifest in sorted(directory.glob("*/manifest.json")):
        pilot_controls[model][manifest.parent.name]=completed_stage(manifest.parent)["data"]
    positional=pilot_controls[model]["positional"]
    control_model=Path(positional["model_root"])
    current=base/"runs/lean_reverification_20260913_local"/model
    old_labels=control_model/"pilot/verification/labels.jsonl"
    new_labels=current/"pilot/verification/labels.jsonl"
    attach(old_labels.parent/"manifest.json")
    attach(new_labels.parent/"manifest.json")
    old={r["trace_id"]:r for r in rows(old_labels)}
    new={r["trace_id"]:r for r in rows(new_labels)}
    fields=("category","t_star","whole_proof_ok","replay_ok")
    changed=[i for i in sorted(set(old)&set(new)) if any(old[i].get(k)!=new[i].get(k) for k in fields)
             or [(s["status"],s["valid"]) for s in old[i]["steps"]]!=[(s["status"],s["valid"]) for s in new[i]["steps"]]]
    pilot_lineage[model]={"control_model_root":str(control_model),"current_model_root":str(current),
                           "old_labels":digest(old_labels),"current_labels":digest(new_labels),
                           "shared_ids":len(set(old)&set(new)), "changed_semantic_labels":len(changed),
                           "changed_ids":changed,"only_old_ids":sorted(set(old)-set(new)),
                           "only_new_ids":sorted(set(new)-set(old)),
                           "scope":"semantic label comparison; does not establish numerical equivalence of re-extracted activations"}
main_shards={}
for model in main:
    root=base/"runs/lean_reverification_20260913_local"/model
    generation,_=generation_inputs(root,"main")
    planned={r["trace_id"]:r for r in generation}
    seen_ids=set(); summary=Counter(); complete=[]
    absorption=[]; mismatches=[]; unplanned=[]; duplicate=[]
    native=0
    for manifest in sorted((root/"main/verification").glob("shard-*/manifest.json")):
        attach(manifest)
        path=manifest.parent/"labels.jsonl"
        # Include final labels from completed shards so another reviewer can inspect individual cases.
        attach(path,recursive=False)
        labels=rows(path)
        inventory=native_policy_inventory(path)
        native+=inventory["native_policy_only_count"]
        for r in labels:
            i=r["trace_id"]
            if i in seen_ids: duplicate.append(i)
            seen_ids.add(i)
            if i not in planned: unplanned.append(i)
            else:
                if r.get("request_sha256")!=identity(planned[i]): mismatches.append(i)
            t=r.get("t_star")
            for step in r.get("steps",[]):
                if t is not None and (step["index"]>=t and step["valid"] or step["index"]>t and step["status"]!="unreached"):
                    absorption.append([i,step["index"]])
            summary[r["category"]]+=1
        complete.append({"shard":manifest.parent.name,"attempts":len(labels),"native_policy_only":inventory["native_policy_only_count"]})
    assert not (absorption or mismatches or duplicate or unplanned)
    main_shards[model]={"completed_shards":complete,"final_labels":len(seen_ids),"planned_attempts":len(planned),
                         "categories":dict(summary),"native_policy_only":native,
                         "absorption_violations":absorption,"row_digest_mismatches":mismatches,
                         "duplicate_ids":duplicate,"unplanned_ids":unplanned,
                         "scope":"only shards with final manifest; provisional running journals reported separately"}
print("COLLECTION_COMPLETE",flush=True)


finished=datetime.now(timezone.utc).isoformat()
metrics={"started_utc":started,"finished_utc":finished,"source":str(source),"source_sha256":digest(source),
 "queues":queues,"main":main,"main_completed_shards":main_shards,"runtime_validation":validation,
 "compiler_review":compiler_review,"pilot_attestation":pilot_attestation,
 "deduction_v2_review":ded_review,"deduction_v3":deduction_exact,
 "pilot_controls":pilot_controls,"pilot_control_lineage":pilot_lineage,"main_controls":controls,
 "p4":p4,"p3_selection":selection,"p3_selection_integrity":selection_audit,
 "p3_selection_preflight":selection_preflight,"p3_constrained":p3_candidate,"historical_p3":p3,
 "primary_method_changed":False,
 "scope":"current programme and selected historical evidence; not a new execution of every draft experiment"}
write_once(out/"metrics.json",metrics)
lines=[]
def para(s): lines.extend([s,""])
def table(headers,data):
    lines.extend(["| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |"])
    for row in data: lines.append("| "+" | ".join(str(v).replace("|","/").replace("\n"," ") for v in row)+" |")
    lines.append("")
def num(v):
    if v is None:return "NA"
    if isinstance(v,float):return f"{v:.5g}"
    return str(v)
def prop(p):
    return f'{p["successes"]}/{p["datasets"]} ({100*p["fraction"]:.2f}%)' if p["fraction"] is not None else "NA"
def ci(v):return "["+", ".join(num(x) for x in v)+"]" if v is not None else "NA"
def link(path,label):
    return "["+label+"](artifacts/"+str(Path(path).relative_to(base))+")"
primary=selection_protocol["primary_candidate"]
under=[name for name,v in selection["primary_family_monte_carlo"].items() if v["undercoverage_detected"]]
para("# One Big Jump: общая ревизия и проверка порога P3")
para("Срез на Жоресе: "+started+" — "+finished+". Все числа автоматически прочитаны из артефактов серверных запусков. Slurm job отчёта: "+os.environ.get("SLURM_JOB_ID","unknown")+". Время — UTC; Москва UTC+3.")
para("## Главный вывод")
para("Измерительный контур стал надёжнее, но основные научные предсказания пока нельзя объявить подтверждёнными. Генерация сохранена; исправленная проверка Lean продолжается. P4 воспроизвёл обучение без подтверждённого перехода хвостового индекса. Дедукционные пилоты не прошли допуск по формату. Новая проверка P3 отделяет проблемы оптимизации от порога, отбора и малого объёма калибровки.")
para("Новая независимая проверка завершена: "+str(selection["parent_datasets"])+" родительских наборов и "+str(selection["analysis_conditions"])+" условий по объёму calibration. Кандидат зафиксирован заранее: "+primary+". "+("Семейная проверка Monte Carlo обнаружила недопокрытие: "+", ".join(under)+"." if under else "Семейная проверка Monte Carlo не обнаружила недопокрытия в четырёх точных hard-сценариях; это не доказательство номинального покрытия на реальных данных.")+" Основной метод не заменён.")
para("Для дальнейшей работы: [план](NEXT_PLAN.md), [задание другому GPT](FOR_REVIEWING_GPT.md), [метрики](metrics.json), [все ячейки P3](P3_ALL_CELLS.md), [независимая сверка интервалов](selection-integrity.json).")
para("## Границы ревизии")
para("Проверены текущие очереди, завершённые main-шарды, валидация Lean и смысл native-policy исключений, оба пилота дедукции, происхождение пилотных контролей, все парные P4, новый и предыдущий P3. Хеши проверяются рекурсивно на сервере. Полные веса и активации остаются на сервере. Это не новый прогон всех исторических симуляций и всех экспериментов draft.")
table(["Ветка","Вычислительное состояние","Научное состояние"],[
["Основная Lean","Генерация сохранена; проверка/последующие стадии выполняются","Полные P1/P2/P3 ещё не готовы"],
["P3 optimizer","Численные проверки и независимая валидация завершены","Ремонт optimizer сам по себе не устраняет недопокрытие"],
["P3 threshold/selection","Новая фиксированная проверка завершена","Ограничения и все сценарии ниже"],
["Whitening/позиция","Пилотная сетка завершена; main ждёт измерений","Чувствительность к calibration и первому шагу"],
["P4","Парные real/null завершены","Обучение есть; ожидаемый переход xi не показан"],
["Дедукция/P5","Два development-пилота не прошли gate","Main закрыт; P5 пока не тестируется"],
["Программа draft","Реализована частично","Нельзя заявлять полную репликацию"]])
para("## Основная кампания")
table(["Модель","Сохранено генераций","Задач","Завершено шардов проверки","Итоговых меток шардов","Строк в текущих журналах"],
 [[m,v["saved_attempts"],v["distinct_tasks"],len(main_shards[m]["completed_shards"]),main_shards[m]["final_labels"],sum(p["complete_records"] for p in v["verification_progress"])] for m,v in main.items()])
para("Всего сохранено "+str(sum(v["saved_attempts"] for v in main.values()))+" попыток. Новые метки завершённых шардов сверены по request_sha256=identity исходных попыток; посторонних ID, дублей и нарушений absorption не найдено. Исходные токены не перегенерировались. Это проверка целостности и формальных инвариантов, не ручное доказательство правильности каждой метки.")
table(["Очередь","Состояния","Последний опрос UTC"],[[k,json.dumps(v["counts"]),v["last_poll_utc"]] for k,v in queues.items()])
table(["Модель","Стадия","Итоговый manifest доступен"],[[m,s,bool(main[m]["main"][s])] for m in main for s in ("verification","extraction","measurement","analysis")])
para("Захваченный squeue:")
para("~~~text\n"+(out/"inputs/squeue.txt").read_text(encoding="utf-8").strip()+"\n~~~")
para("COMPLETED в графе задач включает сохранённые входы и зависимости; это не процент научной готовности. Частичные журналы не заменяют итоговый gather. Старые FAILED/BLOCKED относятся к сохранённой истории инцидента, а не автоматически к текущему v7.")
table(["Модель","Категория завершённых меток","Число"],[[m,k,n] for m,v in main_shards.items() for k,n in v["categories"].items()])
para("## Lean: надёжность и исключения")
para("Авторитетный snapshot: "+str(source.parent)+". SHA256 source-manifest: "+digest(source)+". Git commit и dirty state записаны в manifests. Точная версия задаётся замороженными хешами, а не только commit.")
table(["Полная валидация","Результат"],[[k,v] for k,v in validation["test_counts"].items()])
para("Полный набор включал live Lean и GPT-2. Дополнительно проверены реальные доказательства, scopes без переноса константы-ответа, proofStatus, очистка процессов, отделение I/O от математических ошибок и полный toolchain на диске узла. Успех этих проверок не означает, что первопричина сетевого I/O установлена.")
ar=pilot_attestation["data"];cr=compiler_review["data"]
para("Содержательный разбор фиксированного gate-пакета: "+str(ar["reviewed_examples"])+" примеров, "+str(ar["compilations"])+" компиляций; инфраструктурных ошибок "+str(cr["infrastructure_errors"])+", нарушений absorption "+str(cr["absorbing_violations"])+". Это ревью ассистентом, не человеческая подпись и не случайная выборка main. "+link(audit/"8466083-review-attestation/case-review.json","Пояснения по каждому случаю")+".")
table(["Модель","Native-policy-only исключения","Меток в проверенных main-шардах"],[[m,v["native_policy_only"],v["final_labels"]] for m,v in main_shards.items()])
para("Native-policy-only: whole proof и replay прошли, буквальных formal sorry/admit нет, но фиксированная allowlist не разрешает вспомогательную аксиому native_decide, которую создаёт pinned Lean. Это нельзя называть математической ошибкой модели. Основные метки сохранены. Native-inclusive анализ потребует отдельного режима доверия, проверки происхождения аксиом и нового manifest; регулярная allowlist только по имени недостаточна.")
para("## P3: от численной ошибки к порогу и отбору")
para("Предыдущая диагностика выявила неустойчивость старого fit около границы параметров. Ограниченный кандидат ищет внутренние stationary maxima при gamma > -1 и сравнивает их с uniform boundary. Победа границы остаётся недоступной оценкой, а внутренние отрицательные gamma сохраняются.")
para("Численный preflight: "+str(p3_candidate["preflight"]["cases"])+" случаев; проверено на плотной сетке "+str(p3_candidate["fresh_point_checks"])+" точек, расхождений "+str(p3_candidate["fresh_point_mismatches"])+". Предыдущая независимая validation: "+str(p3_candidate["validation"]["datasets"])+" наборов. "+link(audit/"reviews/p3-constrained-validation-v3/REPORT.md","Полный предыдущий отчёт")+".")
para("Если ошибки отбираются только выше c, fit excess Z−tau при tau<c использует неверную нижнюю границу. При корректном u>=c условная GPD сохраняет gamma, а scale меняется как sigma+gamma*u. Эта идентичность проверена до новой генерации. [Первичная работа о threshold exceedances](https://academic.oup.com/jrsssb/article/52/3/393/7027838).")
table(["Параметр нового протокола","Значение"],[
["Seed",selection_protocol["seed"]],["Наборов на сценарий",selection_protocol["datasets_per_scenario"]],
["Calibration задач",selection_protocol["calibration_budgets"]],["Evaluation задач",selection_protocol["evaluation_tasks"]],
["Support-pilot задач",selection_protocol["support_tasks"]],["Calibration шагов/задачу",selection_protocol["steps_per_calibration_task"]],
["Failure значений/задачу",selection_protocol["failures_per_task"]],["q",selection_protocol["q"]],
["Bootstrap",selection_protocol["statistics"]["bootstrap"]],["Минимум задач",selection_protocol["statistics"]["min_tasks"]],
["Primary candidate",primary]])
table(["Метод","Правило и данные"],[
["original","tau из calibration; fit на evaluation"],
["observed_minimum","max(tau,min evaluation failure): выбор нижней границы на той же выборке"],
["independent_floor","max(tau,min support-pilot failure): отдельная выборка для границы, fit на evaluation"],
["oracle_correct_selection","max(tau,true c): диагностическое недоступное на реальных данных знание"],
["pooled_original","tau из calibration; fit на evaluation+pilot: тот же общий failure-бюджет, что у independent_floor"]])
para("Calibration двух объёмов вложена. Потоки calibration/evaluation/support независимы; bootstrap пересэмплирует задачи во всех группах и пересчитывает порог. Optimizer совпадает с ранее замороженным байт-в-байт. Все методы и percentile/basic сохранены. SeedSequence и роли потоков указаны в протоколе. [Документация NumPy](https://numpy.org/doc/stable/reference/random/bit_generators/generated/numpy.random.SeedSequence.html).")
para("Hard-сценарии включают положительную форму с двумя границами отбора, exponential и bounded null. Soft stress использует плавную вероятность отбора с ненулевым фоном: конечная выбранная выборка не имеет точного GPD-распределения. Её результаты — восстановление parent/asymptotic target при ошибке спецификации, а не точное coverage GPD. Oracle там неприменим.")
para("### Результаты percentile: все методы и бюджеты")
table(["Сценарий","Calibration","Метод","Доступность","Покрытие доступных","Попадание / все","Bias","Width"],
 [[name,budget,method,prop(c["availability"]),prop(c["coverage_conditional"]),prop(c["coverage_counting_unavailable_as_failure"]),
   num(c["mean_point_bias"]),num(c["mean_width"])]
  for name,s in selection["scenarios"].items() for budget in selection_protocol["calibration_budgets"] for method in selection_protocol["methods"]
  for c in [s["cells"][budget+"/"+method+"/percentile"]] if c["applicable"]])
para("«Попадание / все» считает отсутствие интервала неуспехом процедуры. Это не условное покрытие. Все basic, Monte Carlo CI, направления промахов и причины недоступности — в P3_ALL_CELLS.md.")
para("### Зафиксированный кандидат: неопределённость Monte Carlo")
table(["Hard-сценарий","Покрытие","Семейные MC bounds","Недопокрытие обнаружено"],
 [[name,prop(selection["scenarios"][name]["cells"][primary]["coverage_conditional"]),ci(d["mc_family_95_bounds"]),d["undercoverage_detected"]]
 for name,d in selection["primary_family_monte_carlo"].items()])
para("Семейные bounds учитывают четыре hard-сценария фиксированного кандидата. Это не поправка за выбор лучшей ячейки из всей сетки и не тест эквивалентности номинальному уровню. Выбирать победителя после просмотра этой таблицы нельзя.")
table(["Сценарий","Calibration","Сравнение independent_floor с","Общие доступные","Попадания reference / candidate","Выиграно / потеряно интервалов"],
 [[name,budget,ref,p["common"],str(p["reference_covered_common"])+" / "+str(p["candidate_covered_common"]),
 str(p["gained_intervals"])+" / "+str(p["lost_intervals"])]
 for name,s in selection["scenarios"].items() for budget in selection_protocol["calibration_budgets"]
 for ref in ("original","pooled_original","oracle_correct_selection")
 for p in [s["paired"][budget+"/independent_floor_vs_"+ref+"/percentile"]]])
para("Independent floor меняет само правило порога; его перенос в primary P3 был бы изменением протокола. Oracle — контроль механизма, не практическое решение. Увеличение calibration одновременно влияет на точность tau и прохождение gate; поэтому оба показателя отчётны.")
para("q=0.001, межзадачная heterogeneity, сильная зависимость шагов, whitening и поглощающий отбор первой ошибки не проверены этим генератором. Значения внутри синтетических групп независимы; task-bootstrap не делает их реалистично зависимыми. Хороший результат здесь не устанавливает калибровку реального Lean.")
para("Независимая сверка по сохранённым draws: "+str(selection_audit["checks"]["gates_and_arrays"])+" условий gate/массивов, "+str(selection_audit["checks"]["summary_cells"])+" сводных ячеек, несовпадений "+str(selection_audit["mismatches"])+". Это аудит отчётности, не второй независимый симулятор.")
para("## Whitening и позиционные эффекты")
para("Пилотная сетка сохранена из раннего lineage. Сравнение семантических меток с текущей версией ниже. Оно не доказывает равенства заново извлечённых активаций. Main-контроли работают от новой основной кампании и до завершения зависимостей не считаются полученными.")
table(["Модель","Control root","Общих ID","Изменённых семантических меток","ID только с одной стороны"],
 [[m,v["control_model_root"],v["shared_ids"],v["changed_semantic_labels"],len(v["only_old_ids"])+len(v["only_new_ids"])] for m,v in pilot_lineage.items()])
control_rows=[]
for m,cs in pilot_controls.items():
    for name,data in cs.items():
        if not name.startswith("whitening"):continue
        v=data["variant"];s=v["specification"];t=v.get("threshold")
        if not t:continue
        e=t["evaluation"]["accepted_evaluation"]
        control_rows.append([m,name,s["disjoint"],s["drop_first"],s["shrinkage"],v["fit_increments"],v["effective_fit_tasks"],
            v["overlap_tasks"],num(t["tau"]),str(e["exceedances"])+"/"+str(e["steps"]),num(e["exceedance_rate"])])
table(["Модель","Вариант","Disjoint","Drop first","Shrinkage","Fit шагов","Fit задач","Overlap задач","tau","Accepted > tau","Доля"],control_rows)
para("Повторное использование calibration для transform и threshold занижает порог относительно новых трасс. Disjoint меняет результат, но малая выборка не устанавливает номинальную tail-вероятность. Shrinkage и исключение первого приращения остаются вторичными проверками; основной слой/статистика/температура сохранены.")
table(["Модель","Статистика","Трасс/задач","Jump top1","Surprisal top1","Парный gain","CI"],
 [[m,stat,str(v["P2"]["all"]["n_traces"])+"/"+str(v["P2"]["all"]["n_tasks"]),num(v["P2"]["all"]["jump_top1"]),
 num(v["P2"]["all"]["surprisal_top1"]),num(v["P2"]["all"]["paired_gain"]),ci(v["P2"]["all"]["paired_ci95"])]
 for m,cs in pilot_controls.items() for stat,v in cs["positional"]["cells"].items()])
para("Jump и surprisal сравниваются на одинаковых trace IDs. При недостатке независимых задач CI отсутствует. Исключение первого шага может исключить и трассы, ошибившиеся на нём: популяция меняется. Высокий raw top1 без позиционного контроля не доказывает локализацию математического отказа.")
para("## P4: все парные real/null")
table(["Arm","Seed","Финальная test accuracy","Moment до / после","GPD до / после","Hill до / после","Решение"],
 [[v["arm"],v["seed"],num(v["final"]["test_acc"]),
 num(v["measurement"]["primary_transition"]["moment"]["before"])+" / "+num(v["measurement"]["primary_transition"]["moment"]["after"]),
 num(v["measurement"]["primary_transition"]["gpd"]["before"])+" / "+num(v["measurement"]["primary_transition"]["gpd"]["after"]),
 num(v["measurement"]["primary_transition"]["hill"]["before"])+" / "+num(v["measurement"]["primary_transition"]["hill"]["after"]),
 v["measurement"]["scientific_decision"]] for v in p4])
para("Окна вокруг устойчивого перехода test accuracy и fixed-final-frequency измерения сохранены в metrics. Null сопоставляется по парной reference-точке. Независимая единица межзапускового сравнения — training seed. Checkpoint и примеры сложения не увеличивают число независимых training-репликаций.")
para("Пять пар дают ограниченную мощность. Итог: обучение подтверждено; ожидаемый переход xi не продемонстрирован. Отрицательная точечная moment/GPD сама по себе не доказывает bounded support, а положительный Hill не доказывает тяжёлый хвост. Все три оценивателя показаны без clipping gamma.")
para("Fixed-fraction кривые measurement и полная tail-сетка с выбором k — разные анализы. Полные tail/step-*.json включены. Старые GPD bootstrap сохраняют ограничения прежнего fit и не заменены новым кандидатом в этой ревизии.")
para("## Дедукция и P5")
para("worked-example-v2: полный аудит в metrics.json → deduction_v2_review. numbered-slots-v3: "+json.dumps(deduction_exact.get("label_summary",{}),ensure_ascii=False)+". Оба пилота не прошли gate; main остаётся закрыт.")
para("Gold-checker проверки, исходные ответы и причины исключений сохранены. Задачи между пилотами свежие: это не парный причинный тест промптов. Неизвестные строки/комментарии не удалялись ради gate. Формат и reasoning разделены: повтор исходного факта не считается новым modus ponens.")
para("P5 требует управляемой длины и отложенных задач/длин. Из одной зависимости exp(-theta*L*Fbar(tau)) свободные theta и tau не определяются раздельно без дополнительных ограничений: length-данные определяют произведение. Нужно фиксировать tau и calibration law, отдельно проверять зависимость; сильное утверждение о tolerance требует интервенции по tolerance.")
para("## Остаток полного контракта статьи")
table(["Раздел","Что ещё нужно"],[
["P1/P2/P3 main","Полная разметка → активации → измерения → фиксированный анализ → согласованные контроли"],
["P1","Все три gamma, k-устойчивость и bands, семейства задач, split-half, task resampling и честные NA"],
["P2","Парный surprisal, позиционный null по длине/семейству, первый шаг, ROC; supervised probe отдельной работой"],
["P3","q=0.001, зависимость, heterogeneity, selection и независимая калибровка до confirmatory CI"],
["P4","Итоговый paired seed рисунок/вывод с ограничениями; без новых seeds ради желаемого знака"],
["P5","Допуск deduction, held-out длины/задачи, идентифицируемая модель и зависимый null"],
["Kesten/Figure 1","Отдельно сверить publication-run с контрактом и digests; здесь симуляция заново не запускалась"],
["Другие ветки","ProofNet/PutnamBench, другие deduction-модели, two-hop, recurrent depth, Tracr/ngram нельзя считать завершёнными"],
["Публикация","Generated tables/figures, compute accounting, исключения, анонимный репозиторий и ограничения"]])
para("## Следующие действия и независимый аудит")
para("Подробные приоритеты, зависимости и критерии завершения — в [NEXT_PLAN.md](NEXT_PLAN.md). Ближайший результат: целостная основная выборка и контроли на одной версии измерений, затем научное решение по фиксированной ячейке. Рост данных не исправляет ошибку модели отбора.")
para("artifact-index.json сопоставляет серверные пути, копии и SHA256. manifest.json содержит provenance отчёта, package versions, hardware и digests. source/ — основной v7; экспериментальный P3-код — в artifacts/audit/revision_2026_09_13/p3_selection_v1/code. Все новые bootstrap draws включены. Отсутствующие внешние веса/активации reviewer должен явно перечислить как непроверенные.")
(out/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
lines=[]
para("# P3: все ячейки и причины недоступности")
for scenario,item in selection["scenarios"].items():
    para("## "+scenario)
    table(["Ячейка","Доступность","Условное покрытие","MC CI95","Попадание / все","Bias","Width","Промах ниже / выше"],
      [[key,prop(c["availability"]),prop(c["coverage_conditional"]),ci(c["coverage_conditional"]["monte_carlo_ci95"]),
      prop(c["coverage_counting_unavailable_as_failure"]),num(c["mean_point_bias"]),num(c["mean_width"]),
      str(c["miss_below_truth"])+" / "+str(c["miss_above_truth"])]
      for key,c in item["cells"].items() if c["applicable"]])
    for key,c in item["cells"].items():
        if not c["applicable"] or not key.endswith("/percentile"):continue
        para("### "+key)
        para("Недоступность: "+json.dumps(c["unavailable_reason_sets"],ensure_ascii=False)+".")
        para("Bootstrap fit: "+json.dumps(c["bootstrap_fit_reasons"],ensure_ascii=False)+".")
        para("Порог ниже support, original / bootstrap: "+str(c["point_threshold_below_support"])+" / "+str(c["bootstrap_threshold_below_support"])+".")
(out/"P3_ALL_CELLS.md").write_text("\n".join(lines),encoding="utf-8")


for filename in ("NEXT_PLAN.md","FOR_REVIEWING_GPT.md"):
    template=Path(__file__).parent/(filename+".template")
    inputs.append(template)
    shutil.copy2(template,out/filename)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig,axes=plt.subplots(2,2,figsize=(16,10),sharex=True,sharey=True)
names=list(selection_protocol["scenarios"])
colors=plt.get_cmap("tab10")
for bi,budget in enumerate(selection_protocol["calibration_budgets"]):
    for col,key in enumerate(("availability","coverage_conditional")):
        ax=axes[bi,col]
        for mi,method in enumerate(selection_protocol["methods"]):
            for si,name in enumerate(names):
                c=selection["scenarios"][name]["cells"][budget+"/"+method+"/percentile"]
                if not c["applicable"]:continue
                p=c[key]; value=p["fraction"]
                if value is None:continue
                low,high=p["monte_carlo_ci95"]
                ax.errorbar(si+(mi-2)*.13,value,yerr=[[value-low],[high-value]],
                            fmt="o",markersize=4,capsize=2,color=colors(mi),
                            label=method if si==0 else None)
        ax.axhline(.95,color="black",linestyle="--",alpha=.4)
        ax.axvspan(3.55,4.5,color="orange",alpha=.08)
        ax.set_ylim(0,1.03);ax.set_xlim(-.5,4.5)
        ax.set_title(budget+" calibration: "+("interval availability" if col==0 else "target inclusion, conditional"))
        ax.set_xticks(range(len(names)),[x.replace("_","\n") for x in names],fontsize=8)
        ax.grid(axis="y",alpha=.15)
axes[0,0].legend(fontsize=8,loc="lower left")
fig.suptitle("P3 fixed threshold/selection validation\nSoft selection: misspecified target recovery, not exact GPD coverage",fontsize=13)
fig.tight_layout(rect=(0,0,1,.94))
fig.savefig(out/"p3-selection.png",dpi=180)
fig.savefig(out/"p3-selection.pdf")
plt.close(fig)
report=(out/"REPORT.md").read_text(encoding="utf-8")
report=report.replace("### Зафиксированный кандидат: неопределённость Monte Carlo","![P3: доступность и попадание в target](p3-selection.png)\n\n### Зафиксированный кандидат: неопределённость Monte Carlo")
(out/"REPORT.md").write_text(report,encoding="utf-8")
write_once(out/"artifact-index.json",artifacts)
inputs.append(out/"code/collector.py")
outputs=[p for p in out.rglob("*") if p.is_file()]
finish(out,stage="whole-project-revision-after-independent-selection-validation",
 context={"source":digest(source),"started_utc":started,"primary_method_changed":False},
 inputs=list(dict.fromkeys(inputs)),outputs=outputs,
 metrics={"started_utc":started,"finished_utc":finished,"primary_method_changed":False,
          "main_analysis_complete":all(m["main"]["analysis"] for m in main.values()),
          "p3_selection_validation_complete":True,"p3_recheck":selection_audit})
print("FULL_REVIEW_WRITTEN",out,flush=True)
