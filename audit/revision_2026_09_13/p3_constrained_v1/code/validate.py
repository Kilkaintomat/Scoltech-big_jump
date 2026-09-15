"""Frozen paired independent validation of legacy and constrained P3 GPD fits."""
from __future__ import annotations

from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import io
import json
import os
import time
import numpy as np

from candidate import constrained_gpd_fit
from onebigjump.e1.analysis import finite_json
from onebigjump.e1.artifacts import Journal, digest, finish, identity, read_json, verify_manifest, write_once
from onebigjump.e1.stages import rows
from onebigjump.readiness import p3_validation
from onebigjump.readiness.p3_diagnosis import draw_sample
from onebigjump.readiness.p3_validation import proportion
from onebigjump.stats.gpd import gpd_fit

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = Path(__file__).resolve().parent
PROTOCOL = HERE.parent / "protocol.json"
OUT = BASE / "runs/p3_constrained_validation_20260913"
SOURCE = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"


def instrumented_evaluate(calibration, failures, config, seed, estimator):
    total = config["statistics"]["bootstrap"]
    arrays = {
        "shape": np.full((total,2),np.nan),
        "raw_gamma": np.full((total,2),np.nan),
        "threshold": np.full((total,2),np.nan),
        "reason": np.full((total,2),"",dtype="U160"),
    }
    point = {}
    reasons = {"original":Counter(),"observed_support":Counter()}
    names = ["original","observed_support"]
    call = 0
    last = None
    cache = None
    function = p3_validation.shape_at

    def wrapped(values, threshold):
        nonlocal call, last, cache
        group, column = divmod(call,2)
        key = (group,threshold)
        if key != last:
            excess = values[values > threshold]-threshold
            try:
                if estimator == "legacy":
                    fit = gpd_fit(excess,threshold=threshold)
                    obj = fit.as_dict()
                    why = fit.message if not fit.converged else "success"
                else:
                    fit = constrained_gpd_fit(excess,grid_size=config["numerics"]["grid_size_per_side"])
                    obj = fit.as_dict()
                    why = fit.reason
                value = fit.shape_estimate
            except (ValueError,FloatingPointError,OverflowError) as error:
                obj = {"gamma":float("nan"),"shape_estimate":float("nan"),"converged":False}
                value = float("nan")
                why = ("fewer_than_5_excesses" if excess.size<5
                       else type(error).__name__ + ": " + str(error))
            cache = obj, value, why
            last = key
        obj, value, why = cache
        if group == 0:
            point[names[column]] = finite_json(obj)
        else:
            b = group-1
            arrays["shape"][b,column] = value
            arrays["raw_gamma"][b,column] = obj["gamma"]
            arrays["threshold"][b,column] = threshold
            arrays["reason"][b,column] = why
            reasons[names[column]][why] += 1
        call += 1
        return value

    p3_validation.shape_at = wrapped
    try:
        result = p3_validation.evaluate(calibration,failures,config,seed)
    finally:
        p3_validation.shape_at = function
    assert call == 2+2*total
    # A candidate with an unusable original point cannot advertise an interval.
    # The legacy result is kept byte-equivalent to the existing evaluation.
    if estimator == "constrained":
        for name in names:
            if result[name]["point"] is None:
                result[name]["percentile"]["ci95"] = None
                result[name]["percentile"]["ci_family"] = None
                result[name]["basic"]["ci95"] = None
                result[name]["basic"]["ci_family"] = None
    return result, arrays, point, {key:dict(value) for key,value in reasons.items()}


def worker(task):
    config, scenario, index = task
    settings = config["scenarios"][scenario]
    seed = config["seed"] + settings["seed_offset"] + index
    cal, fail, support = draw_sample(seed,settings["shape"],settings["failure_quantile"],tasks=config["tasks"])
    methods, arrays, points, reasons = {}, {}, {}, {}
    for estimator in config["estimators"]:
        result, draw, point, why = instrumented_evaluate(cal,fail,config,seed+10000000,estimator)
        methods[estimator], points[estimator], reasons[estimator] = result, point, why
        for key, value in draw.items():
            arrays[estimator+"_"+key] = value
    assert np.array_equal(arrays["legacy_threshold"],arrays["constrained_threshold"])
    count_keys = ["threshold","calibration_tail_tasks","calibration_excesses",
                  "failure_tail_tasks","failure_excesses"]
    for name in config["thresholds"]:
        assert all(methods["legacy"][name][k] == methods["constrained"][name][k] for k in count_keys)
    stream = io.BytesIO()
    np.savez_compressed(stream,**arrays)
    record = finite_json({
        "trace_id":scenario+":"+str(index),
        "request":{"scenario":scenario,"index":index,"seed":seed},
        "truth":settings["shape"],
        "true_support_diagnostic_only":support,
        "methods":methods,"point_fit_diagnostics":points,"bootstrap_fit_reasons":reasons,
        "identical_bootstrap_thresholds":True,
    })
    return record, stream.getvalue()


