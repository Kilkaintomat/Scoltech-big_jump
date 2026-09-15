"""Bounded read-only audit of completed repaired pilot stages, executed in Slurm."""
from pathlib import Path
from datetime import datetime, timezone
import collections, json, os, re
import pandas as pd
from onebigjump.e1.artifacts import finish, verify_manifest
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
out=base/"audit/revision_2026_09_13"/("progress-audit-"+os.environ["SLURM_JOB_ID"])
out.mkdir(exist_ok=False)
new=base/"runs/lean_reverification_20260913_local"
old=base/"runs/lean_reverification_20260913"
inputs=[Path(__file__),Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"]
metrics={"started_utc":datetime.now(timezone.utc).isoformat(),"models":{},"infrastructure_log_hits":[],"main_analysis_complete":False}
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def rows(path):return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]
def semantic(r):
    return {**{k:r.get(k) for k in ("category","t_star","whole_proof_ok","replay_ok","unexplained_disagreement","explained_resource_disagreement")},
            "steps":[{k:s.get(k) for k in ("index","status","valid")} for s in r.get("steps",[])]}
for model in ("deepseek","goedel","kimina"):
    root=new/model/"pilot"; previous=old/model/"pilot"
    entry={"verification_complete":(root/"verification/manifest.json").exists(),"stages":{}}
    for stage in ("verification","extraction","measurement","analysis"):
        p=root/stage/"manifest.json"
        if p.exists():
            verify_manifest(p)
            inputs.append(p)
            entry["stages"][stage]=read(p)["metrics"]
    if entry["verification_complete"]:
        a=root/"verification/labels.jsonl";b=previous/"verification/labels.jsonl"
        inputs.extend([a,b,previous/"verification/manifest.json"])
        verify_manifest(previous/"verification/manifest.json")
        fresh={r["trace_id"]:r for r in rows(a)};prior={r["trace_id"]:r for r in rows(b)}
        mismatches=[k for k in fresh.keys() & prior.keys() if semantic(fresh[k]) != semantic(prior[k])]
        absorbing_errors=[]
        for k,r in fresh.items():
            t=r.get("t_star")
            if t is not None:
                for step in r.get("steps",[]):
                    if step["index"]>t and (step.get("valid") or step.get("status")!="unreached"):absorbing_errors.append(k)
        entry["semantic_comparison"]={"new_attempts":len(fresh),"previous_attempts":len(prior),"identical_ids":set(fresh)==set(prior),"changed_trace_ids":mismatches,"absorbing_errors":absorbing_errors}
        trajectory=root/"extraction/trajectories.jsonl"
        tables=list((root/"measurement").glob("*.parquet"))
        if trajectory.exists() and tables:
            inputs.extend([trajectory,*tables])
            all_trajectories=rows(trajectory)
            extracted={r["trace_id"]:r for r in all_trajectories if r.get("extraction_status")=="extracted"}
            table=pd.concat([pd.read_parquet(p) for p in tables],ignore_index=True)
            included=set(table["trace_id"])
            missing=sorted(set(extracted)-included)
            entry["measurement_denominator"]={"trajectory_rows":len(all_trajectories),"extracted":len(extracted),"extraction_statuses":dict(collections.Counter(r.get("extraction_status") for r in all_trajectories)),"measured":len(included),"table_rows":len(table),
                "not_in_table":[{"trace_id":k,"verification":semantic(fresh[k]),"trajectory_metadata":{a:v for a,v in extracted[k].items() if a not in ("steps","vectors","hidden_states","surprisals","input_ids","completion")}} for k in missing]}
    metrics["models"][model]=entry
for p in (new/"logs").glob("*.log"):
    hits=[s for s in p.read_text(encoding="utf-8",errors="replace").splitlines() if re.search(r"remote i/o error|too many open files|fatal python|traceback",s,re.I)]
    if hits:metrics["infrastructure_log_hits"].append({"file":str(p),"hits":hits[-10:]})
queue=out/"queue.json";queue.write_bytes((new/"queue.json").read_bytes())
control=out/"controls-queue.json";control.write_bytes((base/"runs/controls_20260913_local/queue.json").read_bytes())
metrics["queue_counts"]=read(queue).get("counts")
metrics["control_counts"]=read(control).get("counts")
metrics["finished_utc"]=datetime.now(timezone.utc).isoformat()
p=out/"metrics.json";p.write_text(json.dumps(metrics,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
finish(out,stage="repaired_pilot_progress_audit",context={"source":os.environ["E1_SNAPSHOT"],"main_scientific_claims":False},inputs=inputs,outputs=[p,queue,control],metrics=metrics)
print(json.dumps({"output":str(out),"metrics":metrics},ensure_ascii=False))
