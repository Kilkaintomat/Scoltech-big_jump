"""Full-population CPU audit of identities, exported observations, and sample structure."""
import collections,concurrent.futures,gzip,json,os,time
from pathlib import Path
import numpy as np
import pandas as pd
from data import REPO,RUN as STATES,SEG,MODELS,read,atomic,digest,identity,environment,check_source,check_manifest,shard_items,load_export,alignment
from measure_analyze import labels
HERE=REPO/"audit/segmentation_quality_20260914_v1"
OUT=REPO/"runs/segmentation_quality_20260914_v1"
PLAN=read(HERE/"plan.json")
def manifest(folder,metrics,inputs,outputs):
    atomic(folder/"metrics.json",metrics)
    atomic(folder/"manifest.json",{"config":PLAN,"git_commit":os.environ.get("ONEBIGJUMP_GIT_COMMIT"),
      "dirty":bool(os.environ.get("ONEBIGJUMP_GIT_STATUS")),"environment":environment(),
      "inputs":{str(p):digest(p) for p in inputs},"source_files":{str(p):digest(p) for p in HERE.iterdir() if p.suffix in [".py",".sbatch"]},
      "outputs":{str(p):digest(p) for p in [folder/"metrics.json",*outputs]}})
def summarize(frame):
    x={"attempts":len(frame),"tasks":int(frame.problem_id.nunique()),"statuses":frame.status.value_counts().to_dict(),
       "ready_for_forward":int(frame.forward_ready.sum()),"p2_flagged":int(frame.p2_flag.sum()),
       "p2_accepted":int(frame.p2_ok.sum()),"p2_tasks":int(frame.loc[frame.p2_ok,"problem_id"].nunique()),
       "verified_accepted":int(frame.verified_ok.sum()),"verified_tasks":int(frame.loc[frame.verified_ok,"problem_id"].nunique())}
    for name,mask in [("forward",frame.forward_ready),("p2",frame.p2_ok),("verified",frame.verified_ok)]:
        g=frame[mask]
        if g.empty:x[name]={};continue
        a=g.L.to_numpy(dtype=float);b=g.old_L.to_numpy(dtype=float)
        v={"traces":len(g),"tasks":int(g.problem_id.nunique()),"mean_L":float(a.mean()),"median_L":float(np.median(a)),
           "q90_L":float(np.quantile(a,.9)),"max_L":int(a.max()),"mean_old_L":float(b.mean()),"median_old_L":float(np.median(b)),
           "L_counts":{str(k):int(v) for k,v in g.L.value_counts().sort_index().items()},
           "branch_traces":int((g.branches>0).sum()),"post_completion_traces":int((g.post_completion>0).sum()),
           "boundary_rejection_traces":int((g.rejected>0).sum())}
        if name=="p2":
            f=g.first_error.to_numpy(dtype=float)
            v.update(first_error_count=int((f==0).sum()),last_error_count=int((f==a-1).sum()),
                both_neighbors_count=int(((f>0)&(f<a-1)).sum()),after_first_count=int((f>0).sum()),
                failure_position_counts={str(k):int(v) for k,v in (g.first_error+1).value_counts().sort_index().items()},
                uniform_exact_chance=float(np.mean(1/a)),
                uniform_window_chance=float(np.mean((np.minimum(a-1,f+1)-np.maximum(0,f-1)+1)/a)))
            unique=g.sort_values("trace_id").drop_duplicates("problem_id")
            counts=unique.groupby(["task_family","L"]).size()
            supported=set(counts[counts>=2].index)
            v["positional_null_tasks"]=sum((r.task_family,r.L) in supported for r in unique.itertuples())
            v["positional_null_excluded_tasks"]=len(unique)-v["positional_null_tasks"]
        x[name]=v
    return x
def choose_cases(frame):
    good=frame[frame.forward_ready & frame.alignment_ok & frame.labels_ok].copy()
    masks={
      "verified_short":good.verified_ok,"verified_long":good.verified_ok,
      "error_first_short":good.p2_ok & (good.first_error==0),"error_first_long":good.p2_ok & (good.first_error==0),
      "error_interior":good.p2_ok & (good.first_error>0)&(good.first_error<good.L-1),
      "error_last":good.p2_ok & (good.first_error==good.L-1),
      "error_branch":good.p2_ok & (good.branches>0),"verified_branch":good.verified_ok & (good.branches>0),
      "merged_boundary":good.merged>0,"rejected_boundary":good.rejected>0,"post_completion":good.post_completion>0,
      "largest_length_increase":good.L>good.old_L}
    seen=set();selected=[];unavailable=[]
    for bucket in PLAN["manual_review"]["buckets"]:
        group=good[masks[bucket] & ~good.trace_id.isin(seen)].copy()
        if group.empty:unavailable.append(bucket);continue
        if bucket.endswith("short"):group=group.sort_values(["L","trace_id"])
        elif bucket.endswith("long"):group=group.sort_values(["L","trace_id"],ascending=[False,True])
        elif bucket=="largest_length_increase":group=group.assign(increase=group.L-group.old_L).sort_values(["increase","trace_id"],ascending=[False,True])
        else:group=group.sort_values("trace_id")
        row=group.iloc[0];selected.append((bucket,row.to_dict()));seen.add(row.trace_id)
    return selected,unavailable
