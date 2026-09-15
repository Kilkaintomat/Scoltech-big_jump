"""Reproduce the new discrepancy in fresh sessions and record node file-table counters."""
from pathlib import Path
import resource,os
from onebigjump.e1.artifacts import read_json,finish,write_once,verify_manifest,digest
from onebigjump.e1.stages import rows
from onebigjump.e1.verification import verify_one
from onebigjump.lean import LeanREPL,discover
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
root=base/"runs/lean_reverification_20260912/goedel"
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
protocol=root/"main/protocol.json";settings=read_json(protocol)["lean"]
problems_path=root/"inputs/problems.json";problems={p["problem_id"]:p for p in read_json(problems_path)}
manifest=root/"main/generation/shard-002-of-008/manifest.json";verify_manifest(manifest)
sample=next(r for r in rows(manifest.parent/"samples.jsonl") if r["trace_id"]=="main:mathd_algebra_31:T0.6:a04")
def files():
 return {"file_nr":Path("/proc/sys/fs/file-nr").read_text().strip(),
         "file_max":Path("/proc/sys/fs/file-max").read_text().strip(),
         "process_nofile":list(resource.getrlimit(resource.RLIMIT_NOFILE))}
results=[];counters=[{"phase":"before","values":files()}]
for index in range(2):
 with LeanREPL(discover(settings["workspace"]),imports="import Mathlib\nimport Aesop",
               startup_timeout_s=settings["startup_timeout_s"]) as repl:
  counters.append({"phase":"started-"+str(index),"values":files()})
  r=verify_one(repl,sample,problems[sample["problem_id"]],settings);results.append(r)
  counters.append({"phase":"verified-"+str(index),"values":files()})
 counters.append({"phase":"closed-"+str(index),"values":files()})
 print(index,r["category"],r["whole_proof_ok"],r["replay_ok"],flush=True)
m={"source_sha256":digest(source),"trace_id":sample["trace_id"],"fresh_session_results":[
 {"category":r["category"],"whole":r["whole_proof_ok"],"replay":r["replay_ok"],
  "unexplained_disagreement":r["unexplained_disagreement"],
  "messages":[s.get("message","") for s in r["steps"] if s.get("message")]} for r in results],
 "node_file_counters":counters,"original_rows_preserved":True}
folder=base/"audit/status_2026_09_13/fresh-replay"
a=write_once(folder/"metrics.json",m);b=write_once(folder/"results-server-only.json",results)
finish(folder,stage="fresh-session-discrepancy-diagnosis",context={"source":digest(source)},
 inputs=[Path(__file__),source,protocol,problems_path,manifest],outputs=[a,b],metrics=m)
