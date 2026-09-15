"""Isolated one-GPU timings; original science jobs and artifacts remain untouched."""
import gc,io,json,os,time
from pathlib import Path
import numpy as np
from data import REPO,RUN as STATES,MODELS,read,atomic,digest,environment,check_source,check_manifest,shard_items,load_export,alignment
from extract import check_forward,token_logprobs
from repair_support import check_repair,validate_architecture
from onebigjump.e1.stages import check_model
from onebigjump.models.hooks import record_residuals
HERE=REPO/"audit/segmentation_extraction_repair_20260914_v2"
QUALITY=REPO/"runs/segmentation_quality_20260914_v1"
OUT=REPO/"runs/segmentation_extraction_repair_20260914_v2"/("profile-"+os.environ.get("SLURM_JOB_ID","unallocated"))
def main():
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    if not torch.cuda.is_available() or "SLURM_JOB_ID" not in os.environ:raise RuntimeError("Slurm GPU allocation required")
    OUT.mkdir(parents=True,exist_ok=False);check_source();check_repair()
    source=read(HERE/"source-manifest.json")
    for name,h in source["files"].items():
        if digest(name)!=h:raise ValueError("followup source changed")
    check_manifest(QUALITY/"manifest.json")
    if read(QUALITY/"metrics.json")["gpu_adapter_blockers"]:raise RuntimeError("quality audit blocked adapter")
    config=read(STATES/"config.json")
    plan=read(REPO/"audit/segmentation_quality_20260914_v1/plan.json")
    start=time.monotonic();deadline=start+22*60;metrics={"models":{},"scope":"timings only; not scientific measurements","generation_calls":0,
        "gpu":torch.cuda.get_device_name(0),"allocated_gpu_count":torch.cuda.device_count(),"planned_minutes":plan["profile"]["time_limit_minutes"]}
    inputs=[HERE/"source-manifest.json",REPO/"audit/segmentation_quality_20260914_v1/plan.json",STATES/"source-manifest.json",QUALITY/"manifest.json"]
    def save():
        metrics["elapsed_seconds"]=time.monotonic()-start
        atomic(OUT/"metrics.json",metrics)
        atomic(OUT/"manifest.json",{"config":plan,"source_control":read(STATES/"source-manifest.json")["source_control"],
             "environment":environment(),"inputs":{str(p):digest(p) for p in inputs},
             "outputs":{str(OUT/"metrics.json"):digest(OUT/"metrics.json")}})
    for name in MODELS:
        if time.monotonic()>deadline:break
        selection_path=QUALITY/name/"profile-selection.json";check_manifest(QUALITY/name/"manifest.json");inputs.append(selection_path)
        selection=read(selection_path);wanted={x["trace_id"]:x for x in selection};requests={}
        t=time.monotonic()
        for task in sorted({x["task"] for x in selection}):
            for item,annotation,path in shard_items(task):
                if item["trace_id"] in wanted:requests[item["trace_id"]]=(item,annotation,path)
        if set(requests)!=set(wanted):raise ValueError("incomplete profiling selection")
        mc=read(STATES/"protocols"/(name+".json"));layers=mc["layers"]
        preflight=time.monotonic();check_model(REPO/"runs/lean_reverification_20260913_local"/name,mc)
        checked=time.monotonic()
        model=AutoModelForCausalLM.from_pretrained(mc["model_path"],torch_dtype=torch.bfloat16,local_files_only=True,
                    attn_implementation="sdpa").to("cuda").eval()
        validate_architecture(model)
        tokenizer=AutoTokenizer.from_pretrained(mc["model_path"],local_files_only=True);torch.cuda.synchronize()
        model_result={"input_seconds":preflight-t,"weight_verification_seconds":checked-preflight,"load_seconds":time.monotonic()-checked,
                      "model_revision":mc.get("model_revision"),"samples":[]}
        metrics["models"][name]=model_result;checked_forward=False;save()
        for selected in selection:
            if time.monotonic()>deadline:break
            item,annotation,path=requests[selected["trace_id"]];s=item["sample"];t=time.monotonic()
            export=load_export(item,annotation,path);align=alignment(item,export,tokenizer)
            ids=torch.tensor([s["prompt_token_ids"]+s["completion_token_ids"]],device="cuda")
            if not checked_forward:
                model_result["forward_check"]=check_forward(model,ids,layers);checked_forward=True
            torch.cuda.synchronize();alignment_seconds=time.monotonic()-t;torch.cuda.reset_peak_memory_stats()
            t=time.monotonic()
            try:
                with torch.inference_mode(),record_residuals(model,layers,align["capture_positions"]) as rec:
                    hidden=model.model(input_ids=ids,use_cache=False).last_hidden_state
                    torch.cuda.synchronize();after_transformer=time.monotonic()
                    lp=token_logprobs(model,hidden,ids,config["logit_chunk_tokens"])
                    torch.cuda.synchronize();after_head=time.monotonic()
                arrays={str(layer):rec.captures[layer].numpy() for layer in layers};arrays["logprobs"]=lp
                if not all(np.isfinite(a).all() for a in arrays.values()):raise RuntimeError("nonfinite profile output")
                buf=io.BytesIO();np.savez_compressed(buf,**arrays)
                encode_seconds=time.monotonic()-after_head
                result={**selected,"status":"ok","alignment_and_initial_check_seconds":alignment_seconds,
                        "transformer_seconds":after_transformer-t,"head_seconds":after_head-after_transformer,
                        "forward_seconds":after_head-t,"compress_seconds":encode_seconds,"compressed_bytes":buf.tell(),
                        "peak_allocated_bytes":torch.cuda.max_memory_allocated(),"peak_reserved_bytes":torch.cuda.max_memory_reserved(),
                        "observations":len(export["observation_rows"]),"capture_positions":len(align["capture_positions"]),
                        "tokens_per_second":ids.shape[1]/(after_head-t)}
                del hidden,rec,lp,arrays,buf
            except torch.cuda.OutOfMemoryError as e:
                result={**selected,"status":"cuda_out_of_memory","message":str(e)[:500]}
                gc.collect();torch.cuda.empty_cache()
            model_result["samples"].append(result);save();print("PROFILE",name,selected["trace_id"],result["status"],flush=True)
            del ids
        del model,tokenizer,requests;gc.collect();torch.cuda.empty_cache();save()
    metrics["all_selected_complete"]=all(name in metrics["models"] and
       len(metrics["models"][name]["samples"])==len(read(QUALITY/name/"profile-selection.json")) for name in MODELS)
    metrics["deadline_reached"]=time.monotonic()>deadline;save()
    print("PROFILE DONE",str(OUT),flush=True)
if __name__=="__main__":main()
