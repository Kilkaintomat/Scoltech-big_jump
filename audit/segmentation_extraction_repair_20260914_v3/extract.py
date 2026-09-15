"""One original-ID model forward per usable answer, with chunked vocabulary projection."""
import argparse,collections,os,time
from pathlib import Path
import numpy as np
from data import *
from onebigjump.e1.artifacts import Journal
from onebigjump.models.hooks import record_residuals
from onebigjump.e1.stages import check_model
from repair_support import check_repair,validate_architecture,backend_comparison

def token_logprobs(model,hidden,inputs,chunk=128):
    import torch
    result=[]
    for lo in range(0,hidden.shape[1]-1,chunk):
        hi=min(lo+chunk,hidden.shape[1]-1)
        logits=model.lm_head(hidden[:,lo:hi])[0].float()
        target=inputs[0,lo+1:hi+1]
        lp=logits.gather(1,target[:,None]).squeeze(1)-logits.logsumexp(-1)
        result.append(lp.cpu().numpy())
    return np.concatenate(result)

def check_forward(model,inputs,layers):
    import torch
    probe=inputs[:,:min(inputs.shape[1],256)]
    pos=sorted(set([0,probe.shape[1]//2,probe.shape[1]-1]))
    with torch.inference_mode(),record_residuals(model,layers,pos) as rec:
        hidden=model.model(input_ids=probe,use_cache=False).last_hidden_state
        lp=token_logprobs(model,hidden,probe)
    with torch.inference_mode():
        ref=model(input_ids=probe,use_cache=False,output_hidden_states=True)
    checks={}
    for layer in layers:
        target=ref.hidden_states[layer+1][0,pos].float().cpu()
        err=float((target-rec.captures[layer]).abs().max())
        checks[str(layer)]={"max_abs_error":err,"passed":bool(torch.allclose(target,rec.captures[layer],atol=1e-5,rtol=1e-5))}
    logits=ref.logits[0,:-1].float();target=probe[0,1:]
    actual=(logits.gather(1,target[:,None]).squeeze(1)-logits.logsumexp(-1)).cpu().numpy()
    checks["chunked_lm_head"]={"max_abs_error":float(np.max(np.abs(actual-lp))),"passed":bool(np.allclose(actual,lp,atol=1e-4,rtol=1e-4))}
    if not all(c["passed"] for c in checks.values()):raise RuntimeError("independent forward check failed: "+str(checks))
    return checks

def main():
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    p=argparse.ArgumentParser();p.add_argument("--model",choices=MODELS,required=True);p.add_argument("--wave",choices=["ready","remaining","all"],required=True)
    args=p.parse_args();repair=check_repair();source=check_source();config=read(RUN/"config.json");plan=read(RUN/"plan.json")
    tasks=sorted(int(t) for t,m in plan["models"].items() if m==args.model) if args.wave=="all" else [t for t in plan[args.wave] if plan["models"][str(t)]==args.model]
    if args.wave in ["remaining","all"]:
        if not check_manifest(SEG/"summary/manifest.json")["metrics"]["all_accounted"]:raise ValueError("segmentation incomplete")
    model_config=read(RUN/"protocols"/(args.model+".json"))
    check_model(REPO/"runs/lean_reverification_20260913_local"/args.model,model_config)
    if not torch.cuda.is_available():raise RuntimeError("GPU allocation required")
    model=AutoModelForCausalLM.from_pretrained(model_config["model_path"],torch_dtype=torch.bfloat16,
        local_files_only=True,attn_implementation="sdpa").to("cuda").eval()
    validate_architecture(model)
    tokenizer=AutoTokenizer.from_pretrained(model_config["model_path"],local_files_only=True)
    layers=model_config["layers"];checks=None;started=time.monotonic()
    for task in tasks:
        out=RUN/"shards"/f"{task:03d}";out.mkdir(parents=True,exist_ok=True)
        upstream=SEG/"shards"/f"{task:03d}"/"manifest.json"
        context={"repair_source":digest(repair),"source":digest(RUN/"source-manifest.json"),"config":digest(RUN/"config.json"),"upstream":digest(upstream),"task":task}
        with Journal(out/"trajectories.jsonl",context) as journal:
            for item,annotation,blob_path in shard_items(task):
                rid=item["trace_id"];request=identity([identity(item),annotation["row_sha256"]])
                previous=journal.existing(rid,request)
                if previous is not None:
                    if previous.get("states_path") and digest(previous["states_path"])!=previous["states_sha256"]:raise ValueError("saved states corrupt")
                    continue
                row={"trace_id":rid,"model":args.model,"problem_id":item["problem_id"],"sample_meta":{k:item["sample"][k] for k in ["temperature","role","model_id","model_revision","tokenizer_revision"]},
                     "annotation":annotation,"annotation_artifact":str(blob_path),"extraction_status":"excluded_by_annotation",
                     "input_sha256":identity(item),"execution":{"job":os.environ["SLURM_JOB_ID"],"host":os.uname().nodename,"repair_source":digest(repair)}}
                if annotation.get("ready_for_activation_extraction") and annotation["status"]=="annotated":
                    export=load_export(item,annotation,blob_path);align=alignment(item,export,tokenizer);s=item["sample"]
                    inputs=torch.tensor([s["prompt_token_ids"]+s["completion_token_ids"]],device="cuda")
                    if checks is None:
                        checks=check_forward(model,inputs,layers)
                        atomic(RUN/(args.model+"-"+args.wave+"-forward-check.json"),checks)
                    with torch.inference_mode(),record_residuals(model,layers,align["capture_positions"]) as rec:
                        hidden=model.model(input_ids=inputs,use_cache=False).last_hidden_state
                        logprobs=token_logprobs(model,hidden,inputs,config["logit_chunk_tokens"])
                    completion_lp=logprobs[len(s["prompt_token_ids"])-1:]
                    if len(completion_lp)!=len(s["completion_token_ids"]):raise ValueError("probability alignment")
                    index={pos:i for i,pos in enumerate(align["capture_positions"])}
                    arrays={f"states_{layer}":rec.captures[layer].numpy()[[index[p] for p in align["positions"]]] for layer in layers}
                    if align["formal_position"] is not None:
                        for layer in layers:arrays[f"formal_state_{layer}"]=rec.captures[layer].numpy()[index[align["formal_position"]]]
                    arrays["completion_logprobs"]=completion_lp
                    arrays["surprisal"]=np.asarray([-completion_lp[lo:hi+1].mean() for lo,hi in align["source_token_spans_inclusive"]],dtype=np.float64)
                    arrays["positions"]=np.asarray(align["positions"],dtype=np.int64)
                    if not all(np.isfinite(a).all() for a in arrays.values()):raise ValueError("nonfinite measurements")
                    artifact=out/"states"/(identity(rid)+".npz");artifact.parent.mkdir(exist_ok=True);tmp=artifact.with_suffix(".tmp")
                    with tmp.open("wb") as f:np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno())
                    tmp.replace(artifact)
                    comparison=backend_comparison(s,completion_lp)
                    row.update(extraction_status="extracted",states_path=str(artifact),states_sha256=digest(artifact),
                               alignment=align,n_steps=len(export["observation_rows"]),p2_eligible=annotation["p2_eligible"],
                               forward_check=checks,**comparison)
                    del hidden,inputs,arrays,rec
                journal.append(row,request)
                atomic(out/"progress.json",{"completed":len(journal.rows),"expected":plan["counts"][str(task)],"last_trace":rid,
                    "last_status":row["extraction_status"],"job":os.environ["SLURM_JOB_ID"],"elapsed_s":time.monotonic()-started,"updated_unix":time.time()})
                if len(journal.rows)%25==0:print("progress",task,len(journal.rows),row["extraction_status"],flush=True)
            values=list(journal.rows.values())
        if len(values)!=plan["counts"][str(task)]:raise ValueError("extraction accounting mismatch")
        metrics={"attempts":len(values),"all_accounted":True,"statuses":dict(collections.Counter(r["extraction_status"] for r in values)),
                 "model":args.model,"task":task,"generation_calls":0,"implementation_source_manifest":str(repair),"implementation_source_sha256":digest(repair)}
        finish(out,metrics,[repair,upstream,RUN/"source-manifest.json"],[out/"trajectories.jsonl",out/"trajectories.identity.json",
            *[Path(r["states_path"]) for r in values if r.get("states_path")]])
    print("wave complete",args.model,args.wave,tasks,flush=True)
if __name__=="__main__":main()
