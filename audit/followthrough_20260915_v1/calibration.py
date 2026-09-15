"""Cleaned Kimina and formal-entry sensitivity, with disjoint transform/threshold tasks."""
import collections,gzip
import numpy as np,pandas as pd
from scipy import linalg
from stage_support import *
def fit(x):
 mean=x.mean(0);c=x-mean
 _,s,v=linalg.svd(c/np.sqrt(len(x)-1),full_matrices=False,check_finite=False)
 return {"mean":mean,"vectors":v,"variances":s*s,"average":float(np.sum(s*s)/x.shape[1])}
def values(x,f,shrinks):
 out={s:np.empty(len(x)) for s in shrinks}
 for lo in range(0,len(x),256):
  hi=min(len(x),lo+256);c=x[lo:hi]-f["mean"];pr=c@f["vectors"].T
  orth=np.sum((c-pr@f["vectors"])**2,axis=1)
  for s in shrinks:out[s][lo:hi]=np.sqrt(np.sum(pr*pr/((1-s)*f["variances"]+s*f["average"]),axis=1)+orth/(s*f["average"]))
 return out
def binary_group(df,mask,hit):
 g=df.loc[mask,["prompt_id","trace_id"]].copy();g["hit"]=hit[mask]
 if g.empty:return {"steps":0,"tasks":0,"step_rate":None,"equal_task_rate":None}
 return {"steps":len(g),"tasks":g.prompt_id.nunique(),"step_rate":float(g.hit.mean()),"equal_task_rate":float(g.groupby("prompt_id").hit.mean().mean())}
def summarize(df,z,tau,replicates,seed):
 verified=df.outcome.to_numpy()=="verified";ev=df.role.to_numpy()=="evaluation"
 pre=(~verified)&(df.t.to_numpy()<df.t_star.to_numpy());at=(~verified)&(df.t.to_numpy()==df.t_star.to_numpy())
 masks={"verified":ev&verified,"pre":ev&pre,"accepted":ev&(verified|pre),"at":ev&at}
 out={"tau":float(tau),**{k:binary_group(df,mask,z>tau) for k,mask in masks.items()}}
 hits=[]
 for tid,g in df[ev&~verified].groupby("trace_id",sort=True):
  ix=g.index.to_numpy();f=int(g.t_star.iloc[0]);j=int(np.argmax(z[ix]));sj=int(np.argmax(g.surprisal.to_numpy()))
  hits.append({"trace_id":tid,"task":str(g.prompt_id.iloc[0]),"jump":float(j==f),"surprisal":float(sj==f),"first":int(j==0)})
 if hits:
  tab=pd.DataFrame(hits);task=tab.groupby("task")[["jump","surprisal"]].mean();delta=(task.jump-task.surprisal).to_numpy()
  rng=np.random.default_rng(seed);draw=[]
  for lo in range(0,replicates,500):
   ix=rng.integers(len(delta),size=(min(500,replicates-lo),len(delta)));draw.extend(delta[ix].mean(1))
  out["P2"]={"traces":len(tab),"tasks":len(task),"jump":float(tab.jump.mean()),"surprisal":float(tab.surprisal.mean()),
    "equal_task_jump":float(task.jump.mean()),"equal_task_surprisal":float(task.surprisal.mean()),
    "equal_task_difference":float(delta.mean()),"ci95_fixed_transform":np.quantile(draw,[.025,.975]),
    "first_max":float(tab["first"].mean())}
 return out
def tests():
 rng=np.random.default_rng(129);x=rng.normal(size=(17,7));y=rng.normal(size=(11,7));f=fit(x)
 for s,z in values(y,f,[.1,.5,1.0]).items():
  cov=np.cov(x,rowvar=False);cov=(1-s)*cov+s*np.trace(cov)/7*np.eye(7)
  expected=np.sqrt(np.einsum("ij,jk,ik->i",y-x.mean(0),np.linalg.inv(cov),y-x.mean(0)))
  assert np.allclose(z,expected,atol=1e-10)
 states=rng.normal(size=(5,7));form=rng.normal(size=7);orig=np.diff(states,axis=0)
 altered=orig.copy();altered[0]=states[1]-form
 assert np.array_equal(altered[1:],orig[1:])
 return {"direct_inverse_covariance":True,"formal_entry_only_changes_first_increment":True}
