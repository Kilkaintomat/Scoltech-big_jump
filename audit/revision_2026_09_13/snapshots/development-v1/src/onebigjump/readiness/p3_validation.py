"""Independent validation of a prespecified, observable support adjustment for P3.

This diagnostic cannot change the main method. The candidate threshold is the
larger of the calibration quantile and the smallest observed failure value.
Both are re-estimated in every task bootstrap; true support is never an input.
"""

from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from ..e1.analysis import finite_json
from ..e1.artifacts import Journal, digest, finish, identity, read_json, verify_manifest, write_once
from ..e1.main_analysis import intervals
from ..e1.stages import rows
from .p3_diagnosis import draw_sample, shape_at


def thresholds(calibration, failures, q):
    tau = float(np.quantile(calibration, 1 - q))
    observed = np.asarray(failures)[np.isfinite(failures)]
    return {"original": tau, "observed_support": max(tau, float(observed.min()))}


def evaluate(calibration, failures, config, seed):
    points = thresholds(calibration, failures, config["q"])
    shapes = {name: shape_at(failures, tau) for name, tau in points.items()}
    rng = np.random.default_rng(seed)
    draws = {name: np.full(config["statistics"]["bootstrap"], np.nan) for name in points}
    for b in range(config["statistics"]["bootstrap"]):
        cal = calibration[rng.integers(len(calibration), size=len(calibration))]
        fail = failures[rng.integers(len(failures), size=len(failures))]
        for name, tau in thresholds(cal, fail, config["q"]).items():
            draws[name][b] = shape_at(fail, tau)
    results = {}
    for name, tau in points.items():
        cal_tasks = int(np.any(calibration > tau, axis=1).sum())
        cal_steps = int((calibration > tau).sum())
        failure_tasks = int(np.any(failures > tau, axis=1).sum())
        failure_steps = int((failures > tau).sum())
        enough = cal_tasks >= 10 and cal_steps >= 20 and failure_tasks >= 20 and failure_steps >= 50
        percentile = intervals(draws[name], config, min(len(calibration), failure_tasks))
        if not enough:
            percentile["ci95"] = percentile["ci_family"] = None
        basic = {}
        for key in ("ci95", "ci_family"):
            bounds = percentile[key]
            basic[key] = (
                [2 * shapes[name] - bounds[1], 2 * shapes[name] - bounds[0]]
                if bounds is not None and np.isfinite(shapes[name])
                else None
            )
        results[name] = {
            "threshold": tau,
            "point": shapes[name],
            "calibration_tail_tasks": cal_tasks,
            "calibration_excesses": cal_steps,
            "failure_tail_tasks": failure_tasks,
            "failure_excesses": failure_steps,
            "percentile": percentile,
            "basic": basic,
        }
    return finite_json(results)


def run(folder: Path, protocol: Path, source: Path, shard: int):
    config = read_json(protocol)
    path = folder / "replicates.jsonl"
    context = {"source": digest(source), "protocol": digest(protocol), "shard": shard}
    with Journal(path, context) as journal:
        for index in range(shard * config["per_shard"], (shard + 1) * config["per_shard"]):
            for scenario, settings in config["scenarios"].items():
                seed = config["seed"] + index + settings["seed_offset"]
                request = {"scenario": scenario, "index": index, "seed": seed}
                rid = f"{scenario}:{index}"
                if journal.existing(rid, identity(request)) is not None:
                    continue
                cal, fail, cutoff = draw_sample(
                    seed, settings["shape"], settings["failure_quantile"], tasks=config["tasks"]
                )
                result = evaluate(cal, fail, config, seed + 10000000)
                journal.append(
                    {
                        "trace_id": rid,
                        "request": request,
                        "truth": settings["shape"],
                        "true_support_diagnostic_only": cutoff,
                        "methods": result,
                    },
                    identity(request),
                )
                print(rid, "complete", flush=True)
    finish(
        folder,
        stage="independent-p3-candidate-validation",
        context=context,
        inputs=[source, protocol],
        outputs=[path, path.with_suffix(".identity.json")],
        metrics={"config": config, "shard": shard, "main_method_changed": False},
    )


def proportion(values):
    n, k = len(values), sum(values)
    return {
        "successes": k,
        "datasets": n,
        "fraction": k / n if n else None,
        "monte_carlo_ci95": [
            float(stats.beta.ppf(0.025, k, n - k + 1)) if k else 0.0,
            float(stats.beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0,
        ]
        if n
        else None,
    }


def summarize(folder: Path, root: Path, protocol: Path, source: Path):
    config = read_json(protocol)
    manifests = sorted(root.glob("shard-*/manifest.json"))
    records = []
    for manifest in manifests:
        verify_manifest(manifest)
        records.extend(rows(manifest.parent / "replicates.jsonl"))
    expected = {f"{name}:{i}" for name in config["scenarios"] for i in range(config["datasets"])}
    if len(records) != len(expected) or {r["trace_id"] for r in records} != expected:
        raise ValueError("incomplete or duplicate validation population")
    result: dict[str, Any] = {}
    for scenario in config["scenarios"]:
        sample = [r for r in records if r["request"]["scenario"] == scenario]
        result[scenario] = {}
        for candidate in ("original", "observed_support"):
            for method in ("percentile", "basic"):
                cells = [(r, r["methods"][candidate][method]) for r in sample]
                available = [(r, c) for r, c in cells if c["ci95"] is not None]
                coverage = proportion(
                    [c["ci95"][0] <= r["truth"] <= c["ci95"][1] for r, c in available]
                )
                mc = coverage["monte_carlo_ci95"]
                result[scenario][candidate + "_" + method] = {
                    "availability": proportion([c["ci95"] is not None for _, c in cells]),
                    "coverage_conditional_on_available": coverage,
                    "coverage_counting_unavailable_as_failure": proportion(
                        [
                            c["ci95"] is not None and c["ci95"][0] <= r["truth"] <= c["ci95"][1]
                            for r, c in cells
                        ]
                    ),
                    "positive_family_rejection": proportion(
                        [c["ci_family"] is not None and c["ci_family"][0] > 0 for _, c in cells]
                    ),
                    "point_bias_when_interval_available": float(
                        np.mean(
                            [r["methods"][candidate]["point"] - r["truth"] for r, _ in available]
                        )
                    )
                    if available
                    else None,
                    "undercoverage_detected": mc is not None and mc[1] < 0.95,
                }
    output = write_once(
        folder / "metrics.json",
        finite_json(
            {
                "scenarios": result,
                "main_method_changed": False,
                "decision": "diagnostic_only",
                "datasets": len(records),
                "protocol": config,
                "interpretation": "no automatic promotion; not detecting undercoverage does not prove calibration",
            }
        ),
    )
    finish(
        folder,
        stage="p3-candidate-validation-summary",
        context={"source": digest(source)},
        inputs=[source, protocol, *manifests],
        outputs=[output],
        metrics={"datasets": len(records), "main_method_changed": False},
    )
