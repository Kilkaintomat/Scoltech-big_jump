import gzip,json,os
from pathlib import Path
import pandas as pd
from data import REPO,RUN as STATES,MODELS,read,atomic,digest,environment,check_manifest
HERE=REPO/"audit/segmentation_quality_20260914_v1"
OUT=REPO/"runs/segmentation_quality_20260914_v1"
cases=[];counts={};inputs=[HERE/"enrich.py"]
for model in MODELS:
    check_manifest(OUT/model/"manifest.json");inputs.append(OUT/model/"manifest.json")
    f=pd.read_csv(OUT/model/"traces.csv")
    counts[model]={}
    for key,mask in [("all_forward",f.forward_ready),("evaluation_T0.6",f.forward_ready&(f.role=="evaluation")&(f.temperature==.6))]:
        g=f[mask]
        counts[model][key]={c:{"traces":int((g[c]>0).sum()),"points":int(g[c].sum())}
            for c in ["post_completion","post_recovery_observed","rejected","merged","n_calc"]}
    for c in read(OUT/model/"review-cases.json"):
        path=Path(c["artifact_path"])
        if digest(path)!=c["artifact_sha256"]:raise ValueError("case artifact changed")
        with gzip.open(path,"rt",encoding="utf-8") as stream:b=json.load(stream)
        e=b["detail"]["export"];obs=e["observation_rows"]
        switches=[i for i,o in enumerate(obs) if any(p["source_transition"].get("branch_switch") for p in o["source_points"])]
        post=[i for i,o in enumerate(obs) if o["trace_label"]=="post_completion"]
        chosen=set(switches[:2]+post[:2]+([post[0]-1] if post and post[0]>0 else []))
        excerpts=[]
        for i in sorted(chosen):
            o=obs[i];a=min(p["span_start"] for p in o["source_points"])-2;z=max(p["span_end"] for p in o["source_points"])-2
            excerpts.append({"i_1based":i+1,"label":o["trace_label"],"text":c["source_body"][a:z][:600],
              "transitions":[p["source_transition"] for p in o["source_points"]]})
        cases.append({"model":model,"bucket":c["bucket"],"trace_id":c["trace_id"],"L":c["L"],"post_completion_observations":len(post),
           "branch_switch_observations":len(switches),"extra_excerpts":excerpts,
           "boundary_information":{k:v for k,v in e.items() if "reject" in k},
           "export_keys":list(e)})
atomic(OUT/"review-enrichment.json",{"counts":counts,"cases":cases})
atomic(OUT/"enrichment-manifest.json",{"config":{"scope":"bounded structural review, no activation values"},"source_control":read(STATES/"source-manifest.json")["source_control"],
 "environment":environment(),"inputs":{str(p):digest(p) for p in inputs},"outputs":{str(OUT/"review-enrichment.json"):digest(OUT/"review-enrichment.json")}})
print("ENRICHED",len(cases),flush=True)