def make_case(bucket,row,item,annotation,path):
    with gzip.open(path,"rt",encoding="utf-8") as f:blob=json.load(f)
    result=blob["detail"]["observation"];export=blob["detail"]["export"];obs=export["observation_rows"]
    star=None if pd.isna(row["first_error"]) else int(row["first_error"])
    indices=sorted(set([0,len(obs)-1]+([] if star is None else list(range(max(0,star-1),min(len(obs),star+2))))))
    excerpts=[]
    for i in indices:
        o=obs[i];a=min(p["span_start"] for p in o["source_points"])-2;b=max(p["span_end"] for p in o["source_points"])-2
        excerpts.append({"i_1based":i+1,"trace_label":o["trace_label"],"token":o["token_position"],"boundary":o["boundary_kind"],
          "text":item["body"][a:b][:900],"source_span":[a,b],"point_labels":[p["trace_label"] for p in o["source_points"]],
          "point_kinds":[p["observation_kind"] for p in o["source_points"]],
          "scope_changes":[p["source_transition"] for p in o["source_points"]]})
    candidate=result.get("fine_failure_candidate")
    diagnostics=[]
    for d in result.get("diagnostics",[]):
        if d.get("candidate_id")==candidate or (candidate is None and len(diagnostics)<2):
            diagnostics.append({k:d.get(k) for k in ["candidate_id","parse_char","message"]})
    return {"bucket":bucket,"model":row["model"],"trace_id":row["trace_id"],"task":row["problem_id"],"role":row["role"],
      "temperature":row["temperature"],"old_category":row["old_category"],"old_L":int(row["old_L"]),"L":int(row["L"]),
      "first_error_1based":None if star is None else star+1,"branch_switches":int(row["branches"]),
      "header":item["header"],"source_body":item["body"],"excerpts":excerpts,
      "failure_candidate":candidate,"diagnostics":diagnostics[:4],"whole_observed_ok":result["whole_elaboration_ok"],
      "localization_status":result["localization_status"],"prefix_reproduced":result.get("failure_and_prefix_reproduced"),
      "localization_blockers":result.get("localization_blockers"),"replay_status_counts":annotation.get("replay_status_counts"),
      "artifact_path":str(path),"artifact_sha256":digest(path),"original_label_sha256":item["label_row_sha256"],
      "manual_review_status":"pending"}
