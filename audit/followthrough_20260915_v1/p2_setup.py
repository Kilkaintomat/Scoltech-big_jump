import collections,re
from stage_support import *
from onebigjump.e1.artifacts import identity
from onebigjump.e1.generation import prompt_content
from onebigjump.models.generation import assert_tokenizer_roundtrips
def main():
 plan=start("p2_pipeline");protocol=read(HERE/"p2-confirmatory-protocol.json")
 check_manifest(OUT/"new_tasks/manifest.json")
 candidates=read(OUT/"new_tasks/candidates.json");results={};upstream=[]
 for shard in range(4):
  mp=OUT/"new_tasks"/("reference-v2-shard-"+str(shard))/"manifest.json";check_manifest(mp);upstream.append(mp)
  with (mp.parent/"results.jsonl").open(encoding="utf-8") as f:
   for line in f:
    r=json.loads(line);assert r["source_index"] not in results;results[r["source_index"]]=r
 assert set(results)=={p["source_index"] for p in candidates}
 compatible=[p for p in candidates if results[p["source_index"]]["category"]=="reference_verified"]
 groups=sorted({p["exercise_group"] for p in compatible},key=lambda g:identity([protocol["seed"],g]))
 if len(groups)<protocol["technical_pilot_groups"]+protocol["minimum_independent_groups"]:
  raise RuntimeError("Not enough independently grouped compatible problems; no model generation authorized by this gate")
 pilot=set(groups[:protocol["technical_pilot_groups"]])
 problems=[]
 for p in compatible:
  clean={k:p[k] for k in ["problem_id","statement","directives","benchmark","task_family","exercise_group","source_index","source_commit"]}
  clean["original_problem_id"]=clean["problem_id"];clean["problem_id"]="proofnet-"+str(p["source_index"])+":"+clean["problem_id"]
  clean.update(eligible=True,role="pilot" if p["exercise_group"] in pilot else "evaluation")
  assert not any("proof" in k for k in clean if k not in ["benchmark"])
  problems.append(clean)
 assert not {p["exercise_group"] for p in problems if p["role"]=="pilot"} & {p["exercise_group"] for p in problems if p["role"]=="evaluation"}
 folder=OUT/"p2_pipeline";folder.mkdir(exist_ok=True);outputs=[];configs={};requests={};checks={}
 from transformers import AutoTokenizer
 from onebigjump.e1.stages import check_model
 for model in protocol["models"]:
  config=read(STATES/"protocols"/(model+".json"))
  config.update(seed=protocol["seed"],temperatures=[protocol["temperature"]],main_attempts=protocol["attempts_per_task"],max_new_tokens=protocol["max_new_tokens"])
  check_model(ROOT/"runs/lean_reverification_20260913_local"/model,config)
  tok=AutoTokenizer.from_pretrained(config["model_path"],local_files_only=True);assert_tokenizer_roundtrips(tok,config["model_id"])
  current=[];excluded=[]
  for p in problems:
   prompt=prompt_content(p,config)
   ids=tok.apply_chat_template([{"role":"user","content":prompt}],tokenize=True,add_generation_prompt=True)
   if len(ids)+config["max_new_tokens"]>plan["context_limit"]:
    excluded.append({"problem_id":p["problem_id"],"reason":"prompt_context_limit","prompt_tokens":len(ids)});continue
   for attempt in range(protocol["attempts_per_task"]):
    tid=f'{p["role"]}:{p["problem_id"]}:T{protocol["temperature"]:.1f}:a{attempt:02d}'
    current.append({"trace_id":tid,"problem_id":p["problem_id"],"problem":p,"temperature":protocol["temperature"],"attempt_index":attempt,
     "seed":int(identity([protocol["seed"],model,tid])[:8],16)%(2**31-1),"role":p["role"]})
  assert current and all(r["problem"]["role"]==r["role"] for r in current)
  for suffix,value in [("config",config),("requests",current),("context-exclusions",excluded)]:
   path=folder/(model+"-"+suffix+".json");atomic(path,value);outputs.append(path)
  checks[model]={"planned_attempts":len(current),"pilot_attempts":sum(r["role"]=="pilot" for r in current),"evaluation_attempts":sum(r["role"]=="evaluation" for r in current),"context_exclusions":len(excluded)}
 # Prospective representative rule is independent of maxima, surprisal and error position.
 atomic(folder/"task-population.json",problems);outputs.append(folder/"task-population.json")
 finish("p2_pipeline",{"preflight_passed":True,"candidate_problems":len(candidates),"reference_categories":dict(collections.Counter(r["category"] for r in results.values())),
  "compatible_problems":len(compatible),"compatible_exercise_groups":len(groups),"technical_pilot_groups":len(pilot),"evaluation_groups":len(groups)-len(pilot),
  "models":checks,"reference_proofs_in_model_prompts":False,"generation_calls":0,
  "protocol_sha256":digest(HERE/"p2-confirmatory-protocol.json")},
  [*upstream,OUT/"new_tasks/manifest.json",HERE/"p2-confirmatory-protocol.json"],outputs)
 print("P2 PROSPECTIVE PREFLIGHT COMPLETE",json.dumps(checks),flush=True)
if __name__=="__main__":main()
