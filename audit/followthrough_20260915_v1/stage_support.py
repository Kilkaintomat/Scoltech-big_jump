import json,os,datetime,hashlib
from pathlib import Path
import numpy as np
from onebigjump.e1.artifacts import digest,environment
ROOT=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=ROOT/"audit/followthrough_20260915_v1"
OUT=ROOT/"runs/followthrough_20260915_v1"
STATES=ROOT/"runs/segmentation_states_20260914_v1"
SEG=ROOT/"runs/segmentation_20260914_v3_recovery1"
MODELS=["deepseek","goedel","kimina"]
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def atomic(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix(p.suffix+".tmp")
 temp.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+"\n",encoding="utf-8");temp.replace(p)
def check_manifest(p):
 d=read(p)
 for name,h in d["outputs"].items():
  if digest(name)!=h:raise ValueError("output digest mismatch: "+name)
 return d
def start(stage):
 if "SLURM_JOB_ID" not in os.environ:raise RuntimeError("Slurm required")
 sm=read(HERE/(stage+"-source-manifest.json"))
 for p,h in sm["files"].items():
  if digest(p)!=h:raise ValueError("frozen source changed: "+p)
 return read(HERE/(stage+"-plan.json"))
def finish(stage,metrics,inputs=(),outputs=()):
 folder=OUT/stage;folder.mkdir(parents=True,exist_ok=True);atomic(folder/"metrics.json",metrics)
 source=HERE/(stage+"-source-manifest.json");plan=HERE/(stage+"-plan.json")
 atomic(folder/"manifest.json",{"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "config":read(plan),"source_control":read(source)["source_control"],"environment":environment(),
  "inputs":{str(p):digest(p) for p in [source,plan,*inputs]},
  "outputs":{str(p):digest(p) for p in [folder/"metrics.json",*outputs]}})
 check_manifest(folder/"manifest.json")