def main():
 plan=start("calibration");passed=tests();inputs=[];results={};outputpaths=[]
 folder=OUT/"calibration";folder.mkdir(parents=True,exist_ok=True)
 for model in MODELS:
  print("LOAD",model,flush=True);layer=plan["layers"][model]
  md=STATES/"measurement"/model
  if model=="kimina":md=ROOT/"runs/kimina_post_completion_20260914_v1/measurement"
  check_manifest(md/"manifest.json");inputs.append(md/"manifest.json")
  table=pd.read_parquet(md/"deviations.parquet")
  df=table[(table.temperature==plan["temperature"])&(table.layer==layer)&(table.statistic=="whitened")].sort_values(["trace_id","t"]).reset_index(drop=True)
  wanted=set(df.trace_id);records={}
  for task,m in read(STATES/"plan.json")["models"].items():
   if m!=model:continue
   shard=STATES/"shards"/("%03d"%int(task));check_manifest(shard/"manifest.json");inputs.append(shard/"manifest.json")
   with (shard/"trajectories.jsonl").open(encoding="utf-8") as f:
    for line in f:
     rec=json.loads(line)
     if rec["trace_id"] in wanted:records[rec["trace_id"]]=rec
  chunks=[];formal=[];first_ix=[];has=[];anchor_inventory=[];cursor=0
  for tid,g in df.groupby("trace_id",sort=True):
   rec=records[tid];assert digest(rec["states_path"])==rec["states_sha256"]
   with np.load(rec["states_path"],allow_pickle=False) as data:
    states=data["states_"+str(layer)].astype(float);n=len(g);assert len(states)>=n+1
    assert g.t.tolist()==list(range(n));assert np.allclose(data["surprisal"][:n],g.surprisal.to_numpy(),equal_nan=False)
    if len(states)>n+1:assert model=="kimina" and g.outcome.iloc[0]=="verified"
    entry=data["formal_state_"+str(layer)].astype(float) if "formal_state_"+str(layer) in data.files else None
   assert (rec["alignment"]["formal_position"] is not None)==(entry is not None)
   if entry is not None:assert rec["alignment"]["formal_position"]<rec["alignment"]["positions"][1]
   inc=np.diff(states[:n+1],axis=0);chunks.append(inc);first_ix.append(cursor);formal.append(None if entry is None else states[1]-entry)
   has.extend([entry is not None]*n);cursor+=n
   anchor_inventory.append({"trace_id":tid,"task":str(g.prompt_id.iloc[0]),"role":g.role.iloc[0],"outcome":g.outcome.iloc[0],
    "formal_available":entry is not None,"formal_position":rec["alignment"]["formal_position"],"original_steps":len(states)-1,"kept_steps":n})
  X=np.concatenate(chunks);del chunks,states,table
  inventory_path=folder/(model+"-anchor-inventory.json");atomic(inventory_path,anchor_inventory);outputpaths.append(inventory_path)
  available=np.asarray(has,bool);changed=np.flatnonzero(available)
  # Identical paired trace population for the two baselines; missing anchors never silently fall back.
  F=X.copy()
  for ix,entry in zip(first_ix,formal):
   if entry is not None:F[ix]=entry
  paired=df.loc[available].copy().reset_index(drop=True);XP=X[available];FP=F[available]
  cal=(paired.role.to_numpy()=="calibration")&(paired.outcome.to_numpy()=="verified")
  calids=set(paired.loc[cal,"prompt_id"]);evalids=set(paired.loc[paired.role=="evaluation","prompt_id"]);assert not calids&evalids
  tasks=sorted(calids,key=lambda t:hashlib.sha256(str(t).encode()).hexdigest());folds=[set(tasks[::2]),set(tasks[1::2])]
  assert min(map(len,folds))>=plan["min_tasks_per_fold"]
  result={"input_population":len(df.drop_duplicates("trace_id")),"paired_population":len(paired.drop_duplicates("trace_id")),
    "missing_formal_traces":sum(not r["formal_available"] for r in anchor_inventory),
    "removed_terminal_steps":sum(r["original_steps"]-r["kept_steps"] for r in anchor_inventory),
    "formal_anchor_definition":plan["formal_anchor"],"variants":{}}
  for name,Y in [("original_prompt",XP),("formal_entry",FP)]:
   output=[]
   for fold in [0,1]:
    fm=cal&paired.prompt_id.isin(folds[fold]).to_numpy();tm=cal&paired.prompt_id.isin(folds[1-fold]).to_numpy()
    print("FIT",model,name,fold,int(fm.sum()),flush=True);f=fit(Y[fm]);zs=values(Y,f,plan["shrinkage"])
    transform_path=folder/(model+"-"+name+"-fold"+str(fold)+"-transform.npz")
    np.savez_compressed(transform_path,**f);outputpaths.append(transform_path)
    scores=paired[["trace_id","prompt_id","t","t_star","outcome","role","surprisal"]].copy()
    entry={"fit_fold":fold,"fit_task_ids":sorted(folds[fold]),"threshold_task_ids":sorted(folds[1-fold]),"settings":{}}
    for s,z in zs.items():
     tau=float(np.quantile(z[tm],1-plan["q"]));v=summarize(paired,z,tau,plan["bootstrap_replicates"],plan["seed"])
     v["threshold_calibration_rate"]=float(np.mean(z[tm]>tau));v["fit_calibration_rate"]=float(np.mean(z[fm]>tau))
     entry["settings"][str(s)]=v;scores["z_shrinkage_"+str(s)]=z
    sp=folder/(model+"-"+name+"-fold"+str(fold)+"-scores.parquet");scores.to_parquet(sp,index=False);outputpaths.append(sp);output.append(entry)
   result["variants"][name]=output
  results[model]=result;atomic(folder/(model+"-partial.json"),result)
  del X,F,XP,FP,df,paired,records
 finish("calibration",{"models":results,"checks":passed,"generation_calls":0,"model_forward_calls":0,
  "scope":"paired baseline sensitivity on existing evaluation tasks; clean Kimina; all settings reported, not a new confirmation"},inputs,outputpaths)
 print("CALIBRATION COMPLETE",flush=True)
if __name__=="__main__":main()
