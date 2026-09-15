"""Slurm/file management only. Resume incomplete shards, never redo completed rows."""
import argparse,datetime,fcntl,json,os,subprocess,time
from pathlib import Path
ACTIVE={"PENDING","RUNNING","CONFIGURING","COMPLETING","SUSPENDED","REQUEUED","RESIZING"}
def read(p):
    with Path(p).open(encoding="utf-8") as f:return json.load(f)
def write(p,x):
    tmp=Path(str(p)+".tmp")
    with tmp.open("w",encoding="utf-8") as f:json.dump(x,f,indent=2,sort_keys=True)
    tmp.replace(p)
def command(args):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    if p.returncode:raise RuntimeError(str(args)+": "+p.stderr.strip())
    return p.stdout.strip()
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True,type=Path);p.add_argument("--prepare-job",required=True);a=p.parse_args()
    root=a.root;root.mkdir(parents=True,exist_ok=True);logs=root/"logs";logs.mkdir(exist_ok=True)
    lock=(root/"manager.lock").open("a")
    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    queue=root/"queue.json"
    if queue.exists():state=read(queue)
    else:state={"prepare_job":a.prepare_job,"arrays":[],"attempts":{},"gather_job":None,"status":"preparing"}
    def save(status=None):
        if status:state["status"]=status
        state["scheduler_concurrent_tasks"]=concurrency()
        state["updated_utc"]=datetime.datetime.utcnow().isoformat()+"Z";write(queue,state)
    def running(job):
        p=subprocess.run(["squeue","-h","-j",str(job),"-o","%i|%T"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        if p.returncode and "Invalid job id" not in p.stderr and "Invalid job ID" not in p.stderr:
            raise RuntimeError(p.stderr.strip())
        return bool(p.stdout.strip())
    def concurrency():
        policy=root/"scheduler-policy.json"
        count=read(policy)["concurrent_tasks"] if policy.exists() else read(root/"config.json")["concurrent_tasks"]
        if not isinstance(count,int) or not 1<=count<=8:
            raise ValueError("concurrent_tasks must be an integer in 1..8")
        return count
    def submit(tasks,dependency=None):
        if len(tasks)>12:raise ValueError("at most 12 pending array tasks per wave")
        args=["sbatch","--parsable","--array",",".join(map(str,tasks))+"%"+str(concurrency()),"--job-name","obj-seg3",
              "--output",str(logs/"segmentation-%A_%a.log")]
        if dependency:args+=["--dependency",dependency]
        args.append(str(read(root/"config.json")["source_dir"]+"/run_shard.sbatch"))
        jid=command(args).split(";")[0]
        state["arrays"].append({"job_id":jid,"tasks":tasks,"dependency":dependency,"concurrent_tasks_at_submission":concurrency()})
        for t in tasks:state["attempts"][str(t)]=state["attempts"].get(str(t),0)+1
        state.pop("last_manager_error",None)
        save("submitted");print("SUBMITTED",jid,tasks,flush=True)
    save()
    while True:
        try:
            if not state["arrays"]:
                if running(a.prepare_job):time.sleep(30);continue
                if not (root/"inputs/manifest.json").exists():
                    save("preparation_failed");return
                # The older pipeline's currently active jobs, if any, keep priority.
                jobs=command(["squeue","-h","-u","denis.rakhmankin","-o","%i|%j|%T"])
                old=[line.split("|")[0] for line in jobs.splitlines() if any(prefix in line for prefix in ["obj-ctrl13local","obj0913local","obj0909"])]
                state["old_active_jobs_at_submission"]=old
                dep="afterany:"+":".join(old) if old else None
                submit(list(range(min(12,read(root/"config.json")["n_tasks"]))),dep)
            last=state["arrays"][-1]["job_id"]
            if running(last):
                save("running_or_queued");time.sleep(30);continue
            missing=[]
            for task in range(read(root/"config.json")["n_tasks"]):
                m=root/"shards"/("{:03d}".format(task))/"manifest.json"
                if not m.exists() or not read(m)["metrics"]["all_accounted"]:missing.append(task)
            if missing:
                eligible=[t for t in missing if state["attempts"].get(str(t),0)<3]
                if not eligible:
                    state["incomplete_tasks"]=missing;save("requires_attention");return
                eligible.sort(key=lambda t:(state["attempts"].get(str(t),0),t))
                submit(eligible[:12]);time.sleep(30);continue
            if not state["gather_job"]:
                script=Path("/beegfs/home/denis.rakhmankin/onebigjump/audit/segmentation_v3_20260914/gather.sbatch")
                jid=command(["sbatch","--parsable","--job-name","obj-seg3-summary","--output",str(logs/"summary-%j.log"),str(script)]).split(";")[0]
                state["gather_job"]=jid;save("summarizing")
            if running(state["gather_job"]):time.sleep(30);continue
            m=root/"summary/metrics.json"
            if m.exists() and read(m)["all_accounted"]:save("complete")
            else:save("summary_failed")
            return
        except Exception as e:
            state["last_manager_error"]=str(e);save();time.sleep(30)
if __name__=="__main__":main()
