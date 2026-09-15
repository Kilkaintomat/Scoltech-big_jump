"""Additive compiler audit: immutable model outputs and primary labels are never edited."""
from pathlib import Path
from collections import Counter
import json, os, re, signal, subprocess, time
from onebigjump.e1.artifacts import read_json, write_once, finish, digest
from onebigjump.e1.verification import ALLOWED_AXIOMS, trusted_prefix
from onebigjump.e1.spans import mask_comments
from onebigjump.lean import discover

base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
campaign=base/"runs/lean_reverification_20260913_local"
out=base/"audit/revision_2026_09_13"/(os.environ["SLURM_JOB_ID"]+"-compiler-review")
out.mkdir(parents=True,exist_ok=False)
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
settings=read_json(campaign/"kimina/main/protocol.json")["lean"]
env=discover(settings["workspace"]).require()
assert os.stat(os.environ["ELAN_HOME"]).st_dev==os.stat(os.environ["E1_LOCAL_ELAN"]).st_dev
inputs=[source,Path(__file__),Path(__file__).with_suffix(".json"),
        Path(os.environ["E1_ELAN_RUNTIME_MANIFEST"]),Path(os.environ["E1_REPL_RUNTIME_MANIFEST"])]
outputs=[];results=[];inventory={}
def save_text(path,text):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(text,encoding="utf-8");outputs.append(path)
 return path
