"""P3 threshold and selection model experiment; fixed constrained optimizer."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import math
import numpy as np
from scipy import stats
from scipy.special import expit
from candidate import constrained_gpd_fit
from onebigjump.e1.analysis import finite_json
from onebigjump.e1.main_analysis import intervals

METHODS = ["original","observed_minimum","independent_floor","oracle_correct_selection","pooled_original"]


def rng_for(seed, role):
    return np.random.default_rng(np.random.SeedSequence([role,seed]))


def soft_integral(u, config):
    p = config["soft_selection"]
    return (p["background"]*np.asarray(u) + p["amplitude"]*p["cdf_scale"]*(
        np.logaddexp(0,(np.asarray(u)-p["cdf_center"])/p["cdf_scale"])
        - np.logaddexp(0,-p["cdf_center"]/p["cdf_scale"])))


def failures_sample(rng, shape, setting, config, tasks):
    size = tasks * config["failures_per_task"]
    if setting["selection"] == "hard":
        cutoff = float(stats.genpareto.ppf(setting["failure_quantile"],shape))
        values = cutoff + stats.genpareto.rvs(
            shape,scale=1+shape*cutoff,size=size,random_state=rng)
    else:
        p = config["soft_selection"]
        accepted = []
        count = 0
        while count<size:
            u = rng.random(max(4096,4*(size-count)))
            chance = p["background"]+p["amplitude"]*expit((u-p["cdf_center"])/p["cdf_scale"])
            chosen = u[rng.random(len(u))<chance]
            accepted.append(chosen)
            count += len(chosen)
        values = stats.genpareto.ppf(np.concatenate(accepted)[:size],shape)
        cutoff = None
    return np.asarray(values).reshape(tasks,config["failures_per_task"]),cutoff


def sample(seed, setting, config):
    shape = setting["shape"]
    calibration = stats.genpareto.rvs(
        shape,size=(max(config["calibration_budgets"].values()),config["steps_per_calibration_task"]),
        random_state=rng_for(seed,0))
    evaluation,cutoff = failures_sample(rng_for(seed,1),shape,setting,config,config["evaluation_tasks"])
    pilot,_ = failures_sample(rng_for(seed,2),shape,setting,config,config["support_tasks"])
    return calibration,evaluation,pilot,cutoff


def method_thresholds(calibration, evaluation, pilot, cutoff, q):
    tau = float(np.quantile(calibration,1-q))
    return {
        "original":tau,
        "observed_minimum":max(tau,float(evaluation.min())),
        "independent_floor":max(tau,float(pilot.min())),
        "oracle_correct_selection":max(tau,cutoff) if cutoff is not None else None,
        "pooled_original":tau,
    }


def fit_methods(calibration, evaluation, pilot, pooled, cutoff, config):
    thresholds = method_thresholds(calibration,evaluation,pilot,cutoff,config["q"])
    estimates = {}
    cache = {}
    for name,tau in thresholds.items():
        if tau is None:
            estimates[name] = None
            continue
        values = pooled if name=="pooled_original" else evaluation
        cache_key = ("pooled" if name=="pooled_original" else "evaluation",tau)
        if cache_key not in cache:
            excess = values[values>tau]-tau
            if len(excess)<5:
                result = {"gamma":None,"shape_estimate":None,"converged":False,"reason":"too_few_excesses"}
            else:
                try:
                    result = finite_json(constrained_gpd_fit(excess).as_dict())
                except (ValueError,FloatingPointError,OverflowError) as error:
                    result = {"gamma":None,"shape_estimate":None,"converged":False,
                              "reason":type(error).__name__+": "+str(error)}
            cache[cache_key] = result
        estimates[name] = cache[cache_key]
    return thresholds,estimates


def evaluate_budget(calibration, evaluation, pilot, cutoff, config, seed, budget_id):
    pooled = np.concatenate([evaluation,pilot])
    thresholds,points = fit_methods(calibration,evaluation,pilot,pooled,cutoff,config)
    B = config["statistics"]["bootstrap"]
    count = len(METHODS)
    shape = np.full((B,count),np.nan)
    raw_gamma = np.full((B,count),np.nan)
    threshold_draws = np.full((B,count),np.nan)
    reason = np.full((B,count),"not_applicable",dtype="U160")
    # Each dataset/budget/group has a separate deterministic bootstrap stream.
    streams = {role:rng_for(seed,100+10*budget_id+role) for role in range(4)}
    for b in range(B):
        cal = calibration[streams[0].integers(len(calibration),size=len(calibration))]
        ev = evaluation[streams[1].integers(len(evaluation),size=len(evaluation))]
        support = pilot[streams[2].integers(len(pilot),size=len(pilot))]
        pool = pooled[streams[3].integers(len(pooled),size=len(pooled))]
        ts,fits = fit_methods(cal,ev,support,pool,cutoff,config)
        for j,name in enumerate(METHODS):
            obj = fits[name]
            if obj is None:
                continue
            threshold_draws[b,j] = ts[name]
            if obj["shape_estimate"] is not None:
                shape[b,j] = obj["shape_estimate"]
            if obj["gamma"] is not None:
                raw_gamma[b,j] = obj["gamma"]
            reason[b,j] = obj["reason"]
    results = {}
    for j,name in enumerate(METHODS):
        tau = thresholds[name]
        if tau is None:
            results[name] = {"applicable":False,"reason":"no hard support oracle for soft selection"}
            continue
        values = pooled if name=="pooled_original" else evaluation
        counts = {
            "calibration_tail_tasks":int(np.any(calibration>tau,axis=1).sum()),
            "calibration_excesses":int((calibration>tau).sum()),
            "failure_tail_tasks":int(np.any(values>tau,axis=1).sum()),
            "failure_excesses":int((values>tau).sum()),
        }
        failures = [k+"_insufficient" for k,n in counts.items() if n<config["eligibility"][k]]
        percentile = intervals(shape[:,j],config,min(len(calibration),counts["failure_tail_tasks"]))
        if percentile["valid"]/B < config["statistics"]["valid_fraction"]:
            failures.append("too_few_finite_bootstrap_fits")
        point = points[name]["shape_estimate"]
        if point is None:
            failures.append("point_unusable")
        if min(len(calibration),counts["failure_tail_tasks"]) < config["statistics"]["min_tasks"]:
            failures.append("too_few_independent_tasks")
        if failures:
            percentile["ci95"] = percentile["ci_family"] = None
        basic = {key:[2*point-bounds[1],2*point-bounds[0]] if bounds is not None else None
                 for key,bounds in ((key,percentile[key]) for key in ["ci95","ci_family"])}
        results[name] = {
            "applicable":True,"threshold":tau,"point":point,"point_fit":points[name],
            "counts":counts,"unavailable_reasons":failures,
            "percentile":percentile,"basic":basic,
            "bootstrap_fit_reasons":dict(Counter(reason[:,j])),
            "threshold_below_true_support":tau<cutoff if cutoff is not None else None,
            "bootstrap_threshold_below_true_support":int((threshold_draws[:,j]<cutoff).sum()) if cutoff is not None else None,
        }
    arrays = {"shape":shape,"raw_gamma":raw_gamma,"threshold":threshold_draws,"reason":reason}
    return finite_json(results),arrays


def analyze_dataset(config, scenario, index):
    setting = config["scenarios"][scenario]
    seed = config["seed"]+setting["seed_offset"]+index
    calibration,evaluation,pilot,cutoff = sample(seed,setting,config)
    methods,arrays = {},{}
    for i,(name,tasks) in enumerate(config["calibration_budgets"].items()):
        values,draws = evaluate_budget(calibration[:tasks],evaluation,pilot,cutoff,config,seed,i)
        methods[name] = values
        for key,value in draws.items():
            arrays[name+"_"+key] = value
    return finite_json({
        "trace_id":scenario+":"+str(index),
        "request":{"scenario":scenario,"index":index,"seed":seed},
        "truth":setting["shape"],"selection":setting["selection"],
        "true_support_diagnostic_only":cutoff,"methods":methods,
        "data_cost":{"calibration_tasks":config["calibration_budgets"],
                     "evaluation_tasks":len(evaluation),"support_tasks":len(pilot),
                     "pooled_failure_tasks":len(evaluation)+len(pilot)},
    }),arrays
