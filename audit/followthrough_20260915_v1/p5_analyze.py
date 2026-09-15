import collections
import numpy as np
from stage_support import *
from analysis_math import fit,values
from onebigjump.readiness import deduction
from onebigjump.e1.stages import rows
from onebigjump.experiments.p5_rate import fit_length_rate,score_heldout
def by_length(rows_):
 return {L:(sum(r["verified"] for r in rows_ if r["length"]==L),sum(r["length"]==L for r in rows_)) for L in sorted({r["length"] for r in rows_})}
def rate_compare(cal,ev,replicates,seed):
 counts=by_length(cal);ec=by_length(ev);f=fit_length_rate(counts);held=score_heldout(f,ec)
 baseline=np.mean([r["verified"] for r in cal]);base_brier=np.mean([(r["verified"]-baseline)**2 for r in ev]);rng=np.random.default_rng(seed);diffs=[]
 cgroups={L:[r for r in cal if r["length"]==L] for L in counts};egroups={L:[r for r in ev if r["length"]==L] for L in ec}
 for i in range(replicates):
  cb=[g[j] for g in cgroups.values() for j in rng.integers(0,len(g),len(g))]
  eb=[g[j] for g in egroups.values() for j in rng.integers(0,len(g),len(g))]
  cf=fit_length_rate(by_length(cb));score=score_heldout(cf,by_length(eb));bp=np.mean([r["verified"] for r in cb])
  diffs.append(float(np.mean([(r["verified"]-bp)**2 for r in eb])-score["brier"]))
 return {"calibration_counts":counts,"evaluation_counts":ec,"calibration_rate":f,"heldout":held,"constant_calibration_baseline":{"probability":float(baseline),"heldout_brier":float(base_brier)},
  "brier_improvement":float(base_brier-held["brier"]),"brier_improvement_ci975":np.quantile(diffs,[.0125,.9875]).tolist(),
  "bootstrap_unit":"independent problem within assigned length; refit on resampled calibration, evaluate on independently resampled evaluation","bootstrap_replicates":replicates,
  "interpretation":"Length-dependent predictive performance; does not identify theta, tau or a heavy-tail mechanism."}
def main():
 plan=start("p5_analysis");root=OUT/"p5_calibration";gatepath=root/"calibration_gate/manifest.json";check_manifest(gatepath);gate=read(gatepath.parent/"metrics.json")
 if not gate["ready_for_evaluation"]:raise RuntimeError("P5 calibration not adequate")
 all_records=[];states={};inputpaths=[gatepath];outputs=[];labs={}
 for arm in ["calibration","evaluation"]:
  rroot=OUT/("p5_"+arm)
  for stage in ["verification","extraction"]:
   p=rroot/"main"/stage/"manifest.json";check_manifest(p);inputpaths.append(p)
  sample_list,_=deduction.samples(rroot,"main");samples={s["trace_id"]:s for s in sample_list}
  for label in rows(rroot/"main/verification/labels.jsonl"):
   s=samples[label["trace_id"]];prob=s["problem"];key=label["trace_id"];assert key not in labs;labs[key]=label
   all_records.append({"trace_id":key,"problem_id":prob["problem_id"],"role":arm,"temperature":s["temperature"],"length":prob["length"],
    "verified":bool(label["verified"]),"format_eligible":bool(label["format_eligible"]),"category":label["category"]})
  for rec in rows(rroot/"main/extraction/trajectories.jsonl"):
   if rec["extraction_status"]=="extracted":
    assert digest(rec["states_path"])==rec["states_sha256"]
    with np.load(rec["states_path"],allow_pickle=False) as z:states[rec["trace_id"]]={k:z[k] for k in z.files}
 caltasks={r["problem_id"] for r in all_records if r["role"]=="calibration"};evtasks={r["problem_id"] for r in all_records if r["role"]=="evaluation"};assert not caltasks&evtasks
 output={};folder=OUT/"p5_analysis";folder.mkdir(exist_ok=True)
 layer=plan["layer"]
 for temp in plan["temperatures"]:
  subset=[r for r in all_records if r["temperature"]==temp];cal=[r for r in subset if r["role"]=="calibration"];ev=[r for r in subset if r["role"]=="evaluation"]
  item={"attempts":len(subset),"categories":dict(collections.Counter(r["category"] for r in subset)),"length_prediction":rate_compare(cal,ev,plan["bootstrap_replicates"],plan["seed"]+int(temp*100))}
  tasks=gate["temperatures"][str(temp)];fitids=set(tasks["transform_task_ids"]);thresholdids=set(tasks["threshold_task_ids"]);assert not fitids&thresholdids
  fitrows=[r for r in cal if r["verified"] and r["problem_id"] in fitids];thresholdrows=[r for r in cal if r["verified"] and r["problem_id"] in thresholdids]
  assert len({r["problem_id"] for r in fitrows})>=20 and len({r["problem_id"] for r in thresholdrows})>=20
  X=np.concatenate([np.diff(states[r["trace_id"]]["states_"+str(layer)].astype(float),axis=0) for r in fitrows]);f=fit(X)
  path=folder/(f"transform-T{temp}.npz");np.savez_compressed(path,**f);outputs.append(path)
  zth=np.concatenate([values(np.diff(states[r["trace_id"]]["states_"+str(layer)].astype(float),axis=0),f) for r in thresholdrows])
  tau=float(np.quantile(zth,.99));verified=[];at=[];pre=[];trials=[]
  for r in ev:
   key=r["trace_id"]
   if key not in states:continue
   z=values(np.diff(states[key]["states_"+str(layer)].astype(float),axis=0),f);sp=states[key]["surprisal"];lab=labs[key]
   if r["verified"]:verified.extend((z>tau).tolist())
   else:
    star=lab["t_star"]
    if star is None:continue
    assert 0<=star<len(z);at.append(bool(z[star]>tau));pre.extend((z[:star]>tau).tolist())
    trials.append({"trace_id":key,"problem_id":r["problem_id"],"length":r["length"],"jump_hit":int(np.argmax(z)==star),"surprisal_hit":int(np.argmax(sp)==star)})
  def rate(a):return {"steps":len(a),"rate":float(np.mean(a)) if a else None}
  item["independent_whitening"]={"layer":layer,"shrinkage":.1,"fit_tasks":len(fitids),"threshold_tasks":len(thresholdids),"fit_steps":len(X),"threshold_steps":len(zth),"tau":tau,"verified_FPR":rate(verified),"pre_error_FPR":rate(pre),"error_TPR":rate(at),
   "localization":{"eligible":len(trials),"jump":float(np.mean([r["jump_hit"] for r in trials])) if trials else None,"surprisal":float(np.mean([r["surprisal_hit"] for r in trials])) if trials else None},"scope":"Descriptive P2/P3 on the controlled family; no endpoint-specific tuning."}
  path=folder/(f"localization-T{temp}.json");atomic(path,trials);outputs.append(path);output[str(temp)]=item
 path=folder/"assigned-attempts.json";atomic(path,all_records);outputs.append(path)
 finish("p5_analysis",{"temperatures":output,"calibration_evaluation_task_overlap":0,"tail_estimation":"Not performed by this stage; no inference of gamma, theta or a tail mechanism from length-rate fit alone.","scope":"Expanded controlled family, syntax-only grammar, all assigned outcomes in denominators; fixed independent calibration."},inputpaths,outputs)
 print("P5 EXPANSION ANALYSIS COMPLETE",flush=True)
if __name__=="__main__":main()
