"""Staged guided P5 expansion using the previously validated generation implementation."""
import argparse,collections
from stage_support import *
from onebigjump.e1.artifacts import verify_manifest,write_once,finish as artifact_finish,identity
from onebigjump.e1.stages import rows
from onebigjump.readiness import deduction
SOURCE=ROOT/"audit/p5_repair_20260914_v2/source/source-manifest.json"
OLD=ROOT/"runs/p5_repair_20260914_v2/guided"
def arm(name):return OUT/("p5_"+name)
def record(folder,name,metrics,inputs):
 p=write_once(folder/"metrics.json",clean(metrics))
 artifact_finish(folder,stage=name,context={"plan":digest(HERE/"p5-plan.json")},inputs=[SOURCE,HERE/"p5-plan.json",Path(__file__),*inputs],outputs=[p],metrics=clean(metrics))
def setup(plan):
 verify_manifest(SOURCE);verify_manifest(OLD/"pilot/gate/manifest.json")
 checks=[];outputs=[]
 for name in ["calibration","evaluation"]:
  root=arm(name);root.mkdir(parents=True,exist_ok=True);conf=read(OLD/"protocol.json")
  conf.update(version="P5-guided-fixed-expansion-20260915",seed=plan["seed"],allow_main=True,pilot_per_role_per_length=0,
   calibration_per_length=plan["calibration_per_length"] if name=="calibration" else 0,
   evaluation_per_length=plan["evaluation_per_length"] if name=="evaluation" else 0,
   attempts_per_temperature=plan["attempts_per_temperature"],scope=plan["scope"],stage=name)
  write_once(root/"protocol.json",conf);deduction.population(root,SOURCE)
  # Reuse only the already established acquisition capability, explicitly attributed.
  record(root/"pilot/gate","inherited-guided-acquisition-gate",
   {"passed":True,"inherited_from":str(OLD/"pilot/gate/manifest.json"),"scope":"technical grammar/alignment/hooks only; does not assert scientific calibration adequacy"},[OLD/"pilot/gate/manifest.json",root/"protocol.json"])
  problems=read(root/"inputs/problems.json")
  for prob in problems:
   gold="\n".join("Mira is "+x+"." for x in prob["gold_chain"])+"\nAnswer: true"
   assert deduction.check(gold,prob)["verified"]
   assert not deduction.check("Mira is pxxxx.",prob)["format_eligible"]
   bad="\n".join("Mira is "+prob["initial"]+"." for _ in prob["gold_chain"])+"\nAnswer: true"
   assert not deduction.check(bad,prob)["verified"]
  req=deduction.requests(root,"main");assert len(req)==len(problems)*len(conf["temperatures"])
  checks.append({"stage":name,"problems":len(problems),"attempts":len(req),"gold_checks":len(problems),"negative_checks":2*len(problems)})
  outputs += [root/"protocol.json",root/"inputs/manifest.json",root/"pilot/gate/manifest.json"]
 a=read(arm("calibration")/"inputs/problems.json");b=read(arm("evaluation")/"inputs/problems.json")
 assert not {p["problem_id"] for p in a}&{p["problem_id"] for p in b}
 def content(p):return identity({k:p[k] for k in ["length","initial","goal","rules"]})
 old=read(OLD/"inputs/problems.json")
 assert not {content(p) for p in a+b}&{content(p) for p in old}
 finish("p5",{"setup_complete":True,"checks":checks,"calibration_evaluation_task_overlap":0,"old_exact_problem_overlap":0,
  "structural_scope":"random symbol assignments and rule order within the same chain-and-distractor family","new_generation_calls":0},[SOURCE,OLD/"pilot/gate/manifest.json"],outputs)
def calibration_gate(plan):
 root=arm("calibration")
 for stage in ["verification","extraction"]:verify_manifest(root/"main"/stage/"manifest.json")
 labs=rows(root/"main/verification/labels.jsonl");recs=rows(root/"main/extraction/trajectories.jsonl")
 samples,_=deduction.samples(root,"main");byid={s["trace_id"]:s for s in samples}
 extracted={r["trace_id"] for r in recs if r["extraction_status"]=="extracted"}
 eligible={r["trace_id"] for r in labs if r["format_eligible"]}
 passed_hook=any(r.get("forward_check",{}).get("passed") for r in recs)
 result={"temperatures":{},"attempts":len(labs),"categories":dict(collections.Counter(r["category"] for r in labs)),
  "format_fraction":len(eligible)/len(labs),"all_eligible_extracted":eligible==extracted,"hook_check":passed_hook}
 ready=eligible==extracted and passed_hook and len(eligible)/len(labs)>=plan["format_minimum"]
 for temp in plan["temperatures"]:
  valid={byid[r["trace_id"]]["problem"]["problem_id"] for r in labs if r["verified"] and byid[r["trace_id"]]["temperature"]==temp}
  folds=[sorted(t for t in valid if int(hashlib.sha256(t.encode()).hexdigest()[:16],16)%2==i) for i in [0,1]]
  okay=min(map(len,folds))>=plan["minimum_verified_tasks_per_transform_fold"]
  result["temperatures"][str(temp)]={"verified_tasks":len(valid),"transform_task_ids":folds[0],"threshold_task_ids":folds[1],"adequate":okay};ready=ready and okay
 result["ready_for_evaluation"]=ready;result["no_evaluation_outcomes_used"]=True
 record(root/"calibration_gate","P5-independent-calibration-readiness",result,[root/"main/verification/manifest.json",root/"main/extraction/manifest.json"])
 print(json.dumps(clean(result)),flush=True)
def main():
 parser=argparse.ArgumentParser();parser.add_argument("stage");parser.add_argument("arm",nargs="?");args=parser.parse_args()
 plan=start("p5")
 if args.stage=="setup":setup(plan);return
 check_manifest(OUT/"p5/manifest.json")
 if args.stage=="gate":calibration_gate(plan);return
 root=arm(args.arm)
 if args.arm=="evaluation":
  g=arm("calibration")/"calibration_gate/manifest.json";verify_manifest(g)
  if not read(g.parent/"metrics.json")["ready_for_evaluation"]:raise RuntimeError("Evaluation withheld: independent verified calibration is insufficient")
 if args.stage=="generate":deduction.generate(root,"main",SOURCE,0,1)
 elif args.stage=="verify":deduction.verify(root,"main",SOURCE)
 elif args.stage=="extract":deduction.extract(root,"main",SOURCE)
 else:raise ValueError(args.stage)
if __name__=="__main__":main()
