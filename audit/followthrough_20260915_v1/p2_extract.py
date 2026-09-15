import argparse,collections,gzip,time
import numpy as np
from stage_support import *
from onebigjump.e1.artifacts import Journal,identity,write_once
from artifact_bridge import finish_artifact as artifact_finish
from onebigjump.models.hooks import record_residuals
from data import alignment
from extract import check_forward,token_logprobs
def main():
 import torch
 from transformers import AutoModelForCausalLM,AutoTokenizer
 p=argparse.ArgumentParser();p.add_argument("model");args=p.parse_args();modelname=args.model;plan=start("p2_pipeline")
 base=OUT/"p2_pipeline";config=read(base/(modelname+"-config.json"));layer=read(HERE/"p2-confirmatory-protocol.json")["layers"][modelname]
 source=[];records=[]
 for shard in range(4):
  mp=base/modelname/("verification-"+str(shard))/"manifest.json";check_manifest(mp);source.append(mp)
  with (mp.parent/"results.jsonl").open(encoding="utf-8") as f:records.extend(json.loads(line) for line in f)
 folder=base/modelname/"extraction";folder.mkdir(exist_ok=True)
 if (folder/"manifest.json").exists():check_manifest(folder/"manifest.json");return
 context={"source":digest(HERE/"p2_pipeline-source-manifest.json"),"verification":[digest(p) for p in source]}
 assert torch.cuda.is_available()
 model=AutoModelForCausalLM.from_pretrained(config["model_path"],torch_dtype=torch.bfloat16,local_files_only=True,attn_implementation="sdpa").to("cuda").eval()
 if model.config.model_type not in ["llama","qwen2"]:raise RuntimeError("Unvalidated architecture")
 tok=AutoTokenizer.from_pretrained(config["model_path"],local_files_only=True);checks=None
 with Journal(folder/"trajectories.jsonl",context) as journal:
  for record in records:
   tid=record["trace_id"]
   if journal.existing(tid,identity(record)) is not None:continue
   row={k:record[k] for k in ["trace_id","problem_id","role","model","exercise_group","task_family","p2_eligible","category"]}
   row["extraction_status"]="excluded_not_localized_failure"
   if record["p2_eligible"]:
    blob=Path(record["detail_path"]);assert digest(blob)==record["detail_sha256"]
    with gzip.open(blob,"rt",encoding="utf-8") as f:detail=json.load(f)
    item=detail["item"];export=detail["annotation_detail"]["export"];sample=item["sample"]
    align=alignment(item,export,tok)
    if align["formal_position"] is None:row["extraction_status"]="formal_entry_boundary_unavailable"
    else:
     inputs=torch.tensor([sample["prompt_token_ids"]+sample["completion_token_ids"]],device="cuda")
     if checks is None:checks=check_forward(model,inputs,[layer])
     with torch.inference_mode(),record_residuals(model,[layer],align["capture_positions"]) as rec:
      hidden=model.model(input_ids=inputs,use_cache=False).last_hidden_state
      probs=token_logprobs(model,hidden,inputs,128)
     lp=probs[len(sample["prompt_token_ids"])-1:];assert len(lp)==len(sample["completion_token_ids"])
     ix={p:i for i,p in enumerate(align["capture_positions"])}
     states=rec.captures[layer].numpy()[[ix[p] for p in align["positions"]]].astype(float)
     states[0]=rec.captures[layer].numpy()[ix[align["formal_position"]]]
     surprisal=np.asarray([-lp[lo:hi+1].mean() for lo,hi in align["source_token_spans_inclusive"]],dtype=float)
     labels=[o["trace_label"] for o in export["observation_rows"]];at=[i for i,x in enumerate(labels) if x=="at"];assert len(at)==1
     fstar=at[0];assert all(x=="pre" for x in labels[:fstar]) and all(x=="post" for x in labels[fstar+1:])
     assert len(states)==len(labels)+1 and np.isfinite(states).all() and np.isfinite(surprisal).all()
     path=folder/(identity(tid)+".npz")
     with path.open("wb") as f:np.savez_compressed(f,increments=np.diff(states,axis=0),surprisal=surprisal,positions=np.array(align["positions"]))
     row.update(extraction_status="extracted",states_path=str(path),states_sha256=digest(path),t_star=fstar,n_steps=len(labels),alignment=align,forward_check=checks,
      backend_logprob_mean_abs_error=float(np.mean(np.abs(lp-np.asarray(sample["generation_token_logprobs"])))))
     del hidden,inputs,states,rec
   journal.append(row,identity(record));atomic(folder/"progress.json",{"completed":len(journal.rows),"expected":len(records),"updated_unix":time.time()})
   if len(journal.rows)%25==0:print("P2 EXTRACTED",modelname,len(journal.rows),len(records),flush=True)
  rows=list(journal.rows.values())
 metrics={"all_accounted":len(rows)==len(records),"attempts":len(rows),"statuses":dict(collections.Counter(r["extraction_status"] for r in rows)),"scope":"Only reliably localized failures need new GPU states for confirmatory P2; all assigned outcomes retained in denominator."}
 mp=write_once(folder/"metrics.json",metrics)
 artifact_finish(folder,stage="prospective-P2-formal-entry-states",context=context,
  inputs=[HERE/"p2_pipeline-source-manifest.json",*source],outputs=[mp,folder/"trajectories.jsonl",folder/"trajectories.identity.json",*[Path(r["states_path"]) for r in rows if r.get("states_path")]],metrics=metrics)
if __name__=="__main__":main()
