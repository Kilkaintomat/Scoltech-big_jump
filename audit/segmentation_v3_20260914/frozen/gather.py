from pathlib import Path
import argparse,collections,json,os
from onebigjump.e1.artifacts import digest,identity
from campaign_worker import read,atomic_json
p=argparse.ArgumentParser();p.add_argument("--root",required=True,type=Path);a=p.parse_args();root=a.root
inputs=read(root/"inputs/manifest.json");models={};total=0;missing=[];out=root/"summary"
out.mkdir(exist_ok=True);merged=out/"observations.jsonl";tmp=merged.with_suffix(".tmp")
with tmp.open("wb") as f:
 for k,shard in inputs["shards"].items():
    path=root/"shards"/f"{int(k):03d}";mf=path/"manifest.json"
    if not mf.exists():missing.append(k);continue
    m=read(mf)
    for file,h in m["outputs"].items():
        if digest(Path(file))!=h:raise ValueError("corrupt shard output")
    seen=set();c=models.setdefault(shard["model"],{"n":0,"statuses":collections.Counter(),"old_categories":collections.Counter(),
        "n_blocks":0,"n_positions":0,"p2_eligible":0,"token_rejections":0,"whole_disagreements":0})
    with (path/"observations.jsonl").open("rb") as stream:
      for line in stream:
        r=json.loads(line);rh=r.pop("row_sha256")
        if identity(r)!=rh or r["context_sha256"]!=identity(m["context"]):raise ValueError("corrupt result row")
        if r["trace_id"] in seen:raise ValueError("duplicate result")
        seen.add(r["trace_id"])
        if digest(path/r["artifact"])!=r["artifact_sha256"]:raise ValueError("corrupt annotation blob")
        f.write(line);total+=1;c["n"]+=1;c["statuses"][r["status"]]+=1;c["old_categories"][r["old_category"]]+=1
        c["n_blocks"]+=r.get("n_blocks",0);c["n_positions"]+=r.get("n_positions",0);c["p2_eligible"]+=r["p2_eligible"]
        c["token_rejections"]+=r.get("n_rejected_token_boundaries",0)
        c["whole_disagreements"]+=r["status"]=="whole_verdict_disagreement"
    if len(seen)!=shard["count"]:raise ValueError("shard accounting mismatch")
tmp.replace(merged)
metrics={"attempts_accounted":total,"expected":inputs["total"],"all_accounted":not missing and total==inputs["total"],
         "missing_tasks":missing,"models":models,"job":os.environ["SLURM_JOB_ID"],"generation_calls":0,"model_forward_calls":0}
atomic_json(out/"metrics.json",metrics)
atomic_json(out/"manifest.json",{"inputs_sha256":digest(root/"inputs/manifest.json"),
        "source_sha256":digest(root/"source-manifest.json"),"outputs":{str(merged):digest(merged)},"metrics":metrics})
print(json.dumps(metrics),flush=True)
if not metrics["all_accounted"]:raise SystemExit(1)
