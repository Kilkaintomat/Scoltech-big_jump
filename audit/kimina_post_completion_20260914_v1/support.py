import json,os
from pathlib import Path
from data import REPO,RUN as STATES,read,atomic,digest,environment,check_source
HERE=REPO/"audit/kimina_post_completion_20260914_v1"
OUT=REPO/"runs/kimina_post_completion_20260914_v1"
def check_code(name="core-source-manifest.json"):
    check_source();m=read(HERE/name)
    for path,h in m["files"].items():
        if digest(path)!=h:raise ValueError("changed frozen file: "+path)
def finish(folder,metrics,inputs,outputs):
    folder.mkdir(parents=True,exist_ok=True);atomic(folder/"metrics.json",metrics)
    config=read(HERE/"plan.json")
    paths=[HERE/"plan.json",*inputs]
    atomic(folder/"manifest.json",{"config":config,
      "source_control":read(STATES/"source-manifest.json")["source_control"],
      "environment":environment(),"inputs":{str(p):digest(p) for p in paths},
      "outputs":{str(p):digest(p) for p in [folder/"metrics.json",*outputs]}})
