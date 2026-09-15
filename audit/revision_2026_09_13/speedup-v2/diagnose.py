from pathlib import Path
import json,datetime,collections
from onebigjump.e1.stages import rows
from onebigjump.e1.artifacts import write_once,finish,digest
root=Path("runs/lean_reverification_20260913_local")
out=Path("audit/revision_2026_09_13/speedup-v2/diagnostic")
summary=[];bad=[];inputs=[]
for model in ("deepseek","goedel","kimina"):
 for p in sorted((root/model/"main/verification").glob("shard-*/manifest.json")):
  rs=rows(p.parent/"labels.jsonl");inputs.append(p)
  summary.append({"model":model,"shard":p.parent.name,"attempts":len(rs),"elapsed_s":sum(r["elapsed_s"] for r in rs),"categories":dict(collections.Counter(r["category"] for r in rs))})
  for r in rs:
   if r["unexplained_disagreement"]:bad.append({"model":model,"shard":p.parent.name,"row":r})
metrics={"created_utc":datetime.datetime.utcnow().isoformat()+"Z","shards":summary,"bad_count":len(bad),"bad":[{"model":b["model"],"shard":b["shard"],"trace_id":b["row"]["trace_id"],"whole":b["row"]["whole_proof_ok"],"replay":b["row"]["replay_ok"],"body":b["row"].get("replay_body"),"steps":b["row"]["steps"]} for b in bad]}
a=write_once(out/"metrics.json",metrics);b=write_once(out/"bad-full.json",bad)
source=Path("audit/revision_2026_09_13/snapshots/statistical-fitness-v1/source-manifest.json")
finish(out,stage="saved-answer-diagnostic",context={"source":digest(source)},inputs=[source,Path(__file__),*inputs],outputs=[a,b],metrics={"bad_count":len(bad),"completed_shards":len(summary)})
print(json.dumps(metrics,ensure_ascii=False),flush=True)
