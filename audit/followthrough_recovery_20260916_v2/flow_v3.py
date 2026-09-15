#!/usr/bin/env python3
"""Slurm management only: monitor fixed stages, submit dependencies and resume resource interruptions."""
import datetime,fcntl,json,os,subprocess,time,hashlib
from pathlib import Path
ROOT=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=ROOT/"audit/followthrough_20260915_v1"
OUT=ROOT/"runs/followthrough_20260915_v1"
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def atomic(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+".tmp");tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");tmp.replace(p)
def command(args):
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=45)
 if r.returncode:raise RuntimeError(" ".join(args)+": "+r.stderr[-1200:])
 return r.stdout
def parse_rows(text,n):return [r for r in (line.split("|") for line in text.splitlines()) if len(r)>=n]
def indices(spec):return spec.get("indices",[None])
def expected(attempt):
 return [(str(attempt["id"])+("_"+str(i) if i is not None else ""),i) for i in attempt.get("indices",[None])]
def status_of(spec,attempts,live,hist):
 current={}
 for attempt in attempts:
  for job,index in expected(attempt):
   row=live.get(job) or hist.get(job)
   current[index]={"job":job,"index":index,"state":row[1].split()[0] if row else "UNKNOWN","reason":row[4] if job in live else "", "accounting":row}
 if not current:return {"state":"NOT_SUBMITTED","members":[]}
 members=[current.get(i,{"index":i,"state":"UNKNOWN"}) for i in indices(spec)]
 if all(r["state"]=="COMPLETED" for r in members):state="COMPLETED"
 elif any(r["state"] in ["RUNNING","COMPLETING","PENDING","CONFIGURING","REQUEUED"] for r in members):state="ACTIVE"
 else:state="STOPPED"
 return {"state":state,"members":members}
def main():
 OUT.mkdir(exist_ok=True);control=OUT/"flow";control.mkdir(exist_ok=True)
 with (control/"controller.lock").open("a") as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  for name,expected_hash in read(Path("/beegfs/home/denis.rakhmankin/onebigjump/audit/followthrough_recovery_20260916_v2/source-manifest.json"))["files"].items():
   if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=expected_hash:raise RuntimeError("Frozen flow source changed: "+name)
  plan=read(Path("/beegfs/home/denis.rakhmankin/onebigjump/audit/followthrough_recovery_20260916_v2/flow-plan-v3.json"));state_path=control/"jobs.json"
  state=read(state_path) if state_path.exists() else {"stages":plan["initial_jobs"],"events":[]}
  ids=[str(a["id"]) for aa in state["stages"].values() for a in aa]
  live={r[0]:r for r in parse_rows(command(["squeue","-r","-h","-u","denis.rakhmankin","-o","%i|%T|%M|%l|%r|%j|%P"]),7)}
  hist={r[0]:r for r in parse_rows(command(["sacct","-X","-n","-P","-j",",".join(ids),"-o","JobID,State,ExitCode,Elapsed,Start,End"]),6)}
  statuses={name:status_of(spec,state["stages"].get(name,[]),live,hist) for name,spec in plan["stages"].items()}
  gpu_active=len({r[0].split("_")[0] for r in live.values() if "gpu" in r[6]});alerts=[]
  def submit(name,spec,retry_indices=None):
   nonlocal gpu_active
   jobname="ft15-"+name.replace("_","-")
   orphan={r[0].split("_")[0] for r in live.values() if r[5]==jobname}
   if orphan:raise RuntimeError("Unregistered live stage exists: "+name)
   args=["sbatch","--parsable","--job-name="+jobname,"--output="+str(OUT/(name+"-%A_%a.log"))]
   inds=retry_indices if retry_indices is not None else spec.get("indices")
   if inds is not None:args+=["--array="+",".join(map(str,inds))+"%"+str(spec.get("concurrency",2))]
   args+=[str(HERE/spec["script"])]
   job=command(args).strip().split(";")[0];assert job.isdigit()
   record={"id":job,"script":str(HERE/spec["script"]),"recovery_source":"/beegfs/home/denis.rakhmankin/onebigjump/audit/followthrough_recovery_20260916_v2/source-manifest.json","submitted_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
   if inds is not None:record["indices"]=inds
   state["stages"].setdefault(name,[]).append(record)
   state["events"].append({"stage":name,"job":job,"retry":retry_indices is not None,"at":record["submitted_utc"]});atomic(state_path,state)
   statuses[name]={"state":"SUBMITTED","members":[{"job":j,"index":i,"state":"PENDING"} for j,i in expected(record)]}
   if spec.get("gpu"):gpu_active+=1
  for name in plan["submission_order"]:
   spec=plan["stages"][name];st=statuses[name];attempts=state["stages"].get(name,[])
   if st["state"]=="STOPPED":
    failed=[r for r in st["members"] if r["state"]!="COMPLETED"]
    can_retry=failed and all(r["state"] in ["TIMEOUT","NODE_FAIL","PREEMPTED","BOOT_FAIL"] for r in failed) and len(attempts)<3 and spec.get("resumable",False)
    if can_retry and (not spec.get("gpu") or gpu_active<2):
     if spec.get("indices") is None:submit(name,spec)
     else:submit(name,spec,[r["index"] for r in failed])
    else:alerts.append({"stage":name,"kind":"stage_stopped","members":failed,"automatic_retry":False})
    continue
   if st["state"]!="NOT_SUBMITTED":continue
   if not all(statuses[d]["state"]=="COMPLETED" for d in spec.get("requires",[])):continue
   if spec.get("gate"):
    gp=OUT/spec["gate"]
    if not gp.exists():alerts.append({"stage":name,"kind":"gate_missing"});continue
    if not read(gp).get(spec["gate_field"],False):alerts.append({"stage":name,"kind":"gate_not_passed","gate":str(gp)});continue
   if spec.get("gpu") and gpu_active>=2:continue
   submit(name,spec)
  for name,st in statuses.items():
   for r in st["members"]:
    if r.get("reason") in ["DependencyNeverSatisfied","JobHeldAdmin","InvalidAccount","InvalidQOS"]:alerts.append({"stage":name,"kind":"scheduler_block","member":r})
  snapshot={"checked_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"stages":statuses,"alerts":alerts,"gpu_active_or_pending":gpu_active,
   "policy":"Fixed dependency chain; only resource interruptions automatically resumed at most twice. No cancellations, no statistical tuning, no chat notifications."}
  atomic(control/"latest.json",snapshot);atomic(state_path,state)
  with (control/"history.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(snapshot)+"\n")
  print(json.dumps({"checked_utc":snapshot["checked_utc"],"alerts":alerts,"states":{k:v["state"] for k,v in statuses.items()}}))
if __name__=="__main__":main()
