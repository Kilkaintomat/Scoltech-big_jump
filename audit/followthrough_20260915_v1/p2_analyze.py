import collections
from stage_support import *
from analysis_math import *
from onebigjump.e1.artifacts import identity
def main():
 plan=start("p2_pipeline");protocol=read(HERE/"p2-confirmatory-protocol.json")
 folder=OUT/"p2_results";folder.mkdir(exist_ok=True);base=OUT/"p2_pipeline";results={};outputs=[];inputs=[]
 for model in protocol["models"]:
  mp=base/model/"extraction/manifest.json";check_manifest(mp);inputs.append(mp)
  with (mp.parent/"trajectories.jsonl").open(encoding="utf-8") as f:records=[json.loads(line) for line in f]
  transform=OUT/"calibration"/(model+"-formal_entry-fold0-transform.npz")
  expected=read(HERE/"p2_pipeline-source-manifest.json")["files"][str(transform)];assert digest(transform)==expected;inputs.append(transform)
  with np.load(transform,allow_pickle=False) as z:fit_params={k:z[k] for k in z.files}
  trials=[];byid={}
  for r in records:
   if r["role"]!="evaluation":continue
   byid[r["trace_id"]]=r
   if r["extraction_status"]!="extracted":continue
   assert digest(r["states_path"])==r["states_sha256"]
   with np.load(r["states_path"],allow_pickle=False) as z:
    jump=values(z["increments"],fit_params,.1);surprisal=z["surprisal"]
   star=r["t_star"];L=len(jump);assert 0<=star<L
   trial={k:r[k] for k in ["trace_id","problem_id","exercise_group","task_family"]}
   trial.update(f=star,L=L,j=int(np.argmax(jump)),s=int(np.argmax(surprisal)),jump_hit=int(np.argmax(jump)==star),surprisal_hit=int(np.argmax(surprisal)==star),
    jump_tied=int(np.sum(jump==jump.max())>1),surprisal_tied=int(np.sum(surprisal==surprisal.max())>1),
    j_no_first=int(np.argmax(jump[1:]))+1 if L>1 else None,s_no_first=int(np.argmax(surprisal[1:]))+1 if L>1 else None)
   trials.append(trial)
  groups=equal_group(trials);boot=bootstrap_group(groups,protocol["bootstrap_replicates"],protocol["seed"],alpha=.025)
  pos={}
  if model=="deepseek":
   # Pick one trace before consulting error position or the measured scores.
   one={}
   for r in byid.values():
    if not r["p2_eligible"]:continue
    g=r["exercise_group"];key=identity([protocol["seed"],g,r["trace_id"]])
    if g not in one or key<one[g][0]:one[g]=(key,r["trace_id"])
   trialmap={r["trace_id"]:r for r in trials};selected=[trialmap[tid] for key,tid in one.values() if tid in trialmap]
   later=[dict(r,j=r["j_no_first"]-1,f=r["f"]-1,L=r["L"]-1) for r in selected if r["f"]>0 and r["L"]>1]
   pos=exact_position(later);pos.update(representatives_before_error_filter=len(one),formal_or_extraction_unavailable=len(one)-len(selected),later_error_representatives=len(later),
    decisive=pos["matched_groups"]>=20 and pos["p_one_sided"] is not None and pos["p_one_sided"]<=.025,
    adequate=pos["matched_groups"]>=20)
  value={"assigned_evaluation_attempts":sum(r["role"]=="evaluation" for r in records),"extraction_statuses":dict(collections.Counter(r["extraction_status"] for r in records if r["role"]=="evaluation")),
   "eligible_traces":len(trials),"eligible_problems":len({r["problem_id"] for r in trials}),"eligible_exercise_groups":len(groups),
   "trace_weighted_jump":float(np.mean([r["jump_hit"] for r in trials])) if trials else None,
   "trace_weighted_surprisal":float(np.mean([r["surprisal_hit"] for r in trials])) if trials else None,
   "equal_group_difference":boot,"ties":{"jump":sum(r["jump_tied"] for r in trials),"surprisal":sum(r["surprisal_tied"] for r in trials)}}
  if model=="goedel":value["primary"]={"adequate":boot["available"],"confirmed":bool(boot["available"] and boot["interval"][0]>0),"claim":"Equal-exercise-group top1 advantage over surprisal.","family_size":2}
  else:value["primary"]={"adequate":pos["adequate"],"confirmed":pos["decisive"],"claim":"Later-error localization beyond textbook-by-length positional null after first increment removal.","family_size":2,"position":pos}
  results[model]=value
  p=folder/(model+"-trials.json");atomic(p,trials);outputs.append(p)
  p=folder/(model+"-group-effects.json");atomic(p,groups);outputs.append(p)
 # This stage has its own immutable source manifest and plan, linked to the prospective pipeline.
 finish("p2_results",{"models":results,"scope":"Fixed prospective endpoints on project-new ProofNet tasks; no general heavy-tail or coupling claim.", "protocol_sha256":digest(HERE/"p2-confirmatory-protocol.json")},inputs,outputs)
 print("PROSPECTIVE P2 COMPLETE",json.dumps(clean(results)),flush=True)
if __name__=="__main__":main()
