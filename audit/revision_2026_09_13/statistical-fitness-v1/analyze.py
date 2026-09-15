from pathlib import Path
import os,time,json,math
import numpy as np
import pandas as pd
from scipy.stats import binomtest,binom,norm
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,identity,verify_manifest
from onebigjump.e1.stages import rows
from onebigjump.readiness.finite_sample import localization_effects,threshold_rates,bounded_mean,sign_screen
from onebigjump.readiness.whitening import fit_whitening,replace_scores

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/statistical-fitness-v1"
OUT=HERE/"analysis"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
protocol=read_json(HERE/"protocol.json")
inputs=[SOURCE,HERE/"protocol.json",Path(__file__)]
result={"models":{},"calibration":{},"primary_unchanged":True,"scope":"supplementary, post-pilot, fixed benchmark"}
start=time.monotonic()
for model in ["deepseek","goedel","kimina"]:
    root=BASE/"runs/lean_reverification_20260913_local"/model
    measurement=root/"pilot/measurement/manifest.json"
    extraction=root/"pilot/extraction/manifest.json"
    for path in [measurement,extraction]:verify_manifest(path)
    inputs.extend([measurement,extraction,root/"pilot/protocol.json"])
    config=read_json(root/"pilot/protocol.json")
    table=pd.read_parquet(measurement.parent/"deviations.parquet")
    table=table[(table.temperature==config["primary_temperature"]) &
                (table.layer==config["primary_layer"]) & table.primary_eligible]
    raw=table[table.statistic=="raw"].copy()
    cal_ids=set(raw.loc[raw.role=="calibration","prompt_id"])
    eval_ids=set(raw.loc[raw.role=="evaluation","prompt_id"])
    assert not cal_ids & eval_ids
    cells={}
    for statistic in ["raw","whitened","innovation"]:
        cell=table[table.statistic==statistic]
        evaluation=cell[cell.role=="evaluation"]
        cal=cell[(cell.role=="calibration") & (cell.outcome=="verified")]
        tau=float(np.quantile(cal.z,1-protocol["finite_metrics"]["q"])) if len(cal) else None
        cells[statistic]={"P2":localization_effects(evaluation),
                         "P2_drop_first":localization_effects(evaluation,True),
                         "finite_threshold":threshold_rates(evaluation,tau) if tau is not None else None,
                         "threshold_tasks":int(cal.prompt_id.nunique()),"threshold_steps":len(cal),
                         "tau":tau,"transform_threshold_reuse":statistic!="raw"}
    records={r["trace_id"]:r for r in rows(extraction.parent/"trajectories.jsonl") if r["extraction_status"]=="extracted"}
    states={}
    for rid in raw.trace_id.unique():
        row=records[rid]
        assert digest(row["states_path"])==row["states_sha256"]
        with np.load(row["states_path"],allow_pickle=False) as bundle:
            states[str(rid)]=bundle["states_%d"%config["primary_layer"]]
    verified=raw[(raw.role=="calibration") & (raw.outcome=="verified")]
    tasks=sorted(verified.prompt_id.unique(),key=lambda t:identity([20260911,str(t)]))
    fit_tasks=tasks[::2];threshold_tasks=tasks[1::2]
    fit_ids=verified.loc[verified.prompt_id.isin(fit_tasks),"trace_id"].unique()
    fitted=fit_whitening([states[str(rid)] for rid in fit_ids],.1)
    transformed=replace_scores(raw,states,fitted)
    cal=transformed[(transformed.role=="calibration") & transformed.prompt_id.isin(threshold_tasks) & (transformed.outcome=="verified")]
    evaluation=transformed[transformed.role=="evaluation"]
    tau=float(np.quantile(cal.z,.99))
    cells["whitened_disjoint_0.1"]={
        "P2":localization_effects(evaluation),"P2_drop_first":localization_effects(evaluation,True),
        "finite_threshold":threshold_rates(evaluation,tau),
        "fit_task_ids":list(fit_tasks),"threshold_task_ids":list(threshold_tasks),
        "fit_increments":fitted["n"],"dimension":fitted["d"],
        "threshold_steps":len(cal),"tau":tau,"transform_threshold_reuse":False,
        "warning":"tiny calibration split; independence does not ensure a precisely estimated quantile"}
    result["models"][model]={"primary_layer":config["primary_layer"],
        "temperature":config["primary_temperature"],"calibration_task_ids":sorted(cal_ids),
        "evaluation_task_ids":sorted(eval_ids),"cells":cells}
    print("FINITE_ANALYSIS",model,flush=True)

