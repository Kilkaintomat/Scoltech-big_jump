import json,datetime,hashlib,collections,statistics,os
from pathlib import Path
from artifact_bridge import verify_any,finish_artifact
from stage_support import read
R=Path("/beegfs/home/denis.rakhmankin/onebigjump");F=R/"runs/followthrough_20260915_v1";O=R/"runs/status_check_20260916_0205"
def rows(p):
 if not p.exists():return []
 data=p.read_bytes().splitlines(keepends=True)
 if data and not data[-1].endswith(b"\n"):data=data[:-1]
 return [json.loads(line) for line in data]
m={"checked_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"p2":{}}
for model in ["deepseek","goedel"]:
 allrows=[];parts={}
 for role in ["pilot","evaluation"]:
  rr=rows(F/"p2_pipeline"/model/role/"generation/samples.jsonl");parts[role]=len(rr);allrows+=rr
 assert len({x["trace_id"] for x in allrows})==len(allrows)
 current=[x for x in allrows if x.get("slurm_job_id")=="8468361"]
 ref=current if len(current)>=16 else allrows
 per=[x["batch_elapsed_s"]/x["batch_size"] for x in ref]
 requested=read(F/"p2_pipeline"/(model+"-requests.json"));expected=len(requested)
 for x in allrows:
  assert len(x["completion_token_ids"])==len(x["generation_token_logprobs"])
 quant=statistics.quantiles(per,n=4) if len(per)>4 else [0,0,0]
 m["p2"][model]={"saved":parts,"expected":expected,"remaining":expected-len(allrows),"current_job_saved":len(current),"rate_reference":"current generation" if current else "previous technical pilot; may differ on evaluation", "median_seconds_per_attempt":statistics.median(per),"quartiles_seconds_per_attempt":quant,"reference_seconds_per_attempt_mean":statistics.mean(per),"estimated_remaining_hours_at_reference_mean":(expected-len(allrows))*statistics.mean(per)/3600,"alignment_exclusions":sum(not x.get("original_token_alignment",{"passed":True})["passed"] for x in allrows),"finish_reasons":dict(collections.Counter(x["finish_reason"] for x in allrows)),"duplicate_trace_ids":0,"token_logprob_lengths_consistent":True}
verify_any(F/"p5_analysis/manifest.json")
metrics=read(F/"p5_analysis/metrics.json")
evalm=read(F/"p5_evaluation/main/verification/manifest.json")["metrics"]
assert evalm["attempts"]==1000 and sum(evalm["categories"].values())==1000
assert metrics["calibration_evaluation_task_overlap"]==0
m["p5"]={"manifest_integrity_passed":True,"evaluation":evalm,"calibration_evaluation_overlap":0,"by_temperature":{}}
for temp,v in metrics["temperatures"].items():
 c=v["length_prediction"]["evaluation_counts"]
 assert sum(x[1] for x in c.values())==500
 m["p5"]["by_temperature"][temp]={"evaluation_verified":sum(x[0] for x in c.values()),"brier_improvement":v["length_prediction"]["brier_improvement"],"brier_improvement_ci975":v["length_prediction"]["brier_improvement_ci975"],"jump_localization":v["independent_whitening"]["localization"]}
mp=O/"metrics.json";mp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8")
finish_artifact(O,stage="live-status-integrity-and-runtime-estimate",context={"job":os.environ["SLURM_JOB_ID"]},inputs=[Path(__file__),F/"p5_analysis/manifest.json"],outputs=[mp],metrics={"p5_integrity_passed":True,"p2_saved":sum(sum(x["saved"].values()) for x in m["p2"].values())})
print(json.dumps(m,ensure_ascii=False,indent=2),flush=True)
