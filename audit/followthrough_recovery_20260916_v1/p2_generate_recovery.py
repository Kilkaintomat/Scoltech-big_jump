import argparse,collections,re,time
import numpy as np
from stage_support import *
from onebigjump.e1.artifacts import Journal,identity,write_once
from artifact_bridge import finish_artifact as artifact_finish
from onebigjump.e1.generation import prompt_content
from onebigjump.e1.verification import trusted_prefix
from onebigjump.e1.spans import original_token_spans,formal_body,SourceExclusion
RECOVERY=Path(__file__).resolve().parent

def alignment_status(tok,ids,text):
 try:
  original_token_spans(tok,ids,text)
  return {"passed":True}
 except SourceExclusion as exc:
  return {"passed":False,"category":exc.category,"reason":str(exc)}

def generate(model,role,plan):
 from transformers import AutoTokenizer
 from vllm import LLM,SamplingParams
 base=OUT/"p2_pipeline";config=read(base/(model+"-config.json"));reqs=[r for r in read(base/(model+"-requests.json")) if r["role"]==role]
 folder=base/model/role/"generation";folder.mkdir(parents=True,exist_ok=True)
 if (folder/"manifest.json").exists():check_manifest(folder/"manifest.json");return
 context={"source":digest(HERE/"p2_pipeline-source-manifest.json"),"config":digest(base/(model+"-config.json")),"requests":identity(reqs),"role":role}
 if role=="evaluation":
  gate=base/model/"pilot/generation/metrics.json"
  if not read(gate)["acquisition_passed"]:raise RuntimeError("Pilot acquisition gate failed")
 with Journal(folder/"samples.jsonl",context) as journal:
  pending=[r for r in reqs if journal.existing(r["trace_id"],identity(r)) is None]
  if pending:
   tok=AutoTokenizer.from_pretrained(config["model_path"],local_files_only=True)
   llm=LLM(model=config["model_path"],tokenizer=config["model_path"],dtype="bfloat16",trust_remote_code=False,enforce_eager=True,
    gpu_memory_utilization=.85,max_model_len=plan["context_limit"],max_num_seqs=12,seed=config["seed"])
   for lo in range(0,len(pending),16):
    batch=pending[lo:lo+16];prompts=[prompt_content(r["problem"],config) for r in batch]
    ids=[tok.apply_chat_template([{"role":"user","content":p}],tokenize=True,add_generation_prompt=True) for p in prompts]
    assert all(len(x)+config["max_new_tokens"]<=plan["context_limit"] for x in ids)
    params=[SamplingParams(n=1,temperature=r["temperature"],top_p=config["top_p"],top_k=config["top_k"],max_tokens=config["max_new_tokens"],seed=r["seed"],logprobs=1,skip_special_tokens=False) for r in batch]
    t0=time.monotonic();outs=llm.generate([{"prompt_token_ids":x} for x in ids],params)
    for request,prompt,tokens,generated in zip(batch,prompts,ids,outs,strict=True):
     assert list(generated.prompt_token_ids)==tokens and len(generated.outputs)==1
     output=generated.outputs[0];completion_ids=list(output.token_ids)
     completion=tok.decode(completion_ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)
     alignment_info=alignment_status(tok,completion_ids,completion)
     lp=[float(v[t].logprob) for t,v in zip(completion_ids,output.logprobs or [],strict=True)]
     assert len(lp)==len(completion_ids) and np.isfinite(lp).all()
     row={k:v for k,v in request.items() if k!="problem"}
     row.update(model_id=config["model_id"],model_revision=config["revision"],tokenizer_revision=config["tokenizer_revision"],
      prompt_content=prompt,prompt=tok.decode(tokens,skip_special_tokens=False,clean_up_tokenization_spaces=False),
      prompt_token_ids=tokens,completion_token_ids=completion_ids,completion=completion,backend_completion=output.text,
      finish_reason=output.finish_reason,stop_reason=output.stop_reason,generation_token_logprobs=lp,
      theorem_statement=request["problem"]["statement"],trusted_context=trusted_prefix(request["problem"],config["lean"]["max_heartbeats"]),
      task_family=request["problem"]["task_family"],exercise_group=request["problem"]["exercise_group"],
      sampling={"seed":request["seed"],"top_p":config["top_p"],"top_k":config["top_k"],"max_new_tokens":config["max_new_tokens"]},
      batch_elapsed_s=time.monotonic()-t0,batch_size=len(batch),slurm_job_id=os.environ["SLURM_JOB_ID"])
     row.update(original_token_alignment=alignment_info,recovery_source_sha256=digest(RECOVERY/"source-manifest.json"))
     journal.append(row,identity(request))
    atomic(folder/"progress.json",{"completed":len(journal.rows),"expected":len(reqs),"updated_unix":time.time(),"role":role,"model":model})
    print("P2 GENERATED",model,role,len(journal.rows),len(reqs),flush=True)
  assert set(journal.rows)=={r["trace_id"] for r in reqs}
  rows=list(journal.rows.values())
 prob={r["trace_id"]:r["problem"] for r in reqs};parsed=0;parse_categories=collections.Counter()
 for row in rows:
  try:formal_body(row["completion"],prob[row["trace_id"]]["statement"],trusted_prefix(prob[row["trace_id"]],config["lean"]["max_heartbeats"]));parsed+=1
  except SourceExclusion as e:parse_categories[e.category]+=1
 metrics={"attempts":len(rows),"all_accounted":True,"exact_original_token_reconstruction":all(r.get("original_token_alignment",{"passed":True})["passed"] for r in rows),"alignment_exclusions":sum(not r.get("original_token_alignment",{"passed":True})["passed"] for r in rows),"logprob_alignment":True,
  "parseable_declarations":parsed,"parse_exclusions":dict(parse_categories),"acquisition_passed":len(rows)==len(reqs) and parsed>=1,
  "semantic_success_not_used_for_gate":True,"finish_reasons":dict(collections.Counter(r["finish_reason"] for r in rows))}
 p=write_once(folder/"metrics.json",metrics)
 artifact_finish(folder,stage="prospective-P2-generation",context=context,
  inputs=[RECOVERY/"source-manifest.json",RECOVERY/"AMENDMENT.md",HERE/"p2_pipeline-source-manifest.json",base/"manifest.json",base/(model+"-requests.json"),base/(model+"-config.json")],
  outputs=[p,folder/"samples.jsonl",folder/"samples.identity.json"],metrics=metrics)
def main():
 p=argparse.ArgumentParser();p.add_argument("model");p.add_argument("role");args=p.parse_args()
 plan=start("p2_pipeline");check_manifest(OUT/"p2_pipeline/manifest.json");generate(args.model,args.role,plan)