def summarize(records, config):
    result = {}
    for scenario in config["scenarios"]:
        sample = [r for r in records if r["request"]["scenario"] == scenario]
        cells, paired = {}, {}
        for estimator in config["estimators"]:
            for threshold in config["thresholds"]:
                for interval_type in config["intervals"]:
                    key = estimator+"/"+threshold+"/"+interval_type
                    pairs = [(r,r["methods"][estimator][threshold]) for r in sample]
                    available = [(r,c) for r,c in pairs if c[interval_type]["ci95"] is not None]
                    cov = proportion([c[interval_type]["ci95"][0] <= r["truth"] <= c[interval_type]["ci95"][1]
                                      for r,c in available])
                    mc = cov["monte_carlo_ci95"]
                    width = [c[interval_type]["ci95"][1]-c[interval_type]["ci95"][0] for _,c in available]
                    point_values = [c["point"]-r["truth"] for r,c in pairs if c["point"] is not None]
                    reason_counts = Counter()
                    for r in sample:
                        reason_counts.update(r["bootstrap_fit_reasons"][estimator][threshold])
                    cells[key] = {
                        "availability":proportion([c[interval_type]["ci95"] is not None for _,c in pairs]),
                        "coverage_conditional":cov,
                        "coverage_counting_unavailable_as_failure":proportion([
                            c[interval_type]["ci95"] is not None and
                            c[interval_type]["ci95"][0] <= r["truth"] <= c[interval_type]["ci95"][1]
                            for r,c in pairs]),
                        "positive_family_rejection":proportion([
                            c[interval_type]["ci_family"] is not None and c[interval_type]["ci_family"][0]>0
                            for _,c in pairs]),
                        "available_ci_below_truth":sum(c[interval_type]["ci95"][1]<r["truth"] for r,c in available),
                        "available_ci_above_truth":sum(c[interval_type]["ci95"][0]>r["truth"] for r,c in available),
                        "point_available":sum(c["point"] is not None for _,c in pairs),
                        "mean_point_bias_when_point_available":float(np.mean(point_values)) if point_values else None,
                        "mean_ci_width":float(np.mean(width)) if width else None,
                        "median_ci_width":float(np.median(width)) if width else None,
                        "undercoverage_detected_by_descriptive_mc95":bool(mc is not None and mc[1]<.95),
                        "bootstrap_fit_reasons":dict(reason_counts),
                    }
        def covered(record,estimator,threshold,kind):
            interval = record["methods"][estimator][threshold][kind]["ci95"]
            return interval is not None and interval[0]<=record["truth"]<=interval[1]
        for threshold in config["thresholds"]:
            for kind in config["intervals"]:
                common = [r for r in sample if all(
                    r["methods"][e][threshold][kind]["ci95"] is not None for e in config["estimators"]
                )]
                paired[threshold+"/"+kind] = {
                    "common_available":len(common),
                    "legacy_covered_common":sum(covered(r,"legacy",threshold,kind) for r in common),
                    "candidate_covered_common":sum(covered(r,"constrained",threshold,kind) for r in common),
                    "gained_intervals":sum(
                        r["methods"]["legacy"][threshold][kind]["ci95"] is None and
                        r["methods"]["constrained"][threshold][kind]["ci95"] is not None for r in sample),
                    "lost_intervals":sum(
                        r["methods"]["legacy"][threshold][kind]["ci95"] is not None and
                        r["methods"]["constrained"][threshold][kind]["ci95"] is None for r in sample),
                    "coverage_gains_common":sum(not covered(r,"legacy",threshold,kind) and covered(r,"constrained",threshold,kind) for r in common),
                    "coverage_losses_common":sum(covered(r,"legacy",threshold,kind) and not covered(r,"constrained",threshold,kind) for r in common),
                }
        result[scenario] = {"cells":cells,"paired":paired}
    return finite_json(result)


