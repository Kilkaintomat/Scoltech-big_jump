#!/usr/bin/env python3
"""Read-only Slurm state monitor; never cancels or resubmits jobs."""
import datetime,fcntl,hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path("/beegfs/home/denis.rakhmankin/onebigjump")
OUT=ROOT/"runs/scheduler_watch_20260914_v1"
QUEUE=ROOT/"runs/segmentation_extraction_repair_20260914_v3/queue.json"
def atomic(p,value):
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8");tmp.replace(p)
def command(args):
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=30)
    if r.returncode:raise RuntimeError(" ".join(args)+": "+r.stderr.strip())
    return r.stdout
def main():
    OUT.mkdir(exist_ok=True)
    with (OUT/"watch.lock").open("a") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        cfg=json.loads(QUEUE.read_text(encoding="utf-8"));expected=cfg.get("watch_jobs",[cfg["profile"]])
        now=datetime.datetime.now(datetime.timezone.utc);alerts=[]
        snap={"checked_at_utc":now.isoformat(),"expected_jobs":expected,"queue_sha256":hashlib.sha256(QUEUE.read_bytes()).hexdigest()}
        if (OUT/"complete.json").exists():
            previous=json.loads((OUT/"complete.json").read_text(encoding="utf-8"))
            if previous["queue_sha256"]==snap["queue_sha256"]:return
        try:
            live={x[0]:x for x in [s.split("|") for s in command(["squeue","-r","-h","-u","denis.rakhmankin","-o","%i|%T|%M|%l|%r|%j|%S"]).splitlines()] if len(x)>=7}
            hist={x[0]:x for x in [s.split("|") for s in command(["sacct","-X","-n","-P","-j",",".join(expected),"-o","JobID,JobName,State,ExitCode,Elapsed,Start,End"]).splitlines()] if len(x)>=7}
            rows=[]
            for job in expected:
                if job in live:
                    x=live[job];r={"job":job,"state":x[1],"elapsed":x[2],"time_limit":x[3],"reason":x[4],"name":x[5],"start":x[6]}
                    if x[4] in ["DependencyNeverSatisfied","InvalidAccount","InvalidQOS","JobHeldAdmin","JobHeldUser"]:alerts.append({"job":job,"kind":"blocked","reason":x[4]})
                elif job in hist:
                    x=hist[job];r={"job":job,"name":x[1],"state":x[2],"exit_code":x[3],"elapsed":x[4],"start":x[5],"end":x[6]}
                else:r={"job":job,"state":"UNKNOWN"};alerts.append({"job":job,"kind":"unobserved"})
                if any(r["state"].startswith(s) for s in ["FAILED","CANCELLED","TIMEOUT","OUT_OF_MEMORY","NODE_FAIL","BOOT_FAIL","DEADLINE","PREEMPTED"]):alerts.append({"job":job,"kind":"failure","state":r["state"],"exit_code":r.get("exit_code")})
                rows.append(r)
            snap["jobs"]=rows;snap["all_complete"]=bool(rows) and all(r["state"]=="COMPLETED" for r in rows)
            snap["progress"]={}
            for p in sorted((ROOT/"runs/segmentation_states_20260914_v1/shards").glob("*/progress.json")):
                try:snap["progress"][p.parent.name]=json.loads(p.read_text(encoding="utf-8"))
                except (ValueError,OSError) as e:alerts.append({"kind":"progress_read_error","path":str(p),"error":str(e)})
            for r in rows:
                if r["state"]!="RUNNING" or r["job"] not in cfg.get("gpu_tasks",[]):continue
                index=int(r["job"].split("_")[-1]);relevant=[v for k,v in snap["progress"].items() if int(k)%3==index]
                if relevant and max(v.get("updated_unix",0) for v in relevant)<time.time()-3600:
                    alerts.append({"job":r["job"],"kind":"stale_progress","reason":"no progress for one hour; inspect manually"})
        except Exception as e:alerts.append({"kind":"monitor_error","message":str(e)});snap["all_complete"]=False
        snap["alerts"]=alerts
        p=OUT/("check-"+now.strftime("%Y%m%dT%H%M%SZ")+".json");atomic(p,snap);atomic(OUT/"latest.json",snap)
        with (OUT/"history.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({"checked_at_utc":snap["checked_at_utc"],"snapshot":str(p),"alerts":alerts,"all_complete":snap["all_complete"]})+"\n")
        lines=["Slurm check: "+snap["checked_at_utc"],"Interval: 30 minutes.",""]
        lines += [r["job"]+" "+r["state"]+" "+r.get("reason","") for r in snap.get("jobs",[])]
        lines += ["","Alerts:"]+([json.dumps(a) for a in alerts] or ["No failed jobs or impossible dependencies detected."])
        lines += ["","Chat notifications are not connected. No automatic resubmissions."]
        (OUT/"STATUS.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
        if snap["all_complete"]:atomic(OUT/"complete.json",snap)
        print(json.dumps({"checked_at_utc":snap["checked_at_utc"],"jobs":len(snap.get("jobs",[])),"alerts":alerts,"all_complete":snap["all_complete"]}))
if __name__=="__main__":main()
