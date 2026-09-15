import json,os,sys,hashlib,datetime
from pathlib import Path
import numpy as np
from data import REPO,RUN as STATES,SEG,read,atomic,digest,environment,check_source,check_manifest
HERE=REPO/"audit/result_review_20260914_v1"
OUT=REPO/"runs/result_review_20260914_v1"
MODELS=["deepseek","goedel","kimina"]
CONTROL=REPO/"runs/segmentation_controls_20260914_v1/controls-8467136"
KIMINA=REPO/"runs/kimina_post_completion_20260914_v1"
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x
def finish(name,metrics,inputs,outputs=()):
    out=OUT/name;out.mkdir(parents=True,exist_ok=True);atomic(out/"metrics.json",clean(metrics))
    paths=[HERE/"plan.json",HERE/"source-manifest.json",*inputs]
    atomic(out/"manifest.json",{"config":read(HERE/"plan.json"),"source_control":read(HERE/"source-manifest.json")["source_control"],
      "environment":environment(),"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "inputs":{str(p):digest(p) for p in paths},
      "outputs":{str(p):digest(p) for p in [out/"metrics.json",*outputs]}})
def check_code():
    if "SLURM_JOB_ID" not in os.environ:raise RuntimeError("Slurm required")
    for p,h in read(HERE/"source-manifest.json")["files"].items():
        if digest(p)!=h:raise RuntimeError("review source changed")
def trace_rows(frame):
    rows=[]
    for tid,g in frame.groupby("trace_id",sort=True):
        g=g.sort_values("t")
        if g.outcome.iloc[0]!="refuted":continue
        f=int(g.t_star.iloc[0]);L=len(g);z=g.z.to_numpy(float);s=g.surprisal.to_numpy(float)
        if g.t.tolist()!=list(range(L)) or not np.isfinite(z).all() or not np.isfinite(s).all():raise ValueError("invalid trace")
        j=int(np.argmax(z));a=int(np.argmax(s))
        rows.append({"id":tid,"task":str(g.prompt_id.iloc[0]),"family":str(g.task_family.iloc[0]),"L":L,"f":f,"j":j,"s":a,
            "jump":float(j==f),"surprisal":float(a==f),"chance":1/L,"D":j-f,
            "rank_jump":int(np.sum(z>z[f]))+1,"rank_surprisal":int(np.sum(s>s[f]))+1})
    return rows
def describe(rows):
    if not rows:return {"traces":0}
    return {"traces":len(rows),"tasks":len(set(r["task"] for r in rows)),
      "jump":np.mean([r["jump"] for r in rows]),"surprisal":np.mean([r["surprisal"] for r in rows]),
      "chance":np.mean([r["chance"] for r in rows]),"difference":np.mean([r["jump"]-r["surprisal"] for r in rows]),
      "mean_L":np.mean([r["L"] for r in rows]),"median_L":np.median([r["L"] for r in rows]),
      "harmonic_L":1/np.mean([r["chance"] for r in rows]),"first_error_rate":np.mean([r["f"]==0 for r in rows]),
      "first_max_rate":np.mean([r["j"]==0 for r in rows]),"Dminus1":np.mean([r["D"]==-1 for r in rows]),
      "D0":np.mean([r["D"]==0 for r in rows]),"Dplus1":np.mean([r["D"]==1 for r in rows]),
      "window1":np.mean([abs(r["D"])<=1 for r in rows]),"mean_rank_jump":np.mean([r["rank_jump"] for r in rows]),
      "mean_rank_surprisal":np.mean([r["rank_surprisal"] for r in rows])}
def paired(rows,seed,replicates):
    keys=sorted(set(r["task"] for r in rows));ix={k:i for i,k in enumerate(keys)}
    sums=np.zeros(len(keys));counts=np.zeros(len(keys))
    for r in rows:sums[ix[r["task"]]]+=r["jump"]-r["surprisal"];counts[ix[r["task"]]]+=1
    means=sums/counts;rng=np.random.default_rng(seed);trace=[];task=[]
    for lo in range(0,replicates,1000):
        w=rng.multinomial(len(keys),np.ones(len(keys))/len(keys),size=min(1000,replicates-lo))
        trace.extend((w@sums)/(w@counts));task.extend((w@means)/len(keys))
    def summary(draws,point):
        return {"point":point,"ci95":np.quantile(draws,[.025,.975]),"ci_family9":np.quantile(draws,[.05/18,1-.05/18])}
    return {"tasks":len(keys),"traces":len(rows),"replicates":replicates,"seed":seed,
       "trace_weighted":summary(trace,sums.sum()/counts.sum()),"equal_task":summary(task,means.mean()),
       "tasks_positive":int(np.sum(means>0)),"tasks_negative":int(np.sum(means<0)),"tasks_zero":int(np.sum(means==0))}