rng=np.random.default_rng(protocol["seed"])
drawfiles=[]
for n in protocol["calibration"]["task_counts"]:
    for effect in protocol["calibration"]["effect"]:
        # Heterogeneous Bernoulli success probabilities; all repeated attempts within a task
        # share their binary score (perfect dependence). Task means stay independent.
        datasets=protocol["calibration"]["datasets"]
        p=np.linspace(.2,.8,n);p=p+effect
        draws=(rng.random((datasets,n))<p).astype(float)
        truth=float(p.mean())
        bounds=np.array([bounded_mean(list(x),0,1)["interval"] for x in draws])
        covers=(bounds[:,0]<=truth)&(truth<=bounds[:,1])
        ci=binomtest(int(covers.sum()),datasets).proportion_ci(method="exact")
        result["calibration"]["tasks_%d_effect_%s"%(n,effect)]={
            "datasets":datasets,"truth":truth,"coverage":float(covers.mean()),
            "coverage_ci95":[float(ci.low),float(ci.high)],
            "all_intervals_available":True,
            "scope":"independent task scores, perfect within-task dependence; checks implementation, not transformer assumptions"}
        path=OUT/("simulation-%d-%s.npz"%(n,effect))
        path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,task_scores=draws,intervals=bounds)
        drawfiles.append(path)

# Exact-size calculation for all sign outcomes avoids a Monte Carlo excuse at small n.
result["sign_test_size"]=[]
for n in [1,3,5,6,7,10,20,50,100,417]:
    pvals=np.array([binomtest(k,n,.5).pvalue for k in range(n+1)])
    pmf=binom.pmf(np.arange(n+1),n,.5)
    result["sign_test_size"].append({"non_tied_tasks":n,"minimum_two_sided_p":float(pvals.min()),
        "null_size_0.05":float(pmf[pvals<=.05].sum()),
        "null_size_three_model_0.05":float(pmf[pvals<=.05/3].sum())})
p4=BASE/"runs/expansion_20260911/p4/summary/metrics.json"
# Use the already validated final audit receipt for P4; avoid recursively rehashing checkpoints.
inputs.append(p4)
pairs=read_json(p4)["pairs"]
result["P4_sign_screens"]={est:sign_screen([p["paired_difference"][est] for p in pairs]) for est in ["hill","moment","gpd"]}
result["precision_planning"]={
 "distribution_free_gain_bound":[{"half_width":e,
  "tasks_for_marginal_95":math.ceil(2*math.log(40)/e**2),
  "tasks_for_three_model_95":math.ceil(2*math.log(120)/e**2)} for e in [.2,.1,.05]],
 "normal_approximation_gain":[{"assumed_task_sd":sd,"half_width":e,
  "tasks_approx":math.ceil((norm.ppf(.975)*sd/e)**2)} for sd in [.25,.5,1] for e in [.1,.05]],
 "normal_scope":"planning illustration only; not validated intervals, pilot variance not used to promise power",
 "expected_tail_steps":[{"q":q,"target_expected_exceedances":k,"required_steps_in_expectation":math.ceil(k/q)}
     for q in [.01,.001] for k in [20,100]],
 "tail_scope":"expectation only, not independent tail-task count or threshold guarantee"}
result["analysis_seconds"]=time.monotonic()-start
a=write_once(OUT/"metrics.json",result)
finish(OUT,stage="statistical-fitness-supplementary-analysis",context={"source":digest(SOURCE)},
       inputs=list(dict.fromkeys(inputs)),outputs=[a,*drawfiles],
       metrics={"models":len(result["models"]),"simulation_datasets":sum(x["datasets"] for x in result["calibration"].values()),
                "primary_unchanged":True,"seconds":result["analysis_seconds"]})
print("ANALYSIS_COMPLETE",result["analysis_seconds"],flush=True)
