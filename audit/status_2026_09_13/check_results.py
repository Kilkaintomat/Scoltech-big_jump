"""Read-only scientific audit, executed on a Slurm node."""
from pathlib import Path
from collections import Counter
import json,sys,re
from onebigjump.e1.artifacts import read_json,verify_manifest,finish,write_once,identity,digest
from onebigjump.e1.generation import planned_requests

base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
folder=Path(sys.argv[1])
inputs=list((folder/"inputs").iterdir())
checks={}
def checked(path):
    path=Path(path)
    key=str(path.resolve())
    if key in checks:return
    try:
        verify_manifest(path)
        checks[key]={"ok":True}
        inputs.append(path)
    except Exception as exc:
        checks[key]={"ok":False,"error":str(exc)}
    print("checked",path,checks[key]["ok"],flush=True)

def journal(path):
    path=Path(path)
    if not path.exists():return []
    context=identity(read_json(path.with_suffix(".identity.json")))
    data=[]
    seen=set()
    for line in path.read_bytes().splitlines(keepends=True):
        if not line.endswith(b"\n"):raise ValueError("torn final row: "+str(path))
        row=json.loads(line);expected=row.pop("row_sha256")
        if expected!=identity(row) or row["context_sha256"]!=context or row["trace_id"] in seen:
            raise ValueError("invalid journal: "+str(path))
        seen.add(row["trace_id"]);data.append(row)
    inputs.extend([path,path.with_suffix(".identity.json")])
    return data

lean=base/"runs/lean_reverification_20260912"
exp=base/"runs/expansion_20260911"
metrics={"cutoff":read_json(folder/"inputs/cutoff.json"),"lean":{},"p4":{},"deduction":{},"checks":checks}
for model in ("deepseek","goedel","kimina"):
    root=lean/model
    config=read_json(root/"main/protocol.json")
    plan=planned_requests(root,"main",config)
    ids=[]
    for manifest in sorted((root/"main/generation").glob("shard-*/manifest.json")):
        checked(manifest)
        records=journal(manifest.parent/"samples.jsonl")
        ids.extend(r["trace_id"] for r in records)
    m={"planned_attempts":len(plan),"generated_attempts":len(ids),"unique_generated_ids":len(set(ids)),
       "missing_ids":sorted({r["trace_id"] for r in plan}-set(ids)),
       "unexpected_ids":sorted(set(ids)-{r["trace_id"] for r in plan}),"pilot":{},"main_shards":[]}
    for stage in ("verification","extraction","measurement","analysis"):
        path=root/"pilot"/stage/"manifest.json"
        if path.exists():
            checked(path);m["pilot"][stage]=read_json(path)["metrics"]
    labels=[]
    for p in sorted((root/"main/verification").glob("shard-*")):
        records=journal(p/"labels.jsonl");labels.extend(records)
        manifested=(p/"manifest.json").exists()
        if manifested:checked(p/"manifest.json")
        m["main_shards"].append({"name":p.name,"rows":len(records),"manifest":manifested,
            "categories":dict(Counter(r["category"] for r in records)),
            "unexplained":[{"trace_id":r["trace_id"],"whole":r.get("whole_proof_ok"),
                           "replay":r.get("replay_ok"),"messages":[s.get("message","") for s in r.get("steps",[]) if s.get("message")]}
                          for r in records if r.get("unexplained_disagreement")]})
    m["partial_label_rows"]=len(labels)
    m["partial_label_categories"]=dict(Counter(r["category"] for r in labels))
    m["system_error_rows"]=[r["trace_id"] for r in labels if "too many open files" in json.dumps(r).lower()]
    metrics["lean"][model]=m
    print("lean complete",model,flush=True)

