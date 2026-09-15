"""Preflight: unchanged checker, fresh technical tasks, fixed format gate, tokenizer budget."""
from pathlib import Path
import ast,os
from transformers import AutoTokenizer
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,identity
from onebigjump.readiness.deduction import population,requests,prompt,check
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
root=base/"runs/development_20260913_exactlength/deduction"
old=base/"audit/revision_2026_09_13/snapshots/lean-local-toolchain-v7/src/onebigjump/readiness/deduction.py"
def fn(path,name):
 text=path.read_text(encoding="utf-8")
 node=next(x for x in ast.parse(text).body if isinstance(x,ast.FunctionDef) and x.name==name)
 return ast.get_source_segment(text,node)
for name in ["check","make_problem","requests","generate","verify","extract","measure","analyze","gate"]:
 assert fn(old,name)==fn(source.parent/"src/onebigjump/readiness/deduction.py",name),name
population(root,source)
problems=read_json(root/"inputs/problems.json")
old_problems=read_json(base/"runs/development_20260913/deduction/inputs/problems.json")
def content(p):return identity({k:v for k,v in p.items() if k not in ["problem_id","role"]})
assert not ({content(p) for p in problems}&{content(p) for p in old_problems})
cfg=read_json(root/"protocol.json");planned=requests(root,"pilot")
info=read_json(Path(cfg["model_root"])/"model.json")
tokenizer=AutoTokenizer.from_pretrained(info["model_path"],local_files_only=True)
records=[]
for p in problems:
 text=prompt(p,cfg["prompt_version"])
 ids=tokenizer.apply_chat_template([{"role":"user","content":text}],tokenize=True,add_generation_prompt=True)
 assert len(ids)+cfg["max_new_tokens"]<=4096
 gold="\n".join(f"{i}. Mira is {fact}." for i,fact in enumerate(p["gold_chain"],1))+"\nAnswer: true"
 assert check(gold,p)["verified"]
 repeat="\n".join(f"{i}. Mira is {fact}." for i,fact in enumerate([p["initial"],*p["gold_chain"][:-1]],1))+"\nAnswer: true"
 assert check(repeat,p)["format_eligible"] and check(repeat,p)["t_star"]==0 and not check(repeat,p)["verified"]
 assert not check(gold+"\nMira is "+p["goal"]+".",p)["format_eligible"]
 records.append({"problem_id":p["problem_id"],"prompt":text,"input_tokens":len(ids),"length":p["length"]})
assert cfg["format_gate"]==0.90 and cfg["allow_main"] is False
metrics={"passed":True,"tasks":len(problems),"planned_attempts":len(planned),"checker_identical":True,
 "generation_and_analysis_identical":True,"fresh_problem_contents":True,"gold_proofs_passed":len(problems),
 "format_gate":cfg["format_gate"],"allow_main":cfg["allow_main"],
 "max_input_tokens":max(r["input_tokens"] for r in records),"prompt_version":cfg["prompt_version"]}
out=root.parent/"validation"
a=write_once(out/"metrics.json",metrics);b=write_once(out/"prompts.json",records)
finish(out,stage="exact-length-prompt-preflight",context={"source":digest(source)},
 inputs=[source,Path(__file__),old,root/"protocol.json",root/"inputs/manifest.json",Path(cfg["model_root"])/"manifest.json"],
 outputs=[a,b],metrics=metrics)
print("EXACT_LENGTH_PREFLIGHT",metrics,flush=True)
