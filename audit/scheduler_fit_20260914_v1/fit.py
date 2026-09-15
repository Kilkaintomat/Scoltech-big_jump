"""Validate real-GPU profile and set pending job time limits before releasing its dependencies."""
import datetime,hashlib,json,math,os,platform,subprocess,sys
from pathlib import Path
R=Path("/beegfs/home/denis.rakhmankin/onebigjump")
A=R/"audit/scheduler_fit_20260914_v1"
O=R/"runs/segmentation_extraction_repair_20260914_v3"
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
    tmp=p.with_suffix(p.suffix+".tmp");tmp.write_text(json.dumps(x,indent=2)+"\n",encoding="utf-8");tmp.replace(p)
def check(p):
    m=read(p)
    for n,h in m["outputs"].items():
        if digest(n)!=h:raise RuntimeError("changed profile or preflight output: "+n)
    return m
def main():
    q=read(O/"queue.json");pm=O/("profile-"+q["profile"])/"manifest.json";check(pm);check(O/"preflight/manifest.json")
    source=read(R/"audit/segmentation_extraction_repair_20260914_v3/source-manifest.json")
    for n,h in source["files"].items():
        if digest(n)!=h:raise RuntimeError("changed extraction repair source")
    p=read(pm.parent/"metrics.json");w=read(O/"preflight/metrics.json")["ready_by_model"]
    if not p.get("all_selected_complete") or p.get("deadline_reached"):raise RuntimeError("incomplete GPU profile; do not release full extraction")
    result={"policy":read(A/"policy.json"),"profile":str(pm),"models":{},"actions":[]};out=O/"scheduler-fit";out.mkdir(exist_ok=False)
    for index,model in enumerate(["deepseek","goedel","kimina"]):
        m=p["models"][model];samples=m["samples"]
        selection=read(R/"runs/segmentation_quality_20260914_v1"/model/"profile-selection.json")
        if {s["trace_id"] for s in samples}!={s["trace_id"] for s in selection}:raise RuntimeError("profile coverage mismatch")
        if any(s["status"]!="ok" for s in samples):raise RuntimeError("profile encountered GPU error")
        if not all(v["passed"] for v in m["forward_check"].values()):raise RuntimeError("full forward does not agree")
        if max(s["tokens"] for s in samples)<w[model]["max_tokens"]:raise RuntimeError("longest input not covered")
        rate=max(s["forward_seconds"]/s["tokens"] for s in samples)
        overhead=max(s["alignment_and_initial_check_seconds"] for s in samples)+2*max(s["compress_seconds"] for s in samples)+result["policy"]["io_allowance_seconds_per_trace"]
        estimate=w[model]["total_tokens"]*rate+w[model]["traces"]*overhead
        conservative=result["policy"]["multiplier"]*estimate+result["policy"]["fixed_margin_seconds"]
        if not math.isfinite(conservative) or conservative<=0:raise RuntimeError("invalid runtime estimate")
        hours=min(12,max(2,math.ceil(conservative/1800)/2))
        minutes=int(hours*60)
        result["models"][model]={"job":q["gpu_tasks"][index],"profile_seconds_per_token_envelope":rate,
          "per_trace_overhead_seconds":overhead,"projected_seconds":estimate,
          "with_margin_seconds":conservative,"time_limit_minutes":minutes,
          "cap_exceeded":conservative>12*3600,"heuristic_not_guaranteed_upper_bound":True}
        if conservative>12*3600:raise RuntimeError("profile suggests existing 12h insufficient; inspect before launching")
    write(out/"plan.json",result)
    for model,v in result["models"].items():
        job=v["job"]
        before=subprocess.check_output(["scontrol","show","job",job,"-o"]).decode()
        if "JobState=PENDING " not in before:raise RuntimeError("only pending GPU jobs may be changed")
        args=["scontrol","update","JobId="+job,"TimeLimit="+str(v["time_limit_minutes"])]
        r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        action={"model":model,"command":args,"returncode":r.returncode,"stdout":r.stdout,"stderr":r.stderr,"before":before}
        result["actions"].append(action);write(out/"result.json",result)
        if r.returncode:raise RuntimeError("time limit update rejected")
        action["after"]=subprocess.check_output(["scontrol","show","job",job,"-o"]).decode()
        expected="%02d:%02d:00"%(v["time_limit_minutes"]//60,v["time_limit_minutes"]%60)
        if "TimeLimit="+expected+" " not in action["after"]:raise RuntimeError("time limit readback differs")
        write(out/"result.json",result)
    write(out/"manifest.json",{"config":read(A/"policy.json"),"source_control":source["source_control"],
      "environment":{"python":sys.version,"host":platform.node(),"platform":platform.platform(),"job_id":os.environ.get("SLURM_JOB_ID")},
      "inputs":{str(x):digest(x) for x in [A/"fit.py",A/"policy.json",pm,O/"preflight/manifest.json",O/"queue.json"]},
      "outputs":{str(x):digest(x) for x in [out/"plan.json",out/"result.json"]}})
    print(json.dumps(result["models"]),flush=True)
if __name__=="__main__":main()
