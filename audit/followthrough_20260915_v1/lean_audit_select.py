import collections,gzip
import numpy as np
from stage_support import *
def bucket(label,ann):
 cat=label["category"]
 if cat=="generation_truncation":return "truncated"
 if cat=="verified":return "verified"
 if cat=="terminal_unsolved_goals":return "terminal_unsolved"
 if cat=="localized_tactic_failure":
  if not ann.get("p2_eligible"):return "localization_unavailable"
  return "localized_first" if ann.get("fine_star")==0 else "localized_later"
 if label.get("resource_limited") or any(x in cat for x in ["timeout","infrastructure","context_statement"]):return "resource_compatibility"
 return "format_other"
def main():
 plan=start("lean_audit");meta=read(SEG/"inputs/manifest.json");out=OUT/"lean_audit";out.mkdir(parents=True,exist_ok=True);inputs=[SEG/"inputs/manifest.json"];summary={};outputs=[]
 for model in MODELS:
  base=ROOT/"runs/lean_reverification_20260913_local"/model
  lp=base/"main/verification/labels.jsonl";labels={}
  with lp.open(encoding="utf-8") as f:
   for line in f:
    r=json.loads(line);labels[r["trace_id"]]=r
  inputs.append(lp);problems={r["problem_id"]:r for r in read(base/"inputs/problems.json")};inputs.append(base/"inputs/problems.json")
  annotations={};items={};pools=collections.defaultdict(list)
  for task,info in meta["shards"].items():
   if info["model"]!=model:continue
   src=SEG/"inputs"/info["file"];assert digest(src)==info["sha256"];inputs.append(src)
   shard=SEG/"shards"/("%03d"%int(task));check_manifest(shard/"manifest.json");inputs.append(shard/"manifest.json")
   with (shard/"observations.jsonl").open(encoding="utf-8") as f:
    for line in f:
     ann=json.loads(line);ann["artifact_absolute"]=str(shard/ann["artifact"]);annotations[ann["trace_id"]]=ann
   with src.open(encoding="utf-8") as f:
    for line in f:
     item=json.loads(line);items[item["trace_id"]]=item
  # Read only localized records to define early/later strata; never look at activations.
  for tid,item in items.items():
   ann=annotations[tid]
   if ann.get("p2_eligible"):
    p=Path(ann["artifact_absolute"]);assert digest(p)==ann["artifact_sha256"]
    with gzip.open(p,"rt",encoding="utf-8") as f:blob=json.load(f)
    obs=blob["detail"]["export"]["observation_rows"];at=[i for i,o in enumerate(obs) if o["trace_label"]=="at"]
    assert len(at)==1;ann["fine_star"]=at[0]
   pools[bucket(labels[tid],ann)].append(tid)
  selected=[];counts={}
  for b in plan["strata"]:
   ids=sorted(pools[b]);rng=np.random.default_rng(int(hashlib.sha256((str(plan["seed"])+model+b).encode()).hexdigest()[:16],16))
   chosen=rng.choice(ids,size=min(plan["samples_per_stratum_per_model"],len(ids)),replace=False).tolist()
   counts[b]={"population":len(ids),"selected":len(chosen)}
   for tid in chosen:
    it=items[tid];selected.append({"model":model,"stratum":b,"stratum_size":len(ids),"stratum_sample_size":len(chosen),
     "selection_probability":len(chosen)/len(ids),"item":it,"old_label":labels[tid],"old_annotation":annotations[tid],"problem":problems[it["problem_id"]]})
  p=out/(model+"-selected.json");atomic(p,selected);outputs.append(p)
  summary[model]={"strata":counts,"selected":len(selected),"tasks":len({x["item"]["problem_id"] for x in selected})}
 finish("lean_audit",{"selection":summary,"selection_complete":True,"score_blind_selection":True},inputs,outputs)
 print("AUDIT SAMPLE FROZEN",json.dumps(clean(summary)),flush=True)
if __name__=="__main__":main()
