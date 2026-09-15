"""Exploratory disjoint whitening/threshold calibration on saved original-token states."""
import collections,hashlib
import numpy as np,pandas as pd
from scipy import linalg
from support import *
def fit(x):
    mean=x.mean(0);c=x-mean
    _,s,v=linalg.svd(c/np.sqrt(len(x)-1),full_matrices=False,check_finite=False)
    return {"mean":mean,"vectors":v,"variances":s*s,"average":float(np.sum(s*s)/x.shape[1])}
def values(x,f,shrinks):
    out={s:np.empty(len(x)) for s in shrinks}
    for lo in range(0,len(x),256):
        hi=min(len(x),lo+256);c=x[lo:hi]-f["mean"];p=c@f["vectors"].T
        residual=c-p@f["vectors"];orth=np.sum(residual**2,axis=1);square=p*p
        for s in shrinks:
            eigen=(1-s)*f["variances"]+s*f["average"];base=s*f["average"]
            out[s][lo:hi]=np.sqrt(np.sum(square/eigen,axis=1)+orth/base)
    return out
def score(df,z,tau):
    cal=df.role.to_numpy()=="calibration";verified=df.outcome.to_numpy()=="verified"
    ev=~cal;pre=(~verified)&(df.t.to_numpy()<df.t_star.to_numpy());at=(~verified)&(df.t.to_numpy()==df.t_star.to_numpy())
    def rate(mask):return {"steps":int(mask.sum()),"rate":float(np.mean(z[mask]>tau)) if mask.any() else None}
    ids=df.loc[ev&~verified,"trace_id"].unique();hit=0
    for tid in ids:
        ix=np.flatnonzero((df.trace_id.to_numpy()==tid)&ev);f=int(df.t_star.iloc[ix[0]]);hit+=int(np.argmax(z[ix])==f)
    return {"tau":float(tau),"verified":rate(ev&verified),"pre":rate(ev&pre),"accepted":rate(ev&(verified|pre)),"at":rate(ev&at),"P2":{"traces":len(ids),"hits":hit,"top1":hit/len(ids)}}
def main():
    check_code();plan=read(HERE/"plan.json");results={};inputs=[]
    for model in MODELS:
        print("LOAD",model,flush=True)
        md=STATES/"measurement"/model;check_manifest(md/"manifest.json");inputs.append(md/"manifest.json")
        table=pd.read_parquet(md/"deviations.parquet");layer=plan["primary"]["layers"][model]
        df=table[(table.temperature==.6)&(table.layer==layer)&(table.statistic=="whitened")].sort_values(["trace_id","t"]).reset_index(drop=True)
        wanted=set(df.trace_id);records={}
        for task,m in read(STATES/"plan.json")["models"].items():
            if m!=model:continue
            folder=STATES/"shards"/("%03d"%int(task));inputs.append(folder/"manifest.json")
            with (folder/"trajectories.jsonl").open(encoding="utf-8") as stream:
                for line in stream:
                    r=json.loads(line)
                    if r["trace_id"] in wanted:records[r["trace_id"]]=r
        xs=[]
        for tid,g in df.groupby("trace_id",sort=True):
            r=records[tid]
            if digest(r["states_path"])!=r["states_sha256"]:raise ValueError("saved states corrupted")
            with np.load(r["states_path"],allow_pickle=False) as f:states=f["states_"+str(layer)].astype(float)
            if len(states)!=len(g)+1:raise ValueError("state/table alignment")
            xs.append(np.diff(states,axis=0))
        X=np.concatenate(xs);del xs;assert len(X)==len(df)
        calibration=(df.role.to_numpy()=="calibration")&(df.outcome.to_numpy()=="verified")
        tasks=sorted(set(df.loc[calibration,"prompt_id"].astype(str)),key=lambda x:hashlib.sha256(x.encode()).hexdigest())
        folds=[set(tasks[::2]),set(tasks[1::2])]
        if min(map(len,folds))<20 or folds[0]&folds[1]:raise ValueError("invalid disjoint folds")
        saved=md/("transform-T0.6-layer"+str(layer)+".npz")
        with np.load(saved,allow_pickle=False) as f:
            baseline={"mean":f["mean"],"vectors":f["vectors"],"variances":np.maximum(0,(f["eigenvalues"]-.1*f["average_eigenvalue"])/.9),"average":float(f["average_eigenvalue"])}
        check=values(X,baseline,[.1])[.1]
        if not np.allclose(check,df.z.to_numpy(),atol=1e-5,rtol=1e-5):raise ValueError("independent whitening does not reproduce original scores")
        output={"n_steps":len(df),"d":X.shape[1],"calibration_steps":int(calibration.sum()),"calibration_tasks":len(tasks),"full_fit_reproduction_max_abs_error":float(np.max(np.abs(check-df.z.to_numpy()))),"folds":[]}
        del check,baseline
        for i in range(2):
            fitting=calibration&df.prompt_id.astype(str).isin(folds[i]).to_numpy()
            thresholding=calibration&df.prompt_id.astype(str).isin(folds[1-i]).to_numpy()
            print("FIT",model,i,int(fitting.sum()),flush=True)
            f=fit(X[fitting]);zs=values(X,f,plan["whitening"]["shrinkage"])
            part={"fit_fold":i,"fit_tasks":len(folds[i]),"threshold_tasks":len(folds[1-i]),"fit_steps":int(fitting.sum()),"threshold_steps":int(thresholding.sum()),"fit_task_ids":sorted(folds[i]),"threshold_task_ids":sorted(folds[1-i]),"settings":{}}
            for s,z in zs.items():
                tau=np.quantile(z[thresholding],.99);v=score(df,z,tau);v["fit_exceedance"]=float(np.mean(z[fitting]>tau));v["threshold_exceedance"]=float(np.mean(z[thresholding]>tau))
                part["settings"][str(s)]=v
            output["folds"].append(part);del f,zs
        results[model]=output;atomic(OUT/(model+"-whitening-partial.json"),clean(output));del X,df,table,records
    finish("whitening",{"models":results,"generation_calls":0,"model_forward_calls":0,"scope":"post-result diagnosis; reports all folds and shrinkage settings"},inputs);print("WHITENING COMPLETE",flush=True)
if __name__=="__main__":main()
