"""CPU preflight on exported inputs plus architecture regression tests, through Slurm."""
import collections,io,json,os,platform,time,unittest
from pathlib import Path
from data import *
from repair_support import HERE,OUT,check_repair,backend_comparison
from test_repair import CompatibilityTests
def main():
    if "SLURM_JOB_ID" not in os.environ:raise RuntimeError("Slurm required")
    out=OUT/"preflight";out.mkdir(exist_ok=False);repair=check_repair();check_source()
    buf=io.StringIO();r=unittest.TextTestRunner(stream=buf,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompatibilityTests))
    (out/"tests.txt").write_text(buf.getvalue(),encoding="utf-8");print(buf.getvalue(),flush=True)
    if not r.wasSuccessful():raise RuntimeError("regression tests failed")
    meta=read(SEG/"inputs/manifest.json");counts=collections.Counter();fields=collections.Counter();summaries=collections.defaultdict(list);input_hashes={}
    annotations={};quality=REPO/"runs/segmentation_quality_20260914_v1"
    for task,s in meta["shards"].items():
        p=SEG/"inputs"/s["file"]
        if digest(p)!=s["sha256"]:raise ValueError("input digest mismatch")
        input_hashes[str(p)]=s["sha256"]
        with p.open(encoding="utf-8") as f:items=[json.loads(line) for line in f]
        if len(items)!=s["count"]:raise ValueError("input count mismatch")
        folder=SEG/"shards"/("%03d"%int(task));m=check_manifest(folder/"manifest.json")
        anns={a["trace_id"]:a for a in checked_rows(folder/"observations.jsonl",m["context"])}
        for item in items:
            sample=item["sample"];model=read(RUN/"plan.json")["models"][task];counts[model]+=1
            fields["present" if "generation_token_logprobs" in sample else "absent"]+=1
            if "generation_token_logprobs" in sample:
                import numpy as np
                backend_comparison(sample,np.zeros(len(sample["completion_token_ids"])))
            if not sample["prompt_token_ids"] or not sample["completion_token_ids"]:raise ValueError("empty model input")
            a=anns[item["trace_id"]]
            if a.get("ready_for_activation_extraction") and a["status"]=="annotated":
                summaries[model].append({"trace_id":item["trace_id"],"task":int(task),
                 "tokens":len(sample["prompt_token_ids"])+len(sample["completion_token_ids"])})
    metrics={"passed":True,"unit_tests":r.testsRun,"attempts":dict(counts),"generation_logprob_field":dict(fields),
     "ready_by_model":{m:{"traces":len(rows),"max_tokens":max(x["tokens"] for x in rows),"total_tokens":sum(x["tokens"] for x in rows)} for m,rows in summaries.items()},
     "generation_calls":0,"cpu_forward_tests":True,"real_model_gpu_check_required":True}
    atomic(out/"workload.json",summaries);atomic(out/"metrics.json",metrics)
    atomic(out/"manifest.json",{"config":read(HERE/"config.json"),"source_control":read(repair)["source_control"],
       "environment":environment(),"inputs":{str(repair):digest(repair),**input_hashes},
       "outputs":{str(p):digest(p) for p in [out/"metrics.json",out/"tests.txt",out/"workload.json"]}})
    print(json.dumps(metrics),flush=True)
if __name__=="__main__":main()
