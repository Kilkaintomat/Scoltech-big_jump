"""Freeze input partition and validate the extraction math on a small local CPU model."""
import json,os
from pathlib import Path
from data import *

def main():
    import numpy as np,torch
    from transformers import Qwen2Config,Qwen2ForCausalLM
    from extract import check_forward,token_logprobs
    from onebigjump.models.hooks import record_residuals
    torch.manual_seed(173)
    tiny=Qwen2ForCausalLM(Qwen2Config(vocab_size=101,hidden_size=32,intermediate_size=64,num_hidden_layers=4,num_attention_heads=4,num_key_value_heads=2)).eval()
    inputs=torch.randint(0,101,(1,257))
    checks=check_forward(tiny,inputs,[0,1,2])
    with torch.inference_mode():
        hidden=tiny.model(input_ids=inputs,use_cache=False).last_hidden_state
        a=token_logprobs(tiny,hidden,inputs,17);b=token_logprobs(tiny,hidden,inputs,128)
    checks["chunk_boundaries"]={"passed":bool(np.allclose(a,b,atol=1e-6,rtol=1e-6))}
    indexes=[0,17,128,256]
    with torch.inference_mode(),record_residuals(tiny,[0,1,2],indexes) as rec:
        out=tiny.model(input_ids=inputs,use_cache=False,output_hidden_states=True)
    checks["actual_requested_positions"]={"passed":all(torch.allclose(rec.captures[k],out.hidden_states[k+1][0,indexes]) for k in [0,1,2])}
    if not all(x["passed"] for x in checks.values()):raise RuntimeError("CPU extraction gate failed")
    meta=read(SEG/"inputs/manifest.json")
    plan={"ready":[],"remaining":[],"models":{},"counts":{},"ready_manifests":{}}
    for task,shard in meta["shards"].items():
        p=SEG/"shards"/f"{int(task):03d}"/"manifest.json"
        ready=p.exists() and read(p)["metrics"]["all_accounted"]
        plan["ready" if ready else "remaining"].append(int(task));plan["models"][task]=shard["model"];plan["counts"][task]=shard["count"]
        if ready:plan["ready_manifests"][str(p)]=digest(p)
    atomic(RUN/"plan.json",plan)
    # Check original-token boundaries and label absorption on real completed observations.
    from transformers import AutoTokenizer
    from measure_analyze import labels
    examples={}
    for model in MODELS:
        t=next(t for t in plan["ready"] if plan["models"][str(t)]==model)
        tokenizer=AutoTokenizer.from_pretrained(meta["shards"][str(t)]["model_path"],local_files_only=True)
        seen=set()
        for item,row,path in shard_items(t):
            if not row.get("ready_for_activation_extraction") or row["status"]!="annotated":continue
            category=row["old_category"]
            if category in seen or (category!="verified" and not row["p2_eligible"]):continue
            export=load_export(item,row,path);a=alignment(item,export,tokenizer);labels(export,row)
            assert len(a["source_token_spans_inclusive"])==len(a["positions"])-1
            seen.add(category)
            if len(seen)==2:break
        if seen!={"verified","localized_tactic_failure"}:raise ValueError("missing real label/position regression category")
        examples[model]=sorted(seen)
    checks["real_original_positions_and_absorption"]={"passed":True,"categories":examples}
    for model in MODELS:
        p=REPO/"runs/lean_reverification_20260913_local"/model/"main/protocol.json"
        if digest(p)!=meta["origins"][model]["protocol"]:raise ValueError("original protocol changed")
        atomic(RUN/"protocols"/(model+".json"),read(p))
    old=read(SEG/"source-manifest.json")
    files={**old["files"],**{str(p):digest(p) for p in AUDIT.iterdir() if p.suffix in [".py",".sbatch"]}}
    files[str(REPO/"audit/revision_2026_09_13/snapshots/lean-io-v9/scripts/slurm/common.sh")]=digest(REPO/"audit/revision_2026_09_13/snapshots/lean-io-v9/scripts/slurm/common.sh")
    source={"files":files,"segmentation_inputs_sha256":digest(SEG/"inputs/manifest.json"),"parent_source":digest(SEG/"source-manifest.json"),
            "source_control":{"git_commit":os.environ.get("ONEBIGJUMP_GIT_COMMIT"),"dirty":bool(os.environ.get("ONEBIGJUMP_GIT_STATUS"))},
            "environment":environment(),"cpu_checks":checks}
    atomic(RUN/"source-manifest.json",source)
    finish(RUN/"preflight",{"passed":True,"checks":checks,"ready_tasks":plan["ready"],"remaining_tasks":plan["remaining"]},
           [SEG/"inputs/manifest.json"],[RUN/"plan.json",RUN/"config.json",RUN/"source-manifest.json",*[RUN/"protocols"/(m+".json") for m in MODELS]])
    print("PREPARED",json.dumps(plan),flush=True)
if __name__=="__main__":main()