failures=[]
queue=read_json(folder/"inputs/lean-queue.json")
for key,task in queue["tasks"].items():
    if task.get("state")!="FAILED":continue
    logfile=lean/"logs"/(task["job_name"]+"-"+task["job_id"]+".log")
    text=logfile.read_text(errors="replace")
    cause="system_file_exhaustion" if "Too many open files in system" in text else "whole_replay_disagreement" if "whole-proof/replay disagreements" in text else "other"
    failures.append({"task":key,"job_id":task["job_id"],"cause":cause,"log":str(logfile)})
    inputs.append(logfile)
metrics["lean_failures"]=failures

checked(exp/"p4/summary/manifest.json")
metrics["p4"]["summary"]=read_json(exp/"p4/summary/metrics.json")
metrics["p4"]["runs"]=[]
for seed in range(5):
    for arm in ("real","null"):
        run=exp/"p4"/(arm+"-"+str(seed))
        for stage in ("training","measurement","tail"):checked(run/stage/"manifest.json")
        study=read_json(run/"measurement/metrics.json")
        final=read_json(run/"measurement/step-040000.json")
        first=read_json(run/"measurement/step-000000.json")
        grid=[]
        for step in (0,10000,20000,30000,40000):
            est=read_json(run/"tail"/("step-%06d.json"%step))["estimate"]
            grid.append({"step":step,"k":est["k"],"n":est["n"],"hill":est["hill"],"moment":est["moment"],
                         "gpd":est["gpd"],"xi":est["xi"],"identification":est["identification"],"bootstrap":est["bootstrap"]})
        metrics["p4"]["runs"].append({"arm":arm,"seed":seed,"training":read_json(run/"training/manifest.json")["metrics"],
            "primary_transition":study["primary_transition"],"first":first,"final":final,"tail_grid":grid})
        print("p4 complete",arm,seed,flush=True)

ded=exp/"deduction/pilot"
for stage in ("verification","extraction","measurement","analysis"):checked(ded/stage/"manifest.json")
labels=journal(ded/"verification/labels.jsonl")
analysis=read_json(ded/"analysis/metrics.json")
metrics["deduction"]={
    "attempts":len(labels),"categories":dict(Counter(r["category"] for r in labels)),
    "format_eligible":sum(bool(r.get("format_eligible")) for r in labels),
    "first_failure_distribution":dict(Counter(str(r.get("t_star")) for r in labels if r.get("format_eligible"))),
    "P5":analysis["P5"],
    "cells":[{"temperature":c["temperature"],"statistic":c["statistic"],"available":c["available"],
              "P2":{k:c.get("P2",{}).get(k) for k in ("n_traces","n_tasks","paired_difference","jump","surprisal")},
              "positional_null":c.get("positional_null"),"P3":c.get("P3")} for c in analysis["cells"]],
    "gate_result_exists":(ded/"gate/result.json").exists(),
    "gate_log":(exp/"logs/obj-exp11-deduction-gate-8465577.log").read_text(errors="replace")[-2000:],
}
# Representative failed proofs remain on the server; only aggregate error modes are exported.
samples=journal(ded/"generation/shard-000-of-001/samples.jsonl")
by_id={r["trace_id"]:r for r in samples}
examples=[]
for category in ("format_error","invalid_inference"):
    for r in [x for x in labels if x["category"]==category][:3]:
        examples.append({"label":r,"generation":by_id[r["trace_id"]]})
write_once(folder/"deduction-examples-server-only.json",examples)
metrics["p3"]=read_json(base/"runs/p3_diagnosis_20260912/summary/metrics.json")
checked(base/"runs/p3_diagnosis_20260912/summary/manifest.json")
metrics["all_checked_manifests_valid"]=all(v["ok"] for v in checks.values())
write_once(folder/"metrics.json",metrics)
finish(folder,stage="project-status-audit",context={"cutoff":metrics["cutoff"]},
       inputs=[Path(__file__),*inputs],outputs=[folder/"metrics.json",folder/"deduction-examples-server-only.json"],
       metrics={"all_checked_manifests_valid":metrics["all_checked_manifests_valid"],"manifest_count":len(checks)})
print("AUDIT FINISHED",folder,flush=True)
