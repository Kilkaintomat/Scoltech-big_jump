from pathlib import Path
import json,copy,os
from transformers import AutoTokenizer
from segmenter_v2 import align_original
from onebigjump.e1.spans import original_token_spans
from export_observations import export
O=Path(__file__).parent;ROOT=O.parents[2]
read=lambda p:json.loads(p.read_text(encoding="utf-8"))
protocol=read(ROOT/'runs/lean_reverification_20260913_local/goedel/main/protocol.json')
tok=AutoTokenizer.from_pretrained(protocol["model_path"],local_files_only=True)
checks={}
def sample(text):
 ids=tok.encode(text,add_special_tokens=False)
 return {"completion":text,"completion_token_ids":ids,"prompt_token_ids":[1]}
def result(body,ends):
 return {"source":"by"+body,"points":[{"index":i,"end_char":end+2,"trace_label":"verified_trace","execution_status":"observed"} for i,end in enumerate(ends)]}
text="exact hypothesis"
x=sample(text);offsets=original_token_spans(tok,x["completion_token_ids"],text)
boundary=next(a+1 for a,b in offsets if b-a>=2 and text[a:b].strip())
r=result(text,[boundary,len(text)]);z=align_original(r,tok,x,0)
checks["reject_boundary_inside_code_token"]=len(z["rejected"])==1 and len(z["observations"])==1
x=sample("h₁ α 😀");r=result(x["completion"],[len(x["completion"])])
checks["unicode_original_byte_pieces"]=len(align_original(r,tok,x,0)["observations"])==1
y=copy.deepcopy(x);y["completion_token_ids"]=y["completion_token_ids"][:-1]
try:align_original(r,tok,y,0);checks["tampered_token_ids_rejected"]=False
except ValueError:checks["tampered_token_ids_rejected"]=True
try:align_original(result("different",[3]),tok,x,0);checks["changed_body_rejected"]=False
except ValueError:checks["changed_body_rejected"]=True
try:align_original(r,tok,x,-1);checks["negative_source_offset_rejected"]=False
except ValueError:checks["negative_source_offset_rejected"]=True
x=sample("x   ");r=result(x["completion"],[2,3,4])
z=align_original(r,tok,x,0)
checks["whitespace_boundaries_do_not_duplicate_tokens"]=len(z["observations"])==len(set(z["positions"]))-1 and not z["rejected"]
r=read(O/'validation/case--cases_three_steps.json')
checks["branches_are_distinct"]=len({tuple(p["branch_path"]) for p in r["points"]})==2
checks["same_branch_steps_stay_together"]=r["points"][0]["branch_path"]==r["points"][1]["branch_path"] and r["points"][2]["branch_path"]==r["points"][3]["branch_path"]
r=read(O/'validation/case--failure_after_completion.json')
checks["no_goal_failure_is_still_failure"]=r["points"][-1]["trace_label"]=="at"
labels=read(O/"sample.json");samples=read(O/"frozen-generations-small.json")
label=labels[8];s=next(x for x in samples if x["model"]=="goedel" and x["trace_id"]==label["trace_id"])
r=read(O/'validation/case--saved_08_goedel.json')
e=export(r,s,tok,label["body_start"])
wrong=copy.deepcopy(s);wrong["completion"]+="x"
try:export(r,wrong,tok,label["body_start"]);checks["export_rejects_different_answer"]=False
except ValueError:checks["export_rejects_different_answer"]=True
checks["export_reuses_original_positions"]=e["positions_with_original_prompt_baseline"]==r["token_alignment"]["positions"]
checks["formal_entry_is_later_than_prompt"]=e["optional_formal_entry_baseline"]["token_position"]>r["token_alignment"]["prompt_position"]
(O/"example-export.json").write_text(json.dumps(e,ensure_ascii=False,indent=2),encoding="utf-8")
out={"job":os.environ["SLURM_JOB_ID"],"checks":checks,"passed":all(checks.values()),"n_checks":len(checks)}
(O/"contract-checks.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
print(json.dumps(out),flush=True)
if not out["passed"]:raise RuntimeError("contract checks failed")
