"""Refit transforms and repeat the original statistical methods using saved, prefix-trimmed states."""
import collections,gzip,json,os,time
from pathlib import Path
import numpy as np
import pandas as pd
from data import checked_rows,check_manifest,SEG
from support import *
from policy import slice_states,fit_calibration,validate_splits
from onebigjump.e1.measurement import transformed_norms
from onebigjump.e1.main_analysis import analyze_cell
from onebigjump.e1.analysis import finite_json
from onebigjump.experiments.dataset import COLUMNS,validate_table
from controls import trials,describe,positional_null
def table_rows(record,values,config,layer):
    L=len(record["states"])-1;star=record["star"]
    if len(record["surprisal"])!=L:raise ValueError("surprisal length")
    rows=[]
    for stat,scores in values.items():
        if len(scores)!=L:raise ValueError("deviation length")
        for t,z in enumerate(scores):
            valid=star is None or t<star
            rows.append({"trace_id":record["trace_id"],"prompt_id":record["problem_id"],"model":config["model_id"],
             "layer":layer,"statistic":stat,"t":t,"L":L,"z":float(z),"valid":valid,"t_star":star,
             "outcome":"verified" if star is None else "refuted","surprisal":float(record["surprisal"][t]),
             "status":"ok" if valid else "error" if t==star else "unreached","temperature":record["temperature"],
             "task_family":record["task_family"],"role":record["role"],"category":record["category"],"primary_eligible":True})
    return rows
def measure():
    folder=OUT/"measurement"
    if (folder/"manifest.json").exists():
        check_manifest(folder/"manifest.json");return folder/"deviations.parquet"
    config=read(STATES/"protocols/kimina.json");layer=config["layers"][1]
    input_plan=read(STATES/"plan.json");masks={r["trace_id"]:r for r in read(OUT/"preflight/masks.json")}
    problems={r["problem_id"]:r for r in read(REPO/"runs/lean_reverification_20260913_local/kimina/inputs/problems.json")}
    selected=[];seen=set();upstreams=[];attempts=0;excluded=collections.Counter();started=time.monotonic()
    folder.mkdir(parents=True,exist_ok=True)
    for task in sorted(int(t) for t,m in input_plan["models"].items() if m=="kimina"):
        src=STATES/"shards"/f"{task:03d}";manifest=src/"manifest.json";check_manifest(manifest);upstreams.append(manifest)
        records=list(checked_rows(src/"trajectories.jsonl",read(src/"trajectories.identity.json")))
        if len(records)!=input_plan["counts"][str(task)]:raise ValueError("incomplete GPU shard")
        for row in records:
            attempts+=1;rid=row["trace_id"]
            if rid in seen:raise ValueError("duplicate state trace")
            seen.add(rid)
            if rid not in masks:
                excluded[row["extraction_status"]]+=1;continue
            mask=masks[rid]
            if row["extraction_status"]!="extracted":raise ValueError("accepted source missing saved states")
            if row["annotation"]["row_sha256"]!=mask["annotation_sha256"] or row["input_sha256"]!=mask["input_sha256"]:
                raise ValueError("GPU/source annotation mismatch")
            if digest(row["annotation_artifact"])!=mask["artifact_sha256"]:raise ValueError("changed source annotation")
            if row["sample_meta"]["role"]!=mask["role"] or row["sample_meta"]["temperature"]!=mask["temperature"]:
                raise ValueError("role/temperature changed")
            if problems[mask["problem_id"]]["role"]!=mask["role"]:raise ValueError("original task split changed")
            with np.load(row["states_path"],allow_pickle=False) as data:
                original_states=data[f"states_{layer}"];original_surprisal=data["surprisal"]
            states,surprisal=slice_states(original_states,original_surprisal,mask["original_L"],mask["keep_steps"])
            if mask["star"] is not None and mask["removed_steps"]:raise ValueError("refuted proof changed")
            selected.append({**mask,"states":states,"surprisal":surprisal,"task_family":problems[mask["problem_id"]]["task_family"]})
        atomic(folder/"progress.json",{"stage":"loading","shard":task,"attempts":attempts,"elapsed_seconds":time.monotonic()-started})
        print("LOADED",task,attempts,flush=True)
    if attempts!=6672 or {r["trace_id"] for r in selected}!=set(masks):raise ValueError("source population changed")
    validate_splits(selected);rows=[];diagnostics=[];outputs=[]
    for temperature in config["temperatures"]:
        group=[r for r in selected if r["temperature"]==temperature]
        atomic(folder/"progress.json",{"stage":"refit","temperature":temperature,"elapsed_seconds":time.monotonic()-started})
        fit,info=fit_calibration(group,config["whitening"]);info.update(temperature=temperature,layer=layer)
        diagnostics.append(info)
        if fit is not None:
            path=folder/f"transform-T{temperature}-layer{layer}.npz";np.savez_compressed(path,**fit);outputs.append(path)
        for i,r in enumerate(group):
            rows.extend(table_rows(r,transformed_norms(r["states"],fit),config,layer))
            if i%250==0:atomic(folder/"progress.json",{"stage":"norms","temperature":temperature,"traces":i,"elapsed_seconds":time.monotonic()-started})
        print("REFIT AND MEASURED",temperature,info["increments"],flush=True)
    frame=pd.DataFrame(rows,columns=[*COLUMNS,"status","temperature","task_family","role","category","primary_eligible"])
    validate_table(frame);path=folder/"deviations.parquet";frame.to_parquet(path,index=False);outputs.append(path)
    atomic(folder/"calibration.json",diagnostics);outputs.append(folder/"calibration.json")
    metrics={"attempts":attempts,"table_traces":len(selected),"table_rows":len(frame),"exclusions":dict(excluded),"calibration":diagnostics,
      "removed_steps":sum(r["removed_steps"] for r in selected),"refuted_traces_changed":0,"elapsed_seconds":time.monotonic()-started,
      "generation_calls":0,"model_forward_calls":0}
    finish(folder,metrics,[HERE/"analysis-source-manifest.json",OUT/"preflight/manifest.json",STATES/"protocols/kimina.json",*upstreams],outputs)
    return path
