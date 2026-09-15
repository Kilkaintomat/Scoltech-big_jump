"""Prespecified P3-only coverage diagnosis; never changes the main estimator or its threshold."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import stats

from ..e1.analysis import finite_json
from ..e1.artifacts import Journal, digest, finish, identity, read_json, verify_manifest, write_once
from ..e1.main_analysis import intervals
from ..e1.stages import rows
from ..stats.gpd import gpd_fit


def draw_sample(seed: int, shape: float, failure_quantile: float, tasks: int = 48):
    """Independent calibration tasks and failure tasks; three failures per task.

    This is the P3 marginal experiment of coupled_overshoot: 6 attempts * 8
    calibration steps, 3 failure values per evaluation task, and unit task scale.
    Omitting unrelated steps avoids running P1 and consumes a separate RNG stream.
    """
    rng = np.random.default_rng(seed)
    calibration = stats.genpareto.rvs(shape, size=(tasks, 48), random_state=rng)
    cutoff = float(stats.genpareto.ppf(failure_quantile, shape))
    failures = cutoff + stats.genpareto.rvs(
        shape, scale=1 + shape * cutoff, size=(tasks, 3), random_state=rng
    )
    return calibration, failures, cutoff


def shape_at(failures: np.ndarray, threshold: float) -> float:
    excess = failures[failures > threshold] - threshold
    if excess.size < 5:
        return float("nan")
    try:
        return gpd_fit(excess, threshold=threshold).shape_estimate
    except (ValueError, FloatingPointError, OverflowError):
        return float("nan")


def diagnose(calibration, failures, cutoff, config, seed):
    q = config["q"]
    tau = float(np.quantile(calibration, 1 - q))
    # Oracle uses the known failure support, solely to separate support mismatch
    # from finite-sample/bootstrap error. It is unavailable for model data.
    thresholds = {"estimated": tau, "oracle": cutoff}
    point = {name: shape_at(failures, value) for name, value in thresholds.items()}
    rng = np.random.default_rng(seed)
    draws = {name: np.full(config["statistics"]["bootstrap"], np.nan) for name in thresholds}
    below = 0
    for b in range(config["statistics"]["bootstrap"]):
        ev = failures[rng.integers(len(failures), size=len(failures))]
        cal = calibration[rng.integers(len(calibration), size=len(calibration))]
        boot_tau = float(np.quantile(cal, 1 - q))
        below += boot_tau < cutoff
        draws["estimated"][b] = shape_at(ev, boot_tau)
        draws["oracle"][b] = shape_at(ev, cutoff)
    results = {}
    for name, threshold in thresholds.items():
        cal_tail_tasks = int(np.any(calibration > threshold, axis=1).sum())
        cal_excesses = int(np.sum(calibration > threshold))
        tail_tasks = int(np.any(failures > threshold, axis=1).sum())
        excesses = int(np.sum(failures > threshold))
        sufficient = (
            cal_tail_tasks >= 10 and cal_excesses >= 20 and tail_tasks >= 20 and excesses >= 50
        )
        interval = intervals(draws[name], config, min(len(calibration), tail_tasks))
        # Same primary-q sample sufficiency rules as bootstrap_cell.
        if not sufficient:
            interval["ci95"] = interval["ci_family"] = None
        basic = {}
        for key in ("ci95", "ci_family"):
            bounds = interval[key]
            basic[key] = (
                None
                if bounds is None or not np.isfinite(point[name])
                else [2 * point[name] - bounds[1], 2 * point[name] - bounds[0]]
            )
        results[name] = {
            "point": point[name],
            "threshold": threshold,
            "tail_tasks": tail_tasks,
            "excesses": excesses,
            "calibration_tail_tasks": cal_tail_tasks,
            "calibration_excesses": cal_excesses,
            "percentile": interval,
            "basic": basic,
        }
    return finite_json(
        {
            "tau": tau,
            "cutoff": cutoff,
            "tau_below_support": tau < cutoff,
            "bootstrap_threshold_below_support_fraction": below / config["statistics"]["bootstrap"],
            "methods": results,
        }
    )


def run(folder: Path, protocol: Path, source: Path, shard: int):
    config = read_json(protocol)
    context = {"source": digest(source), "protocol": digest(protocol), "shard": shard}
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "replicates.jsonl"
    with Journal(path, context) as journal:
        for index in range(shard * config["per_shard"], (shard + 1) * config["per_shard"]):
            for scenario, settings in config["scenarios"].items():
                seed = config["seed"] + index + settings["seed_offset"]
                request = {"scenario": scenario, "index": index, "seed": seed}
                rid = f"{scenario}:{index}"
                if journal.existing(rid, identity(request)) is not None:
                    continue
                cal, fail, cutoff = draw_sample(
                    seed, settings["shape"], settings["failure_quantile"]
                )
                result = diagnose(cal, fail, cutoff, config, seed + 10000000)
                journal.append(
                    {"trace_id": rid, "request": request, "truth": settings["shape"], **result},
                    identity(request),
                )
                print(rid, "complete", flush=True)
    finish(
        folder,
        stage="p3-independent-diagnosis",
        context=context,
        inputs=[source, protocol],
        outputs=[path, path.with_suffix(".identity.json")],
        metrics={"config": config, "shard": shard},
    )


def summarize(folder: Path, root: Path, protocol: Path, source: Path):
    config = read_json(protocol)
    manifests = sorted(root.glob("shard-*/manifest.json"))
    records = []
    for manifest in manifests:
        verify_manifest(manifest)
        records.extend(rows(manifest.parent / "replicates.jsonl"))
    expected = {f"{name}:{i}" for name in config["scenarios"] for i in range(config["datasets"])}
    if len(records) != len(expected) or {r["trace_id"] for r in records} != expected:
        raise ValueError("incomplete or duplicate P3 diagnosis datasets")

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

    output = {}
    for scenario in config["scenarios"]:
        sample = [r for r in records if r["request"]["scenario"] == scenario]
        result = {
            "threshold_below_support": proportion([r["tau_below_support"] for r in sample]),
            "methods": {},
        }
        for threshold in ("estimated", "oracle"):
            for method in ("percentile", "basic"):
                cells = [(r, r["methods"][threshold][method]) for r in sample]
                available = [(r, c) for r, c in cells if c["ci95"] is not None]
                result["methods"][threshold + "_" + method] = {
                    "availability": proportion([c["ci95"] is not None for _, c in cells]),
                    "coverage": proportion(
                        [c["ci95"][0] <= r["truth"] <= c["ci95"][1] for r, c in available]
                    ),
                    "positive_family_rejection": proportion(
                        [c["ci_family"] is not None and c["ci_family"][0] > 0 for _, c in cells]
                    ),
                    "point_bias": float(
                        np.mean(
                            [r["methods"][threshold]["point"] - r["truth"] for r, c in available]
                        )
                    )
                    if available
                    else None,
                    "coverage_when_threshold_below_support": proportion(
                        [
                            c["ci95"][0] <= r["truth"] <= c["ci95"][1]
                            for r, c in available
                            if r["tau_below_support"]
                        ]
                    ),
                    "coverage_when_threshold_above_support": proportion(
                        [
                            c["ci95"][0] <= r["truth"] <= c["ci95"][1]
                            for r, c in available
                            if not r["tau_below_support"]
                        ]
                    ),
                }
        output[scenario] = result
    path = write_once(
        folder / "metrics.json",
        finite_json(
            {
                "scenarios": output,
                "main_method_changed": False,
                "decision": "diagnostic_only",
                "scope": "Independent prespecified marginal P3 simulations; oracle unavailable in real data; no correction promoted automatically.",
            }
        ),
    )
    finish(
        folder,
        stage="p3-diagnosis-summary",
        context={"source": digest(source)},
        inputs=[source, protocol, *manifests],
        outputs=[path],
        metrics={"datasets": len(records)},
    )
