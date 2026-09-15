"""Independent summaries of completed measurements and explicitly declared precision diagnostics."""
import collections,json
import numpy as np,pandas as pd
from support import *
def main():
    check_code();check_source();plan=read(HERE/"plan.json");inputs=[];results={};integrity=[]
    check_manifest(CONTROL/"manifest.json");control=read(CONTROL/"metrics.json");inputs.append(CONTROL/"manifest.json")
    for model in MODELS:
        print("REVIEW",model,flush=True)
        mm=STATES/"measurement"/model/"manifest.json";am=STATES/"analysis"/model/"manifest.json"
        for p in [mm,am]:check_manifest(p);inputs.append(p);integrity.append(str(p))
        table=pd.read_parquet(STATES/"measurement"/model/"deviations.parquet");x=read(am.parent/"primary-cell.json")
        layer=plan["primary"]["layers"][model]
        cell=table[(table.temperature==.6)&(table.layer==layer)]
        frame=cell[(cell.role=="evaluation")&(cell.statistic=="whitened")]
        rows=trace_rows(frame);d=describe(rows)
        for a,b in [(d["jump"],x["P2"]["jump"]["top1"]),(d["surprisal"],x["P2"]["surprisal"]["top1"]),(d["chance"],x["P2"]["chance"])]:
            if not np.isclose(a,b,atol=1e-12):raise ValueError("independent P2 mismatch")
        counts={}
        single=table[table.statistic=="raw"].drop_duplicates("trace_id")
        for (role,temp,outcome),g in single.groupby(["role","temperature","outcome"]):
            counts[str((role,temp,outcome))]={"traces":len(g),"tasks":g.prompt_id.nunique()}
        extraction=collections.Counter()
        for task,m in read(STATES/"plan.json")["models"].items():
            if m==model:
                p=STATES/"shards"/("%03d"%int(task))/"manifest.json";inputs.append(p)
                metrics=read(p)["metrics"]
                if not metrics["all_accounted"]:raise ValueError("incomplete extraction")
                extraction.update(metrics["statuses"])
        olddir=REPO/"runs/lean_reverification_20260913_local"/model/"main/measurement"
        check_manifest(olddir/"manifest.json");inputs.append(olddir/"manifest.json")
        old=pd.read_parquet(olddir/"deviations.parquet")
        oldf=old[(old.temperature==.6)&(old.layer==layer)&(old.statistic=="whitened")&(old.role=="evaluation")&old.primary_eligible]
        oldrows=trace_rows(oldf);common=set(r["id"] for r in rows)&set(r["id"] for r in oldrows)
        matched={"common_traces":len(common),"old_full":describe(oldrows),"new_full":d,
          "old_matched":describe([r for r in oldrows if r["id"] in common]),"new_matched":describe([r for r in rows if r["id"] in common]),
          "old_only":len(oldrows)-len(common),"new_only":len(rows)-len(common)}
        raw={stat:describe(trace_rows(cell[(cell.role=="evaluation")&(cell.statistic==stat)])) for stat in ["raw","whitened","innovation"]}
        p3={}
        for stat in ["raw","whitened","innovation"]:
            c=cell[cell.statistic==stat];cal=c[(c.role=="calibration")&(c.outcome=="verified")];ev=c[c.role=="evaluation"]
            tau=float(cal.z.quantile(.99));verified=ev[ev.outcome=="verified"];pre=ev[(ev.outcome=="refuted")&(ev.t<ev.t_star)];at=ev[(ev.outcome=="refuted")&(ev.t==ev.t_star)]
            accepted=pd.concat([verified,pre])
            def stats(g):return {"steps":len(g),"tasks":g.prompt_id.nunique(),"exceedance":float((g.z>tau).mean()) if len(g) else None,"median":float(g.z.median()) if len(g) else None}
            p3[stat]={"tau":tau,"calibration":stats(cal),"verified_evaluation":stats(verified),"pre_error_evaluation":stats(pre),"accepted_evaluation":stats(accepted),"at_error":stats(at)}
        if not np.isclose(p3["whitened"]["accepted_evaluation"]["exceedance"],x["P3"][0]["accepted_step_exceedance"]):raise ValueError("P3 denominator mismatch")
        p1={}
        for name,point in x["P1"].items():
            p1[name]={k:point.get(k) for k in ["hill","moment","gpd","k","n_steps","n_tasks","n_traces","tail_tasks","sufficient_sample"]}
            p1[name]["ci"]={e:{k:x["task_bootstrap"]["P1"][name][e].get(k) for k in ["ci95","ci_family","valid","replicates"]} for e in ["hill","moment","gpd"]}
            p1[name]["stability"]={k:point.get("stability",{}).get(k) for k in ["k","hill","moment"]}
        c=control["models"][model];selection={}
        for subset,v in c.items():
            selected=set(v["positional_null"].get("selected_trace_ids",[]))
            tr=read(CONTROL/(model+"-"+subset+"-trials.json"))
            chosen={}
            for t in tr:chosen.setdefault(t["problem_id"],t)
            selection[subset]={"tasks_before_matching":len(chosen),"tasks_matched":len(selected),
                "eligible_one_per_task_D0":float(np.mean([t["j"]==t["f"] for t in chosen.values()])),
                "matched_D0":float(np.mean([t["j"]==t["f"] for t in tr if t["trace_id"] in selected])) if selected else None}
        b=plan["paired_bootstrap"]
        results[model]={"population":counts,"extraction_statuses":dict(extraction),"measurement":read(mm.parent/"metrics.json"),
          "primary":d,"precision_bootstrap":paired(rows,b["seed"],b["replicates"]),
          "original_P2_bootstrap":x["task_bootstrap"]["P2_paired_difference"],
          "P1":p1,"P1_difference_ci":x["task_bootstrap"]["P1_direct_moment_difference"],
          "P1_exclude_first":{n:{k:v.get(k) for k in ["hill","moment","gpd","n_steps","n_tasks","tail_tasks"]} for n,v in x["P1_exclude_first"].items()},
          "P2_metrics":{"top3_jump":x["P2"]["jump"]["top3"],"top3_surprisal":x["P2"]["surprisal"]["top3"],"auc_jump":x["P2"]["roc"]["auc"],"auc_surprisal":x["P2"]["roc_surprisal"]["auc"],"prefix":x["P2"]["prefix_through_failure"]},
          "old_new_matched":matched,"same_trace_statistics":raw,"P3":p3,"P3_original": [{k:v for k,v in z.items() if k in ["q","tau","failure_coverage","accepted_step_exceedance","calibration_tail_tasks","positive_excess_tasks","sufficient_sample","gpd"]} for z in x["P3"]],
          "P3_intervals":x["task_bootstrap"]["P3"],"position_controls":c,"position_selection":selection}
        atomic(OUT/(model+"-partial.json"),clean(results[model]))
    for p in [KIMINA/"comparison/manifest.json",KIMINA/"analysis/manifest.json",KIMINA/"measurement/manifest.json"]:check_manifest(p);inputs.append(p)
    kim=read(KIMINA/"comparison/comparison.json");kx=read(KIMINA/"analysis/primary-cell.json")
    p4=REPO/"audit/p4_audit_20260914";p5=REPO/"runs/p5_repair_20260914_v2/summary"
    inputs += [p4/"summary-audit.json",p4/"original-paired-summary.json",p4/"REPORT_RU.md",p5/"manifest.json"];check_manifest(p5/"manifest.json")
    out={"models":results,"integrity_verified":integrity,
      "kimina":{"cleanup":kim["cleanup"],"raw_values_identical":kim["retained_raw_values_surprisal_and_labels_identical"],
        "refuted_traces_changed":kim["refuted_traces_changed"],"after_P2":{k:kx["P2"][k] for k in ["jump","surprisal","chance","n_tasks","n_traces","paired_difference"]},
        "after_P2_bootstrap":kx["task_bootstrap"]["P2_paired_difference"],"after_P3":[{k:z.get(k) for k in ["q","tau","accepted_step_exceedance","failure_coverage"]} for z in kx["P3"]]},
      "P4":read(p4/"summary-audit.json"),"P4_original_pairs":read(p4/"original-paired-summary.json"),"P5":read(p5/"metrics.json"),
      "generation_calls":0,"model_forward_calls":0,"scope":plan["scope"]}
    finish("audit",out,inputs);print("AUDIT COMPLETE",flush=True)
if __name__=="__main__":main()