def main():
    config = read_json(PROTOCOL)
    freeze_path = HERE.parent / "method-freeze.json"
    freeze = read_json(freeze_path)
    for path, expected in freeze["files"].items():
        assert digest(Path(path)) == expected, path
    preflight = HERE.parent / "preflight/manifest.json"
    verify_manifest(preflight)
    assert read_json(preflight.parent/"metrics.json")["passed"]
    started = datetime.now(timezone.utc).isoformat()
    print("FROZEN_METHOD",digest(freeze_path),"START",started,flush=True)
    OUT.mkdir(parents=True,exist_ok=False)
    # Instrumentation equivalence is checked on old data before any new draws.
    old_root = BASE/"runs/p3_validation_20260913"
    old_config = read_json(old_root/"protocol.json")
    old_config["numerics"] = config["numerics"]
    old_records = [r for r in rows(old_root/"shard-00/replicates.jsonl") if r["request"]["index"] == 0]
    legacy_replay = []
    for r in old_records:
        setting = old_config["scenarios"][r["request"]["scenario"]]
        cal,fail,_ = draw_sample(r["request"]["seed"],setting["shape"],setting["failure_quantile"],tasks=old_config["tasks"])
        replay,_,_,_ = instrumented_evaluate(cal,fail,old_config,r["request"]["seed"]+10000000,"legacy")
        assert replay == r["methods"],r["trace_id"]
        legacy_replay.append(r["trace_id"])
    replay_path = write_once(OUT/"instrumentation-check.json",{
        "legacy_exact_match":legacy_replay,
        "checked_before_new_data":True,
        "fresh_data_started_utc":datetime.now(timezone.utc).isoformat(),
    })
    tasks = [(config,scenario,index) for index in range(config["datasets"]) for scenario in config["scenarios"]]
    context = {"source":digest(SOURCE),"method_freeze":digest(freeze_path)}
    journal_path = OUT/"replicates.jsonl"
    draws_dir = OUT/"bootstrap-draws"
    draws_dir.mkdir()
    draw_paths = []
    records = []
    clock = time.monotonic()
    with Journal(journal_path,context) as journal, ProcessPoolExecutor(max_workers=config["workers"]) as pool:
        for record, array_bytes in pool.map(worker,tasks):
            file = draws_dir/(record["trace_id"].replace(":","-")+".npz")
            with file.open("xb") as stream:
                stream.write(array_bytes)
            draw_paths.append(file)
            record["bootstrap_file"] = str(file)
            record["bootstrap_sha256"] = digest(file)
            journal.append(record,identity(record["request"]))
            records.append(record)
            if len(records)%20 == 0:
                print("PROGRESS",len(records),len(tasks),"elapsed_seconds",round(time.monotonic()-clock,1),flush=True)
    expected = {scenario+":"+str(index) for scenario in config["scenarios"] for index in range(config["datasets"])}
    assert len(records)==len(expected) and {r["trace_id"] for r in records}==expected
    metrics = finite_json({
        "started_utc":started,"finished_utc":datetime.now(timezone.utc).isoformat(),
        "datasets":len(records),"bootstrap_fit_slots":len(records)*len(config["estimators"])*len(config["thresholds"])*config["statistics"]["bootstrap"],
        "config":config,"scenarios":summarize(records,config),
        "legacy_exact_replay":legacy_replay,"main_method_changed":False,
        "decision":"no_automatic_promotion; evaluate all prespecified scenarios and availability",
        "method_freeze_sha256":digest(freeze_path),
    })
    metric = write_once(OUT/"metrics.json",metrics)
    finish(OUT,stage="paired-independent-constrained-gpd-validation",
        context=context,
        inputs=[SOURCE,preflight,freeze_path,PROTOCOL,HERE/"candidate.py",Path(__file__),
                HERE.parent/"validation.sbatch",old_root/"shard-00/manifest.json"],
        outputs=[metric,replay_path,journal_path,journal_path.with_suffix(".identity.json"),*draw_paths],
        metrics={"datasets":len(records),"main_method_changed":False,"config":config})
    print("INDEPENDENT_VALIDATION_COMPLETE",OUT,flush=True)


if __name__=="__main__":
    main()
