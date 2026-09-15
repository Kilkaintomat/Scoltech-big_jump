"""Complete fixed-data-budget selection/threshold validation and preserve every draw."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from datetime import datetime, timezone
import io,os,time
import numpy as np
from scipy import stats
from experiment import analyze_dataset
from onebigjump.e1.artifacts import Journal,read_json,write_once,finish,digest,identity,verify_manifest
from onebigjump.e1.analysis import finite_json
from onebigjump.readiness.p3_validation import proportion

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=Path(__file__).resolve().parent
OUT=BASE/"runs/p3_selection_validation_20260913"
PROTOCOL=HERE.parent/"validation_protocol.json"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"


def worker(task):
    record,arrays=analyze_dataset(*task)
    stream=io.BytesIO()
    np.savez_compressed(stream,**arrays)
    return record,stream.getvalue()


def summarize(records,config):
    result={}
    for scenario,setting in config["scenarios"].items():
        sample=[r for r in records if r["request"]["scenario"]==scenario]
        cells={}
        paired={}
        for budget in config["calibration_budgets"]:
            for method in config["methods"]:
                pairs=[(r,r["methods"][budget][method]) for r in sample]
                applicable=[(r,c) for r,c in pairs if c["applicable"]]
                for kind in config["interval_kinds"]:
                    key=budget+"/"+method+"/"+kind
                    if not applicable:
                        cells[key]={"applicable":False,"reason":"no hard support oracle"}
                        continue
                    available=[(r,c) for r,c in applicable if c[kind]["ci95"] is not None]
                    coverage=proportion([c[kind]["ci95"][0]<=r["truth"]<=c[kind]["ci95"][1] for r,c in available])
                    reasons=Counter()
                    fit_reasons=Counter()
                    for _,c in applicable:
                        if c[kind]["ci95"] is None:
                            reasons[";".join(c["unavailable_reasons"])]+=1
                        fit_reasons.update(c["bootstrap_fit_reasons"])
                    biases=[c["point"]-r["truth"] for r,c in applicable if c["point"] is not None]
                    cells[key]={
                        "applicable":True,
                        "interpretation":"exact_hard_selection_coverage" if setting["selection"]=="hard" else "parent_tail_target_recovery_under_misspecification",
                        "availability":proportion([c[kind]["ci95"] is not None for _,c in applicable]),
                        "coverage_conditional":coverage,
                        "coverage_counting_unavailable_as_failure":proportion([
                            c[kind]["ci95"] is not None and c[kind]["ci95"][0]<=r["truth"]<=c[kind]["ci95"][1]
                            for r,c in applicable]),
                        "mean_point_bias":float(np.mean(biases)) if biases else None,
                        "mean_width":float(np.mean([c[kind]["ci95"][1]-c[kind]["ci95"][0] for _,c in available])) if available else None,
                        "miss_below_truth":sum(c[kind]["ci95"][1]<r["truth"] for r,c in available),
                        "miss_above_truth":sum(c[kind]["ci95"][0]>r["truth"] for r,c in available),
                        "positive_family_rejection":proportion([c[kind]["ci_family"] is not None and c[kind]["ci_family"][0]>0 for _,c in applicable]),
                        "unavailable_reason_sets":dict(reasons),
                        "bootstrap_fit_reasons":dict(fit_reasons),
                        "point_threshold_below_support":sum(c["threshold_below_true_support"] is True for _,c in applicable) if setting["selection"]=="hard" else None,
                        "bootstrap_threshold_below_support":sum(c["bootstrap_threshold_below_true_support"] for _,c in applicable) if setting["selection"]=="hard" else None,
                    }
            for reference in ["original","pooled_original","oracle_correct_selection"]:
                for kind in config["interval_kinds"]:
                    applicable=[r for r in sample if r["methods"][budget][reference]["applicable"]]
                    if not applicable:
                        continue
                    def ci(r,m):return r["methods"][budget][m][kind]["ci95"]
                    def covers(r,m):
                        interval=ci(r,m)
                        return interval is not None and interval[0]<=r["truth"]<=interval[1]
                    common=[r for r in applicable if ci(r,reference) is not None and ci(r,"independent_floor") is not None]
                    paired[budget+"/independent_floor_vs_"+reference+"/"+kind]={
                        "common":len(common),
                        "reference_covered_common":sum(covers(r,reference) for r in common),
                        "candidate_covered_common":sum(covers(r,"independent_floor") for r in common),
                        "gained_intervals":sum(ci(r,reference) is None and ci(r,"independent_floor") is not None for r in applicable),
                        "lost_intervals":sum(ci(r,reference) is not None and ci(r,"independent_floor") is None for r in applicable),
                        "coverage_gains_common":sum(not covers(r,reference) and covers(r,"independent_floor") for r in common),
                        "coverage_losses_common":sum(covers(r,reference) and not covers(r,"independent_floor") for r in common),
                    }
        result[scenario]={"cells":cells,"paired":paired}
    return finite_json(result)


def main():
    config=read_json(PROTOCOL)
    pre_config=read_json(HERE.parent/"protocol.json")
    assert {k:v for k,v in config.items() if k!="random_streams"}=={k:v for k,v in pre_config.items() if k!="random_streams"}
    freeze=HERE.parent/"method-freeze.json"
    for path,sha in read_json(freeze)["files"].items():
        assert digest(Path(path))==sha,path
    verify_manifest(HERE.parent/"preflight/manifest.json")
    assert read_json(HERE.parent/"preflight/metrics.json")["passed"]
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/"bootstrap-draws").mkdir()
    started=datetime.now(timezone.utc).isoformat()
    tasks=[(config,name,i) for i in range(config["datasets_per_scenario"]) for name in config["scenarios"]]
    context={"source":digest(SOURCE),"method_freeze":digest(freeze),"protocol":digest(PROTOCOL)}
    outputs=[]
    records=[]
    journal_path=OUT/"replicates.jsonl"
    clock=time.monotonic()
    with Journal(journal_path,context) as journal,ProcessPoolExecutor(max_workers=config["workers"]) as pool:
        for record,data in pool.map(worker,tasks):
            path=OUT/"bootstrap-draws"/(record["trace_id"].replace(":","-")+".npz")
            with path.open("xb") as f:f.write(data)
            outputs.append(path)
            record["bootstrap_file"]=str(path)
            record["bootstrap_sha256"]=digest(path)
            journal.append(record,identity(record["request"]))
            records.append(record)
            if len(records)%20==0:
                print("PROGRESS",len(records),len(tasks),"elapsed_seconds",round(time.monotonic()-clock,1),flush=True)
    expected={name+":"+str(i) for name in config["scenarios"] for i in range(config["datasets_per_scenario"])}
    assert len(records)==len(expected) and {r["trace_id"] for r in records}==expected
    summary=summarize(records,config)
    family={}
    hard=[name for name,setting in config["scenarios"].items() if setting["selection"]=="hard"]
    for name in hard:
        coverage=summary[name]["cells"][config["primary_candidate"]]["coverage_conditional"]
        n,k=coverage["datasets"],coverage["successes"]
        tail=.05/(2*len(hard))
        bounds=[float(stats.beta.ppf(tail,k,n-k+1)) if k else 0.,
                float(stats.beta.ppf(1-tail,k+1,n-k)) if k<n else 1.] if n else None
        family[name]={"mc_family_95_bounds":bounds,"undercoverage_detected":bounds is not None and bounds[1]<.95}
    metrics=finite_json({
        "started_utc":started,"finished_utc":datetime.now(timezone.utc).isoformat(),
        "parent_datasets":len(records),
        "analysis_conditions":len(records)*len(config["calibration_budgets"]),
        "bootstrap_fit_slots_including_not_applicable":len(records)*len(config["calibration_budgets"])*len(config["methods"])*config["statistics"]["bootstrap"],
        "config":config,"scenarios":summary,"primary_family_monte_carlo":family,
        "primary_changed":False,"decision":"no_automatic_promotion",
        "method_freeze_sha256":digest(freeze),
    })
    metric=write_once(OUT/"metrics.json",metrics)
    finish(OUT,stage="p3-selection-and-threshold-independent-validation",
        context=context,inputs=[SOURCE,HERE.parent/"preflight/manifest.json",freeze,PROTOCOL,
        HERE/"candidate.py",HERE/"experiment.py",Path(__file__),HERE.parent/"validation.sbatch"],
        outputs=[metric,journal_path,journal_path.with_suffix(".identity.json"),*outputs],
        metrics={"parent_datasets":len(records),"config":config,"primary_changed":False})
    print("SELECTION_VALIDATION_COMPLETE",OUT,flush=True)


if __name__=="__main__":
    main()