def audit_model(model):
    from transformers import AutoTokenizer
    metadata=read(SEG/"inputs/manifest.json")
    tasks=[int(t) for t,s in metadata["shards"].items() if s["model"]==model]
    config=read(STATES/"protocols"/(model+".json"))
    tok=AutoTokenizer.from_pretrained(config["model_path"],local_files_only=True)
    base=REPO/"runs/lean_reverification_20260913_local"/model
    problems={r["problem_id"]:r for r in read(base/"inputs/problems.json")}
    old={}
    with (base/"main/verification/labels.jsonl").open(encoding="utf-8") as f:
        for line in f:
            r=json.loads(line);old[r["trace_id"]]={"star":r.get("t_star"),"row_sha256":r.get("row_sha256")}
    rows=[];errors=[]
    for task in sorted(tasks):
        for item,r,path in shard_items(task):
            s=item["sample"]
            if item["label_row_sha256"]!=old[item["trace_id"]]["row_sha256"]:raise ValueError("original label identity mismatch")
            if s["role"]!=problems[item["problem_id"]]["role"]:raise ValueError("role mismatch")
            row={"model":model,"task":task,"trace_id":item["trace_id"],"problem_id":item["problem_id"],"role":s["role"],
                 "temperature":s["temperature"],"task_family":problems[item["problem_id"]]["task_family"],
                 "status":r["status"],"old_category":item["old_category"],"old_L":item["n_old_blocks"],
                 "old_first_error":old[item["trace_id"]]["star"],"p2_flag":bool(r["p2_eligible"]),
                 "forward_ready":bool(r.get("ready_for_activation_extraction") and r["status"]=="annotated"),
                 "alignment_ok":False,"labels_ok":False,"p2_ok":False,"verified_ok":False,"first_error":None,
                 "L":None,"branches":r.get("n_branch_switches",0),"post_completion":r.get("n_post_completion",0),
                 "rejected":r.get("n_rejected_token_boundaries",0),"merged":0,"n_calc":0,"post_recovery_observed":0,
                 "tokens":len(s["prompt_token_ids"])+len(s["completion_token_ids"]),"artifact_path":str(path)}
            if row["forward_ready"]:
                e=load_export(item,r,path);obs=e["observation_rows"];row["L"]=len(obs)
                row["merged"]=sum(len(o["point_indices"])>1 for o in obs)
                row["n_calc"]=sum(any(p["observation_kind"]=="calc_step" for p in o["source_points"]) for o in obs)
                row["post_recovery_observed"]=sum(any(p.get("absorbing_unreached") and p.get("observed_during_lean_recovery") for p in o["source_points"]) for o in obs)
                try:
                    al=alignment(item,e,tok)
                    raw=s["completion"].encode("utf-8")
                    for o in obs:
                        tail=raw[o["semantic_end_byte"]:o["token_end_byte"]]
                        if tail.strip():raise ValueError("token contains future non-whitespace source")
                        if o["token_position"]!=len(s["prompt_token_ids"])+o["completion_token_index"]:raise ValueError("global token shift")
                        if any(p["trace_label"]=="post" and not p.get("absorbing_unreached") for p in o["source_points"]):raise ValueError("post-error point not absorbing")
                    row["alignment_ok"]=True
                except ValueError as error:
                    errors.append({"trace_id":item["trace_id"],"kind":"alignment","reason":str(error)})
                try:
                    star=labels(e,r);row["labels_ok"]=True;row["first_error"]=star
                    row["p2_ok"]=r["p2_eligible"] and row["alignment_ok"]
                    row["verified_ok"]=star is None and item["old_category"]=="verified" and row["alignment_ok"]
                except ValueError as error:
                    errors.append({"trace_id":item["trace_id"],"kind":"labels","reason":str(error),"p2_flag":r["p2_eligible"]})
            rows.append(row)
        print("AUDITED",model,task,len(rows),flush=True)
    frame=pd.DataFrame(rows)
    expected=sum(metadata["shards"][str(t)]["count"] for t in tasks)
    if len(frame)!=expected or frame.trace_id.duplicated().any():raise ValueError("attempt accounting")
    calibration=set(frame.loc[frame.role=="calibration","problem_id"]);evaluation=set(frame.loc[frame.role=="evaluation","problem_id"])
    if calibration&evaluation:raise ValueError("task leakage")
    result={"overall":summarize(frame),"by_role_temperature":{},"calibration_tasks":len(calibration),"evaluation_tasks":len(evaluation),
            "task_overlap":[],"checks":{"input_and_label_identities":True,"all_attempts_accounted":True,"roles_disjoint":True},
            "errors_by_reason":dict(collections.Counter((x["kind"]+": "+x["reason"]) for x in errors)),
            "alignment_failures":sum(x["kind"]=="alignment" for x in errors),
            "p2_label_failures":sum(x["kind"]=="labels" and x["p2_flag"] for x in errors)}
    for (role,temp),g in frame.groupby(["role","temperature"]):
        result["by_role_temperature"][f"{role}:T{temp}"]=summarize(g)
    selection,unavailable=choose_cases(frame);selected_ids={r["trace_id"]:(b,r) for b,r in selection};cases=[]
    for task in sorted({r["task"] for _,r in selection}):
        for item,r,path in shard_items(int(task)):
            if item["trace_id"] in selected_ids:
                bucket,record=selected_ids[item["trace_id"]];cases.append(make_case(bucket,record,item,r,path))
    result["review_cases"]=len(cases);result["unavailable_review_strata"]=unavailable
    # Performance sample selection uses lengths and classes only, never model scores.
    profile=[]
    for category,mask in [("verified",frame.verified_ok),("refuted",frame.p2_ok)]:
        group=frame[mask].sort_values(["tokens","trace_id"]);seen=set()
        for q in PLAN["profile"]["quantiles"]:
            target=float(group.tokens.quantile(q))
            picked=group.assign(distance=(group.tokens-target).abs()).sort_values(["distance","trace_id"]).iloc[0]
            if picked.trace_id in seen:continue
            seen.add(picked.trace_id)
            profile.append({"model":model,"trace_id":picked.trace_id,"task":int(picked.task),"category":category,"quantile":q,"tokens":int(picked.tokens)})
    folder=OUT/model;folder.mkdir(parents=True,exist_ok=True)
    frame.to_csv(folder/"traces.csv",index=False)
    atomic(folder/"errors.json",errors);atomic(folder/"review-cases.json",cases);atomic(folder/"profile-selection.json",profile)
    manifest(folder,result,[HERE/"plan.json",SEG/"inputs/manifest.json",SEG/"summary/manifest.json",STATES/"source-manifest.json",
                           base/"main/verification/labels.jsonl",base/"inputs/problems.json"],
             [folder/"traces.csv",folder/"errors.json",folder/"review-cases.json",folder/"profile-selection.json"])
    return model,result
def main():
    check_source()
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:result=dict(pool.map(audit_model,MODELS))
    metrics={"created_unix":time.time(),"models":result,"generation_calls":0,"model_forward_calls":0,
             "all_attempts":sum(v["overall"]["attempts"] for v in result.values()),
             "gpu_adapter_blockers":sum(v["alignment_failures"] for v in result.values()),
             "manual_review_completed":False,"scope":PLAN["scope"]}
    manifest(OUT,metrics,[HERE/"plan.json",*[OUT/m/"manifest.json" for m in MODELS]],[])
    print("AUDIT COMPLETE",metrics["all_attempts"],"adapter blockers",metrics["gpu_adapter_blockers"],flush=True)
if __name__=="__main__":main()