def main():
    if "SLURM_JOB_ID" not in os.environ:raise RuntimeError("Slurm required")
    check_code();check_code("analysis-source-manifest.json");check_manifest(OUT/"preflight/manifest.json")
    if not read(OUT/"preflight/metrics.json")["all_safe"]:raise ValueError("preflight blocked")
    check_manifest(OUT/"analysis-tests/manifest.json")
    if not read(OUT/"analysis-tests/metrics.json")["passed"]:raise ValueError("analysis tests failed")
    source=read(REPO/"audit/segmentation_controls_20260914_v1/source-manifest.json")
    for p,h in source["files"].items():
        if digest(p)!=h:raise ValueError("positional source changed")
    path=measure();config=read(STATES/"protocols/kimina.json");layer=config["layers"][1];out=OUT/"analysis";out.mkdir(exist_ok=True)
    primary=out/"primary-cell.json";started=time.monotonic()
    if not primary.exists():
        result=analyze_cell((str(path),config,.6,layer,"whitened"))
        result["scope"]="Kimina terminal post_completion removed from verified traces, whitening refitted; sensitivity only"
        result["new_whole_proof_certificates"]=False
        atomic(primary,result)
    else:
        # A completed full-stage manifest is the only supported resume point.
        if not (out/"manifest.json").exists():raise ValueError("partial analysis requires explicit recovery with input audit")
        check_manifest(out/"manifest.json");return
    table=pd.read_parquet(path);frame=table[(table.temperature==.6)&(table.statistic=="whitened")&(table.role=="evaluation")&(table.outcome=="refuted")]
    plan=read(REPO/"audit/segmentation_quality_20260914_v1/plan.json");controls={}
    for subset in plan["subsets"]:
        records=trials(frame,subset);controls[subset]=describe(records,plan)
        p=plan["positional_null"];controls[subset]["positional_null"]=positional_null(records,p["permutations"],p["min_tasks"],p["seed"],adjust=False)
        controls[subset]["scope"]="additional cleaned-Kimina sensitivity; p-values exploratory, no new confirmatory claim"
    atomic(out/"positional-controls.json",finite_json(controls))
    metrics={"model":"kimina","available":result["available"],"decision":result["decision"],"P2":result["P2"],
      "generation_calls":0,"model_forward_calls":0,"elapsed_seconds":time.monotonic()-started,"whitening_refitted_before_bootstrap":True,
      "whitening_fixed_inside_bootstrap":True}
    finish(out,metrics,[HERE/"analysis-source-manifest.json",OUT/"measurement/manifest.json",
        OUT/"analysis-tests/manifest.json",REPO/"audit/segmentation_controls_20260914_v1/source-manifest.json",
        REPO/"audit/segmentation_quality_20260914_v1/plan.json"],[primary,out/"positional-controls.json"])
    print("CLEANED ANALYSIS READY",str(out),flush=True)
if __name__=="__main__":main()
