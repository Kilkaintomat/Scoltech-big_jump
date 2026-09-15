from pathlib import Path
import json,time,os
from onebigjump.lean import LeanREPL,discover
from segmenter_fast import SegmenterFast
from segmenter import errors
O=Path(__file__).parent
saved=json.loads((O/'sample.json').read_text(encoding='utf-8'))
dest=O/'profile';dest.mkdir(exist_ok=True)
results=[]
for idx in [5,13,15,17]:
 c=saved[idx]
 for mode in ["plain","selected"]:
  row={"index":idx,"model":c["model"],"trace_id":c["trace_id"],"mode":mode};start=time.monotonic()
  try:
   with LeanREPL(discover(),imports="import Mathlib\nimport Aesop",startup_attempts=1,default_timeout_s=180,drain_timeout_s=5) as repl:
    s=SegmenterFast(repl,timeout_s=180)
    tick=time.monotonic()
    if mode=="plain":
     r=repl._exchange({"cmd":c["replay"]["header"]+c["body"],"env":repl._base_env},timeout_s=180)
     row.update(elaboration_ok=not errors(r) and not r.get("sorries"),profile=r.get("observerProfile"))
    else:
     r=s.inspect(c["replay"]["header"],c["body"],c["trace_id"])
     row.update(elaboration_ok=r["whole_elaboration_ok"],profile=r.get("observer_profile"),n_points=r["n_blocks"],n_events=len(r["native_events"]))
    row["command_wall_s"]=time.monotonic()-tick
    (dest/(str(idx)+"-"+mode+".json")).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
  except Exception as e:row["exception"]=repr(e)
  row["total_s"]=time.monotonic()-start;results.append(row)
  (dest/'results.json').write_text(json.dumps({"job":os.environ["SLURM_JOB_ID"],"results":results},indent=2),encoding="utf-8")
  print(json.dumps(row),flush=True)
