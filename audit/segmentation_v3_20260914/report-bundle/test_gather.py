from pathlib import Path
import os,json,subprocess,sys
from campaign_worker import read,atomic_json
O=Path(__file__).parent;T=O/"batch-pilot";m=read(T/"inputs/manifest.json")
for k,s in m["shards"].items():
    row=json.loads((T/"inputs"/s["file"]).read_text(encoding="utf-8").splitlines()[0])
    s["model"]=row["model"]
atomic_json(T/"inputs/manifest.json",m)
subprocess.run([sys.executable,str(O/"gather.py"),"--root",str(T)],check=True)
metrics=read(T/"summary/metrics.json")
assert metrics["all_accounted"] and metrics["attempts_accounted"]==5
atomic_json(O/"gather-gate.json",{"passed":True,"job":os.environ["SLURM_JOB_ID"],"metrics":metrics})
