"""Full-population P1-P3 measurements with joint task resampling and explicit inference limits."""

from __future__ import annotations

import concurrent.futures
from collections import Counter
from contextlib import suppress
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..experiments.p2_localization import _rank_of
from ..stats import gpd_fit, gpd_from_order_statistics, hill, moment, select_k
from .analysis import finite_json, localization, overshoot, tail
from .artifacts import digest, finish, read_json, write_once
from .campaign import require_collection_gate
from .stages import completed, configuration, generation_inputs, rows

ESTIMATORS = ("hill", "moment", "gpd")


def subsets(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    refuted = frame[frame["outcome"] == "refuted"]
    return {
        "verified": frame[frame["outcome"] == "verified"],
        "refuted_all": refuted,
        "pre": refuted[refuted["t"] < refuted["t_star"]],
        "at": refuted[refuted["t"] == refuted["t_star"]],
        "post": refuted[refuted["t"] > refuted["t_star"]],
        "at_post": refuted[refuted["t"] >= refuted["t_star"]],
    }


def estimate(x: np.ndarray, config: dict[str, Any], seed: int) -> np.ndarray:
    x = x[np.isfinite(x) & (x > 0)]
    out = np.full(3, np.nan)
    if len(x) < 50:
        return out
    k = select_k(
        x,
        "double_bootstrap",
        k_min=config["statistics"]["min_k"],
        resamples=config["statistics"]["inner_bootstrap"],
        seed=seed,
    ).k
    for i, fn in enumerate(
        (hill, moment, lambda z, kk: gpd_from_order_statistics(z, kk).shape_estimate)
    ):
        with suppress(ValueError, FloatingPointError):
            out[i] = fn(x, k)
    return out


def intervals(values: np.ndarray, config: dict[str, Any], n_tasks: int) -> dict[str, Any]:
    values = np.asarray(values)
    valid = values[np.isfinite(values)]
    result: dict[str, Any] = {
        "bootstrap_unit": "task",
        "n_tasks": n_tasks,
        "replicates": len(values),
        "valid": len(valid),
        "ci95": None,
        "ci_family": None,
    }
    if n_tasks < config["statistics"]["min_tasks"]:
        result["reason"] = "fewer than 20 independent tasks; no attempt-level fallback"
    elif not len(values) or len(valid) / len(values) < config["statistics"]["valid_fraction"]:
        result["reason"] = "insufficient finite bootstrap replicates"
    else:
        alpha = 0.05 / config["statistics"].get("family_size", 9)
        result["ci95"] = np.quantile(valid, [0.025, 0.975]).tolist()
        result["ci_family"] = np.quantile(valid, [alpha / 2, 1 - alpha / 2]).tolist()
        result["reason"] = "descriptive variance approximation; bias and coverage not calibrated"
    return result


def paired_scores(frame: pd.DataFrame) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for _, group in frame[frame["outcome"] == "refuted"].groupby("trace_id"):
        group = group.sort_values("t")
        if not np.isfinite(group["surprisal"]).all():
            continue
        fail = int(group["t_star"].iloc[0])
        difference = int(_rank_of(group["z"].to_numpy(), fail) == 1) - int(
            _rank_of(group["surprisal"].to_numpy(), fail) == 1
        )
        result.setdefault(str(group["prompt_id"].iloc[0]), []).append(float(difference))
    return result


def bootstrap_cell(
    calibration: pd.DataFrame, evaluation: pd.DataFrame, config: dict[str, Any]
) -> dict[str, Any]:
    groups = {str(k): v for k, v in evaluation.groupby("prompt_id")}
    calibration = calibration[calibration["outcome"] == "verified"]
    cal_groups = {str(k): v["z"].to_numpy() for k, v in calibration.groupby("prompt_id")}
    keys, cal_keys = sorted(groups), sorted(cal_groups)
    point_subsets = subsets(evaluation)
    b = config["statistics"]["bootstrap"]
    rng = np.random.default_rng(config["seed"])
    tail_draws = {key: np.full((b, 3), np.nan) for key in point_subsets}
    difference = np.full(b, np.nan)
    pair = np.full(b, np.nan)
    overshoot_draws = {q: np.full(b, np.nan) for q in (0.01, 0.02, 0.005, 0.001)}
    overshoot_difference = {q: np.full(b, np.nan) for q in overshoot_draws}
    bands: dict[str, dict[str, Any]] = {}
    for name, frame in point_subsets.items():
        x = frame.loc[frame["z"] > 0, "z"].to_numpy()
        if len(x) >= 50:
            grid = np.arange(20, len(x) // 2 + 1)
            # Curves use every feasible k; bands retain the same tail fractions when n changes.
            bands[name] = {
                "k": grid,
                "fraction": grid / len(x),
                "hill": np.full((b, len(grid)), np.nan),
            }
    scores = paired_scores(evaluation)
    score_keys = sorted(scores)
    if len(keys) >= config["statistics"]["min_tasks"]:
        for r in range(b):
            selected = rng.choice(keys, size=len(keys), replace=True)
            sampled = pd.concat([groups[k] for k in selected], ignore_index=True)
            parts = subsets(sampled)
            for name, part in parts.items():
                if point_subsets[name]["prompt_id"].nunique() < config["statistics"]["min_tasks"]:
                    continue
                x = part["z"].to_numpy(dtype=float)
                tail_draws[name][r] = estimate(x, config, config["seed"] + r)
                if name in bands:
                    from ..stats.hill import log_moments

                    positive = x[np.isfinite(x) & (x > 0)]
                    if len(positive) >= 22:
                        k = np.clip(
                            np.rint(bands[name]["fraction"] * len(positive)).astype(int),
                            1,
                            len(positive) - 1,
                        )
                        _, m1, _ = log_moments(positive, k_max=int(k.max()))
                        bands[name]["hill"][r] = m1[k - 1]
            difference[r] = tail_draws["refuted_all"][r, 1] - tail_draws["verified"][r, 1]
            if len(cal_keys) >= config["statistics"]["min_tasks"]:
                cal_x = np.concatenate(
                    [cal_groups[k] for k in rng.choice(cal_keys, size=len(cal_keys), replace=True)]
                )
                failures = parts["at"]["z"].to_numpy()
                for q in overshoot_draws:
                    tau = float(np.quantile(cal_x, 1 - q))
                    excess = failures[failures > tau] - tau
                    if len(excess) >= 5:
                        try:
                            overshoot_draws[q][r] = gpd_fit(excess, threshold=tau).shape_estimate
                            overshoot_difference[q][r] = (
                                overshoot_draws[q][r] - tail_draws["at_post"][r, 2]
                            )
                        except (ValueError, FloatingPointError):
                            pass
    if len(score_keys) >= config["statistics"]["min_tasks"]:
        for r in range(b):
            pair[r] = np.mean(
                [
                    v
                    for k in rng.choice(score_keys, size=len(score_keys), replace=True)
                    for v in scores[k]
                ]
            )
    out: dict[str, Any] = {
        "P1": {},
        "P1_direct_moment_difference": intervals(
            difference,
            config,
            min(int(point_subsets[k]["prompt_id"].nunique()) for k in ("verified", "refuted_all")),
        ),
        "P2_paired_difference": intervals(pair, config, len(scores)),
        "P3": {},
        "k_reselected_each_replicate": True,
        "whitening_refitted": False,
        "conditional_on_fitted_transform": True,
    }
    for name, values in tail_draws.items():
        n_tasks = int(point_subsets[name]["prompt_id"].nunique())
        out["P1"][name] = {
            est: intervals(values[:, i], config, n_tasks) for i, est in enumerate(ESTIMATORS)
        }
        if name in bands:
            curve = bands[name]
            valid = np.isfinite(curve["hill"]).all(axis=1)
            out["P1"][name]["hill_bands"] = {
                "k": curve["k"].tolist(),
                "valid": int(valid.sum()),
                "lower": None,
                "upper": None,
                "pointwise": True,
                "simultaneous": False,
            }
            if valid.mean() >= config["statistics"]["valid_fraction"]:
                lo, hi = np.quantile(curve["hill"][valid], [0.025, 0.975], axis=0)
                out["P1"][name]["hill_bands"].update(lower=lo.tolist(), upper=hi.tolist())
    for q, values in overshoot_draws.items():
        point = overshoot(calibration, evaluation, q)
        excess_tasks = point.get("positive_excess_tasks", 0)
        n_tasks = min(len(cal_keys), excess_tasks)
        sufficient = (
            point.get("calibration_exceedances", 0) >= (100 if q == 0.001 else 20)
            and point.get("calibration_tail_tasks", 0) >= (20 if q == 0.001 else 10)
            and point.get("positive_excesses", 0) >= 50
            and excess_tasks >= config["statistics"]["min_tasks"]
        )
        shape = intervals(values, config, n_tasks)
        contrast = intervals(overshoot_difference[q], config, n_tasks)
        if not sufficient:
            for result in (shape, contrast):
                result.update(
                    ci95=None,
                    ci_family=None,
                    reason="insufficient independent calibration/evaluation exceedances",
                )
        out["P3"][str(q)] = {
            "shape": shape,
            "difference_from_pooled_gpd": contrast,
            "positive_excess_tasks": excess_tasks,
            "calibration_tail_tasks": point.get("calibration_tail_tasks", 0),
            "sufficient_sample": sufficient,
        }
    return finite_json(out)


def analyze_cell(args: tuple[str, dict[str, Any], float, int, str]) -> dict[str, Any]:
    table_path, config, temperature, layer, statistic = args
    table = pd.read_parquet(table_path)
    cell = table[
        (table["temperature"] == temperature)
        & (table["layer"] == layer)
        & (table["statistic"] == statistic)
    ]
    evaluation = cell[(cell["role"] == "evaluation") & cell["primary_eligible"]]
    calibration = cell[cell["role"] == "calibration"]
    parts = subsets(evaluation)
    p1 = {name: tail(part, config) for name, part in parts.items()}
    for point in p1.values():
        sufficient = (
            point["n_tasks"] >= config["statistics"]["min_tasks"]
            and point["n_positive"] >= config["statistics"]["min_steps"]
            and point.get("tail_tasks", 0) >= config["statistics"]["min_tail_tasks"]
        )
        point["sufficient_sample"] = sufficient
        point["reason"] = (
            "scientific calibration/manual review pending"
            if sufficient
            else "insufficient independent tasks, steps or tail tasks"
        )
        if point.get("stability"):
            point["stability"]["bands_reason"] = "see task_bootstrap for full pointwise Hill bands"
    p2 = localization(evaluation, config)
    p2["reason"] = "descriptive localization; task-stratified positional null/calibration pending"
    p3 = [overshoot(calibration, evaluation, q) for q in (0.01, 0.02, 0.005, 0.001)]
    for result in p3:
        sufficient = (
            result.get("calibration_exceedances", 0) >= (100 if result["q"] == 0.001 else 20)
            and result.get("calibration_tail_tasks", 0) >= (20 if result["q"] == 0.001 else 10)
            and result.get("positive_excesses", 0) >= 50
            and result.get("positive_excess_tasks", 0) >= 20
        )
        result["sufficient_sample"] = sufficient
        result["reason"] = (
            "descriptive compatibility only; no equivalence margin specified"
            if sufficient
            else "insufficient calibration/evaluation exceedances"
        )
    family_estimates: dict[str, Any] = {}
    for name, frame in evaluation.groupby("task_family"):
        family_estimates[str(name)] = {}
        for subset_name, subset in subsets(frame).items():
            point = tail(subset, config)
            point["reason"] = "exploratory per-family point estimates; no inferential claim"
            family_estimates[str(name)][subset_name] = point
    return finite_json(
        {
            "temperature": temperature,
            "layer": layer,
            "statistic": statistic,
            "available": not cell.empty,
            "P1": p1,
            "P2": p2,
            "P3": p3,
            "task_bootstrap": bootstrap_cell(calibration, evaluation, config),
            "P1_exclude_first": {
                name: {
                    **tail(part[part["t"] > 0], config),
                    "reason": "exploratory first-increment sensitivity",
                }
                for name, part in parts.items()
            },
            "family_estimates": family_estimates,
            "decision": "inconclusive",
        }
    )


def analyze(root: Path, phase: str, source: Path) -> None:
    if phase != "main":
        raise ValueError("full-population analysis requires main")
    config = configuration(root, phase)
    gate = require_collection_gate(root, source)
    directory = root / phase / "analysis"
    if completed(directory):
        return
    upstream = root / phase / "measurement"
    if not completed(upstream):
        raise ValueError("measurement incomplete")
    samples, _ = generation_inputs(root, phase)
    labels = rows(root / phase / "verification/labels.jsonl")
    extracted = rows(root / phase / "extraction/trajectories.jsonl")
    ids = {r["trace_id"] for r in samples}
    if any({r["trace_id"] for r in records} != ids for records in (labels, extracted)):
        raise ValueError("main attempt accounting mismatch")
    args = [
        (str(upstream / "deviations.parquet"), config, temperature, layer, statistic)
        for temperature in config["temperatures"]
        for layer in config["layers"]
        for statistic in ("raw", "whitened", "innovation")
    ]
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    pending = []
    for arg in args:
        path = directory / f"cell-T{arg[2]}-layer{arg[3]}-{arg[4]}.json"
        if path.exists():
            # A cell receipt binds inputs and source, including partial-stage resume.
            receipt = read_json(path.with_suffix(".identity.json"))
            if receipt != {
                "source": digest(source),
                "measurement": digest(upstream / "manifest.json"),
                "config": digest(root / phase / "protocol.json"),
            }:
                raise ValueError("analysis cell resume inputs changed")
            if read_json(path.with_suffix(".digest.json")) != digest(path):
                raise ValueError("analysis cell changed")
            files.extend(
                [path, path.with_suffix(".identity.json"), path.with_suffix(".digest.json")]
            )
        else:
            pending.append(arg)
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        for arg, result in zip(pending, pool.map(analyze_cell, pending), strict=True):
            path = directory / f"cell-T{arg[2]}-layer{arg[3]}-{arg[4]}.json"
            write_once(path, result)
            write_once(
                path.with_suffix(".identity.json"),
                {
                    "source": digest(source),
                    "measurement": digest(upstream / "manifest.json"),
                    "config": digest(root / phase / "protocol.json"),
                },
            )
            write_once(path.with_suffix(".digest.json"), digest(path))
            files.extend(
                [path, path.with_suffix(".identity.json"), path.with_suffix(".digest.json")]
            )
            print("ANALYZED", path.name, flush=True)
    payload = {
        "phase": phase,
        "model_id": config["model_id"],
        "model_revision": config["revision"],
        "planned_attempts": len(samples),
        "categories": dict(Counter(r["category"] for r in labels)),
        "extraction_categories": dict(Counter(r["extraction_status"] for r in extracted)),
        "generation_tokens": sum(len(r["completion_token_ids"]) for r in samples),
        "cells": [read_json(directory / f"cell-T{a[2]}-layer{a[3]}-{a[4]}.json") for a in args],
        "scientific_decision": "inconclusive",
        "inference_limitations": [
            "full-sample task bootstrap approximates variance, not calibrated tail bias/coverage",
            "manual review and simulation calibration required before a supported claim",
            "whitening is fixed within task bootstrap; task-refitted sensitivity pending",
            "task-stratified positional null pending; within-trace permutation is descriptive",
            "not an untouched benchmark; model training contamination unknown",
        ],
    }
    metrics = write_once(directory / "metrics.json", finite_json(payload))
    lines = [
        "# Full Lean campaign: " + config["model_id"],
        "",
        "Full-population measurements completed. Scientific claims remain inconclusive.",
        "",
        f"Planned and accounted attempts: {len(samples)}.",
        "",
        "| Lean category | Attempts |",
        "|---|---:|",
    ]
    lines += [f"| {k} | {v} |" for k, v in sorted(payload["categories"].items())]
    lines += [
        "",
        "All temperatures, layers, estimators, exclusions and task-bootstrap intervals:",
        "[metrics.json](metrics.json).",
        "",
        "Inference limitations:",
    ]
    lines += ["- " + text for text in payload["inference_limitations"]]
    report = directory / "REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    finish(
        directory,
        stage="full-population-analysis",
        context={"source": digest(source), "config": digest(root / phase / "protocol.json")},
        inputs=[source, gate, root / phase / "protocol.json", upstream / "manifest.json"],
        outputs=[*files, metrics, report],
        metrics={"attempts": len(samples), "scientific_decision": "inconclusive"},
    )
