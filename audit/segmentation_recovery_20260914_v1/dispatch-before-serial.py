"""File/Slurm management only: bounded retries and release of a guarded summary."""
import datetime,fcntl,json,subprocess,time
from pathlib import Path
REPO=Path("/beegfs/home/denis.rakhmankin/onebigjump")
RUN=REPO/"runs/segmentation_20260914_v3_recovery1"
AUDIT=REPO/"audit/segmentation_recovery_20260914_v1"
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def write(p,x):
    t=p.with_name(p.name+".tmp");t.write_text(json.dumps(x,indent=2,sort_keys=True),encoding="utf-8");t.replace(p)
def cmd(a):return subprocess.check_output(a,universal_newlines=True).strip()
def active(j):
    p=subprocess.run(["squeue","-h","-j",str(j),"-o","%i|%T"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    if p.returncode and "Invalid job" not in p.stderr:raise RuntimeError(p.stderr)
    return bool(p.stdout.strip())
def main():
    lock=(RUN/"recovery-dispatch.lock").open("a");fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    q=read(RUN/"queue.json")
    q.setdefault("retry_arrays",[])
    q.setdefault("attempts",{str(t):2 if t==5 else 1 for t in q["tasks"]})
    while True:
        try:
            missing=[t for t in range(24) if not (RUN/"shards"/f"{t:03d}"/"manifest.json").exists()]
            jobs=[q["recovery_array"],q["transient_retry"]["job"],*q["retry_arrays"],q["original_remaining_job"]]
            live=[j for j in jobs if active(j)]
            if not missing and not live:
                for t in range(24):
                    if not read(RUN/"shards"/f"{t:03d}"/"manifest.json")["metrics"]["all_accounted"]:raise ValueError("incomplete manifest")
                cmd(["scontrol","update","JobId="+q["summary_job"],"Dependency=afterany:"+":".join(jobs)])
                cmd(["scontrol","release",q["summary_job"]])
                q["status"]="all_shards_complete_summary_released";q["updated_utc"]=datetime.datetime.utcnow().isoformat()+"Z"
                write(RUN/"queue.json",q);return
            if missing and not live:
                eligible=[t for t in missing if t in q["tasks"] and q["attempts"].get(str(t),0)<3]
                if not eligible:
                    q["status"]="requires_attention";q["incomplete_tasks"]=missing;write(RUN/"queue.json",q);return
                job=cmd(["sbatch","--parsable","--array="+",".join(map(str,eligible))+"%6","--exclude=cn69,cn55",
                         "--job-name=obj-seg-resume","--output="+str(RUN/"logs/auto-retry-%A_%a.log"),str(AUDIT/"run_shard.sbatch")]).split(";")[0]
                q["retry_arrays"].append(job)
                for t in eligible:q["attempts"][str(t)]=q["attempts"].get(str(t),0)+1
                print("RETRY",job,eligible,flush=True)
            q["status"]="running_recovery";q["incomplete_tasks"]=missing;q["updated_utc"]=datetime.datetime.utcnow().isoformat()+"Z"
            write(RUN/"queue.json",q)
        except Exception as e:
            q["last_dispatch_error"]=str(e);write(RUN/"queue.json",q);print("DISPATCH ERROR",e,flush=True)
        time.sleep(30)
if __name__=="__main__":main()
