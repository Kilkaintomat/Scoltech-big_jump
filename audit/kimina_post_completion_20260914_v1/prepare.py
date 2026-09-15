"""CPU preflight: inspect every Kimina source artifact, freeze trim masks and test policy."""
import collections,csv,io,json,os,time,unittest
from pathlib import Path
import numpy as np
from data import SEG,MODELS,shard_items,load_export,identity,check_manifest
from measure_analyze import labels
from policy import clean_length
from support import *
import test_policy
def main():
    check_code();folder=OUT/"preflight";folder.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    buf=io.StringIO();result=unittest.TextTestRunner(stream=buf,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_policy))
    log=folder/"tests.log";log.write_text(buf.getvalue(),encoding="utf-8");print(buf.getvalue(),flush=True)
    if not result.wasSuccessful():raise RuntimeError("policy tests failed")
    records=[];blockers=[];excluded=collections.Counter();attempts=0;ready=0
    metadata=read(SEG/"inputs/manifest.json")
    for task in sorted(int(t) for t,s in metadata["shards"].items() if s["model"]=="kimina"):
        for item,row,path in shard_items(task):
            attempts+=1
            if not (row.get("ready_for_activation_extraction") and row["status"]=="annotated"):
                excluded["not_forward_ready"]+=1;continue
            ready+=1;e=load_export(item,row,path)
            try:star=labels(e,row)
            except ValueError as err:excluded["original_analysis: "+str(err)]+=1;continue
            try:keep,checked_star=clean_length(e,row)
            except ValueError as err:
                blockers.append({"trace_id":item["trace_id"],"reason":str(err),"artifact":str(path)});continue
            assert star==checked_star
            sample=item["sample"];L=len(e["observation_rows"])
            records.append({"trace_id":item["trace_id"],"problem_id":item["problem_id"],"role":sample["role"],
             "temperature":sample["temperature"],"task":task,"original_L":L,"keep_steps":keep,"removed_steps":L-keep,
             "star":star,"category":row["old_category"],"input_sha256":identity(item),"annotation_sha256":row["row_sha256"],
             "artifact":str(path),"artifact_sha256":digest(path)})
        print("CHECKED",task,attempts,flush=True)
    if attempts!=6672 or len({r["trace_id"] for r in records})!=len(records):raise ValueError("accounting")
    cal={r["problem_id"] for r in records if r["role"]=="calibration"};ev={r["problem_id"] for r in records if r["role"]=="evaluation"}
    if cal&ev:raise ValueError("role overlap")
    groups={}
    for role in ["calibration","evaluation"]:
        for temp in [.6,1.]:
            g=[r for r in records if r["role"]==role and r["temperature"]==temp]
            v=[r for r in g if r["star"] is None];f=[r for r in g if r["star"] is not None]
            groups[f"{role}:T{temp}"]={"accepted_traces":len(g),"verified_traces":len(v),"verified_tasks":len({r["problem_id"] for r in v}),
             "refuted_traces":len(f),"refuted_tasks":len({r["problem_id"] for r in f}),"trimmed_traces":sum(r["removed_steps"]>0 for r in v),
             "removed_steps":sum(r["removed_steps"] for r in v),"verified_steps_before":sum(r["original_L"] for r in v),
             "verified_steps_after":sum(r["keep_steps"] for r in v),"verified_median_L_before":float(np.median([r["original_L"] for r in v])),
             "verified_median_L_after":float(np.median([r["keep_steps"] for r in v])),"verified_max_L_before":max(r["original_L"] for r in v),
             "verified_max_L_after":max(r["keep_steps"] for r in v)}
    history=read(HERE/"scheduler-history.json");accounting={x["JobID"]:x for x in csv.DictReader(io.StringIO(history["accounting"]),delimiter="|")}
    estimates={}
    quality=read(REPO/"runs/segmentation_quality_20260914_v1/metrics.json")
    for model in MODELS:
        jobs=[j for j in history["jobs"] if j["model"]==model and j["kind"]=="extraction"]
        complete=[(j,accounting.get(j["job_id"])) for j in jobs if accounting.get(j["job_id"],{}).get("State")=="COMPLETED"]
        seconds=[int(accounting[job]["ElapsedRaw"]) for job in sorted({j["job_id"] for j,a in complete})];n=sum(j["metrics"]["extracted"] for j,a in complete)
        usable=quality["models"][model]["overall"]["ready_for_forward"]
        estimates[model]={"historical_completed_shards":len(complete),"historical_gpu_seconds":sum(seconds),
          "historical_extracted":n,"historical_shard_seconds_min":min(seconds) if seconds else None,
          "historical_shard_seconds_max":max(seconds) if seconds else None,"new_forward_requests":usable,
          "linear_projection_gpu_seconds":usable*sum(seconds)/n if n else None,
          "scope":"rough historical linear projection only; excludes queue, CPU analysis, different observation count and changed extraction implementation"}
    atomic(folder/"masks.json",records);atomic(folder/"blockers.json",blockers)
    metrics={"attempts":attempts,"forward_ready":ready,"accepted_for_analysis":len(records),"blockers":len(blockers),"all_safe":not blockers,
      "tests_run":result.testsRun,"tests_passed":result.wasSuccessful(),"by_role_temperature":groups,"exclusions":dict(excluded),
      "trimmed_traces":sum(r["removed_steps"]>0 for r in records),"removed_steps":sum(r["removed_steps"] for r in records),
      "refuted_traces_changed":sum(r["star"] is not None and r["removed_steps"] for r in records),"historical_runtime":estimates,
      "generation_calls":0,"model_forward_calls":0,"elapsed_seconds":time.monotonic()-started}
    finish(folder,metrics,[HERE/"core-source-manifest.json",HERE/"scheduler-history.json",SEG/"inputs/manifest.json",
           REPO/"runs/segmentation_quality_20260914_v1/manifest.json"],[folder/"masks.json",folder/"blockers.json",log])
    if blockers:raise RuntimeError("ambiguous cleanup cases; automatic processing blocked")
    print("PREFLIGHT READY",json.dumps(metrics),flush=True)
if __name__=="__main__":main()