def run_source(name,source_text):
 path=save_text(out/"lean"/(name+".lean"),source_text)
 local=env.project/(name+".lean")
 local.write_text(source_text,encoding="utf-8")
 start=time.monotonic();timed_out=False
 proc=subprocess.Popen([env.lake,"env","lean",str(local)],cwd=env.project,env=env.env_vars(),
   stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,text=True,encoding="utf-8")
 try:
  try: stdout,stderr=proc.communicate(timeout=settings["whole_timeout_s"])
  except subprocess.TimeoutExpired:
   timed_out=True;os.killpg(proc.pid,signal.SIGKILL);stdout,stderr=proc.communicate(timeout=15)
 finally:
  try:os.killpg(proc.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  proc.wait(timeout=15)
  local.unlink()
 combined=stdout+"\n"+stderr
 log=save_text(out/"logs"/(name+".log"),combined)
 axioms=[]
 for match in re.finditer(r"depends on axioms:\s*\[(.*?)\]",combined,re.S):
  axioms += [x.strip() for x in match.group(1).split(",") if x.strip()]
 infrastructure=any(x in combined.lower() for x in ["remote i/o error","input/output error","stale file handle","too many open files"])
 return {"name":name,"source":str(path.relative_to(out)),"log":str(log.relative_to(out)),
   "returncode":proc.returncode,"timeout":timed_out,"infrastructure_error":infrastructure,
   "elapsed_s":time.monotonic()-start,"axioms":axioms,"success":proc.returncode==0 and not timed_out and not infrastructure}
def annotate(label):
 body=label.get("body","")
 live=mask_comments(body,mask_strings=True)
 literal=bool(re.search(r"\b(?:sorry|admit|sorryAx)\b",re.sub(r"«[^»]*»","",live)))
 unexpected=[a for a in label.get("axioms",[]) if a not in ALLOWED_AXIOMS]
 native=[a for a in unexpected if re.search(r"\._native\.native_decide\.ax(?:_\d+)?$",a)]
 return {"literal_hole":literal,"unexpected_axioms":unexpected,"native_aux_axioms":native,
   "native_policy_only":label.get("whole_proof_ok") is True and label.get("replay_ok") is True
     and not literal and bool(native) and set(unexpected)==set(native)}
# Keep the exact installed primary source explaining compiler-generated native axioms.
native_src=next(Path(os.environ["ELAN_HOME"]).glob("toolchains/*/src/lean/Lean/Meta/Native.lean"))
inputs.append(native_src)
save_text(out/"evidence/Lean_Meta_Native.lean",native_src.read_text(encoding="utf-8"))
native_done=False
for model in ["kimina","deepseek","goedel"]:
 root=campaign/model
 packet=root/"main/collection-gate/review-samples.json"
 problems_path=root/"inputs/problems.json";protocol=root/"main/protocol.json"
 labels_path=root/"pilot/verification/labels.jsonl"
 inputs += [packet,problems_path,protocol,root/"pilot/verification/manifest.json"]
 problems={x["problem_id"]:x for x in read_json(problems_path)}
 labels=[json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines() if line]
 audit=[{"trace_id":v["trace_id"],"category":v["category"],**annotate(v)} for v in labels]
 inventory[model]={"n":len(labels),"categories":dict(Counter(v["category"] for v in labels)),
  "native_policy_only":sum(v["native_policy_only"] for v in audit),
  "literal_holes":sum(v["literal_hole"] for v in audit),"records":audit}
 for idx,item in enumerate(read_json(packet)):
  v=item["verification"];sample=item["sample"];p=problems[v["problem_id"]]
  cat=v["category"];key=model+"_"+str(idx).zfill(2)
  header=trusted_prefix(p,settings["max_heartbeats"])+"\n"+p["statement"]
  checks=[]
  record={"model":model,"packet_index":idx,"trace_id":v["trace_id"],"category":cat,
          "t_star_zero_based":v.get("t_star"),"whole_proof_ok":v.get("whole_proof_ok"),
          "replay_ok":v.get("replay_ok"),"original_axioms":v.get("axioms",[]),
          "source_error":v.get("error"),"finish_reason":sample["finish_reason"],**annotate(v)}
  # Trusted statement and parsed body, rather than the generated preamble.
  if "body" in v:
   checks.append(run_source(key+"_full",header+v["body"]+"\n#print axioms "+p["problem_id"]+"\n"))
   if v.get("t_star") is not None and cat in ["localized_tactic_failure","terminal_unsolved_goals","timeout_resource"]:
    t=v["t_star"]
    for count,tag in [(t,"before"),(t+1,"through")]:
     prefix="\n".join("  "+s["tactic"].replace("\n","\n  ") for s in v["steps"][:count])
     checks.append(run_source(key+"_"+tag,header+"\n"+prefix+"\n  all_goals sorry\n"))
   if record["native_policy_only"] and not native_done:
    native_done=True
    checks.append(run_source(key+"_diagnostic_decide",header+"\n  decide\n#print axioms "+p["problem_id"]+"\n"))
    checks.append(run_source(key+"_diagnostic_false",trusted_prefix(p)+"\nexample : (1 : Nat) = 2 := by\n  native_decide\n"))
  else:
   # Preserve raw text for exclusions so a reviewer can independently assess statement/preamble.
   save_text(out/"excluded"/(key+".txt"),sample["completion"])
   save_text(out/"excluded"/(key+"_trusted.lean"),header)
  t=v.get("t_star");steps=v.get("steps",[])
  record["absorbing_ok"]=t is None or all(s["valid"]==(i<t) and (i<=t or s["status"]=="unreached") for i,s in enumerate(steps))
  record["checks"]=checks
  record["status"]="review_required"
  if checks:
   full=checks[0]
   if full["infrastructure_error"] or full["timeout"]:record["status"]="compiler_inconclusive"
   elif cat=="verified" and full["success"] and set(full["axioms"])<=ALLOWED_AXIOMS:record["status"]="verified_reproduced"
   elif record["native_policy_only"] and full["success"]:record["status"]="native_policy_exclusion_reproduced"
   elif cat=="parse_error" and not full["success"]:record["status"]="compiler_rejection_reproduced"
   elif t is not None and len(checks)>=3 and checks[1]["success"] and not checks[2]["success"] and not checks[2]["timeout"] and not checks[2]["infrastructure_error"]:
    record["status"]="first_rejection_reproduced"
   elif cat=="timeout_resource":record["status"]="resource_review_required"
  else:record["status"]="source_exclusion_needs_text_review"
  results.append(record)
  print(key,v["trace_id"],record["status"],flush=True)
metrics={"reviewer":"automated independent standalone Lean compiler plus assistant source inspection; not human signoff",
 "scope":"fixed 36 gate-selected pilot examples; not random; not all main traces",
 "main_labels_edited":False,"axiom_policy_changed":False,
 "toolchain":env.toolchain,"budget":settings,
 "records":len(results),"statuses":dict(Counter(r["status"] for r in results)),
 "absorbing_violations":sum(not r["absorbing_ok"] for r in results),
 "pilot_inventory":{m:{k:v for k,v in d.items() if k!="records"} for m,d in inventory.items()},
 "compilations":sum(len(r["checks"]) for r in results),
 "infrastructure_errors":sum(c["infrastructure_error"] for r in results for c in r["checks"]),
 "compiler_timeouts":sum(c["timeout"] for r in results for c in r["checks"]),
 "scientific_release":"hold pending review of native computation policy and full main/controls"}
outputs += [write_once(out/"metrics.json",metrics),write_once(out/"results.json",results),write_once(out/"pilot-axiom-inventory.json",inventory)]
finish(out,stage="independent-pilot-compiler-review",context={"source_sha256":digest(source),"protocol":"additive-audit-v1"},
 inputs=inputs,outputs=outputs,metrics=metrics)
print("COMPILER_REVIEW_SAVED",out,flush=True)
