"""Task-level controls and Monte Carlo audits using the actual E1 interval procedure."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from ..e1.analysis import finite_json, localization, overshoot
from ..e1.artifacts import Journal, digest, finish, identity, read_json, verify_manifest, write_once
from ..e1.main_analysis import bootstrap_cell


def positional_null(
    frame: pd.DataFrame, permutations: int = 999, seed: int = 20260911
) -> dict[str, Any]:
    """One predetermined refuted trace per task, then permute t* within family and exact L.

    Using one trace prevents a task with many attempts from becoming multiple independent units.
    Sparse strata stay excluded. This restricted-population control does not replace full P2.
    """
    picked: dict[str, dict[str, Any]] = {}
    for trace_id, group in frame[frame["outcome"] == "refuted"].groupby("trace_id", sort=True):
        group = group.sort_values("t")
        task = str(group["prompt_id"].iloc[0])
        if task in picked or not np.isfinite(group[["z", "surprisal"]].to_numpy()).all():
            continue
        # Earliest trace ID is fixed by attempt identity, independent of its score and t*.
        picked[task] = {
            "trace_id": str(trace_id),
            "task": task,
            "L": len(group),
            "family": str(group["task_family"].iloc[0]),
            "failure": int(group["t_star"].iloc[0]),
            "jump": int(np.argmax(group["z"].to_numpy())),
            "surprisal": int(np.argmax(group["surprisal"].to_numpy())),
        }
    strata: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in picked.values():
        strata[row["family"], row["L"]].append(row)
    eligible = [v for v in strata.values() if len(v) >= 2]
    n = sum(len(v) for v in eligible)
    out: dict[str, Any] = {
        "unit": "task",
        "selection": "first eligible trace ID per task",
        "n_tasks": n,
        "omitted_sparse_tasks": len(picked) - n,
        "strata": [{"family": k[0], "L": k[1], "tasks": len(v)} for k, v in sorted(strata.items())],
        "permutations": permutations,
        "p_jump": None,
        "p_paired_gain": None,
        "decision": "inconclusive",
    }
    if not n:
        out["reason"] = "no stratum contains two independent tasks"
        return out
    obs_jump = sum(r["jump"] == r["failure"] for rows in eligible for r in rows) / n
    obs_base = sum(r["surprisal"] == r["failure"] for rows in eligible for r in rows) / n
    rng = np.random.default_rng(seed)
    draws = np.zeros((permutations, 2))
    for i in range(permutations):
        for records in eligible:
            failure = rng.permutation([r["failure"] for r in records])
            draws[i, 0] += np.sum(failure == np.array([r["jump"] for r in records]))
            draws[i, 1] += np.sum(failure == np.array([r["surprisal"] for r in records]))
    draws /= n
    out.update(
        jump_top1=obs_jump,
        surprisal_top1=obs_base,
        paired_gain=obs_jump - obs_base,
        null_jump_mean=float(draws[:, 0].mean()),
        null_gain_mean=float(np.diff(draws[:, ::-1], axis=1).mean()),
        p_jump=float((1 + np.sum(draws[:, 0] >= obs_jump)) / (permutations + 1)),
        p_paired_gain=float(
            (1 + np.sum(draws[:, 0] - draws[:, 1] >= obs_jump - obs_base)) / (permutations + 1)
        ),
        sufficient_tasks=n >= 20,
        reason="restricted task population; exact-family/length exchangeability assumption",
    )
    return finite_json(out)


def simulated_cell(
    scenario: str, seed: int, tasks: int = 48, attempts: int = 6, length: int = 8
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    rng = np.random.default_rng(seed)
    if scenario not in {"heavy_null", "position_null", "tail_alternative", "coupled_overshoot"}:
        raise ValueError("unknown simulation scenario")
    target = {"P1": 0.4 if scenario == "tail_alternative" else 0.0, "P3": 0.25}
    frames = []
    true_tau = float(stats.genpareto.ppf(0.99, 0.25))
    for role in ("calibration", "evaluation"):
        records = []
        for task in range(tasks):
            scale = np.exp(rng.normal(0, 0.2)) if scenario != "coupled_overshoot" else 1.0
            for attempt in range(attempts):
                refuted = role == "evaluation" and attempt % 2 == 0
                fail = int(rng.integers(length)) if refuted else None
                gamma = 0.1 if scenario == "tail_alternative" else 0.25
                z = stats.genpareto.rvs(gamma, size=length, random_state=rng) * scale
                base = stats.genpareto.rvs(gamma, size=length, random_state=rng) * scale
                if scenario == "position_null":
                    gradient = np.exp(np.linspace(0, 3, length))
                    z *= gradient
                    base *= gradient
                    if refuted:
                        fail = int(rng.choice(length, p=gradient / gradient.sum()))
                if refuted and scenario == "tail_alternative":
                    assert fail is not None
                    z[fail:] = (
                        stats.genpareto.rvs(0.5, size=length - int(fail), random_state=rng) * scale
                    )
                if refuted and scenario == "coupled_overshoot":
                    assert fail is not None
                    z[:fail] = stats.genpareto.ppf(rng.uniform(0, 0.99, int(fail)), 0.25)
                    z[fail] = true_tau + stats.genpareto.rvs(
                        0.25, scale=1 + 0.25 * true_tau, random_state=rng
                    )
                for t in range(length):
                    records.append(
                        {
                            "prompt_id": f"{role}:{task}",
                            "trace_id": f"{role}:{task}:{attempt}",
                            "task_family": "simulation",
                            "outcome": "refuted" if refuted else "verified",
                            "t": t,
                            "t_star": fail,
                            "L": length,
                            "z": z[t],
                            "surprisal": base[t],
                        }
                    )
        frames.append(pd.DataFrame(records))
    return frames[0], frames[1], target


def calibrate(
    folder: Path, config: dict[str, Any], source: Path, scenario: str, shard: int
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    context = {
        "source": digest(source),
        "config": identity(config),
        "scenario": scenario,
        "shard": shard,
    }
    path = folder / "replicates.jsonl"
    start = shard * config["datasets_per_shard"]
    with Journal(path, context) as journal:
        for index in range(start, start + config["datasets_per_shard"]):
            request = {"scenario": scenario, "index": index, "seed": config["seed"] + index}
            rid = f"{scenario}:{index}"
            if journal.existing(rid, identity(request)) is not None:
                continue
            cal, evaluation, target = simulated_cell(
                scenario, request["seed"], config["tasks"], config["attempts"], config["length"]
            )
            analysis_config = {"seed": request["seed"], "statistics": config["statistics"]}
            boot = bootstrap_cell(cal, evaluation, analysis_config)
            p1 = boot["P1_direct_moment_difference"]
            p3 = boot["P3"]["0.01"]["shape"]
            p2 = positional_null(evaluation, config["permutations"], request["seed"])

            def assess(interval: dict[str, Any], truth: float) -> dict[str, Any]:
                ci = interval.get("ci95")
                family = interval.get("ci_family")
                return {
                    "valid_replicates": interval["valid"],
                    "ci95": ci,
                    "ci_family": family,
                    "covers_truth": None if ci is None else ci[0] <= truth <= ci[1],
                    "rejects_zero_positive": False if family is None else family[0] > 0,
                }

            journal.append(
                {
                    "trace_id": rid,
                    "request": request,
                    "truth": target,
                    "P1": assess(p1, target["P1"]),
                    "P3": assess(p3, target["P3"]),
                    "P2": p2,
                    "P3_sample": overshoot(cal, evaluation, 0.01),
                },
                identity(request),
            )
            print(f"Monte Carlo {rid} complete", flush=True)
    finish(
        folder,
        stage="e1-monte-carlo-calibration",
        context=context,
        inputs=[source],
        outputs=[path, path.with_suffix(".identity.json")],
        metrics={"scenario": scenario, "datasets": config["datasets_per_shard"], "config": config},
    )


def sidecar(folder: Path, model_root: Path, phase: str, source: Path) -> None:
    manifest = model_root / phase / "measurement/manifest.json"
    verify_manifest(manifest)
    config = read_json(model_root / phase / "protocol.json")
    table = pd.read_parquet(manifest.parent / "deviations.parquet")
    selected = table[
        (table["temperature"] == config["primary_temperature"])
        & (table["layer"] == config["primary_layer"])
        & table["primary_eligible"]
    ]
    results = {}
    for statistic, frame in selected.groupby("statistic"):
        evaluation = frame[frame["role"] == "evaluation"]
        results[str(statistic)] = {
            "positional_null": positional_null(evaluation),
            "P2": localization(evaluation, config),
        }
    path = write_once(
        folder / "metrics.json",
        finite_json({"phase": phase, "cells": results, "decision": "inconclusive"}),
    )
    finish(
        folder,
        stage="e1-positional-control",
        context={"source": digest(source)},
        inputs=[source, manifest, model_root / phase / "protocol.json"],
        outputs=[path],
        metrics={"cells": len(results)},
    )


def summarize_calibration(folder: Path, root: Path, source: Path) -> None:
    from ..e1.stages import rows

    manifests = sorted(root.glob("*/*/manifest.json"))
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for manifest in manifests:
        verify_manifest(manifest)
        for row in rows(manifest.parent / "replicates.jsonl"):
            records[row["request"]["scenario"]].append(row)

    def proportion(values: list[bool]) -> dict[str, Any]:
        n, k = len(values), sum(values)
        lo = float(stats.beta.ppf(0.025, k, n - k + 1)) if k else 0.0
        hi = float(stats.beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
        return {
            "successes": k,
            "datasets": n,
            "fraction": k / n if n else None,
            "monte_carlo_ci95": [lo, hi] if n else None,
        }

    metrics: dict[str, Any] = {
        "scenarios": {},
        "decision": "inconclusive",
        "scope": "finite-sample calibration screen on prespecified distributions; does not establish coverage for transformer data",
    }
    for scenario, sample in sorted(records.items()):
        if len({r["trace_id"] for r in sample}) != len(sample):
            raise ValueError("duplicate Monte Carlo dataset")
        result: dict[str, Any] = {"datasets": len(sample)}
        for name in ("P1", "P3"):
            available = [r[name] for r in sample if r[name]["ci95"] is not None]
            result[name] = {
                "availability": proportion([r[name]["ci95"] is not None for r in sample]),
                "coverage_among_available": proportion([r["covers_truth"] for r in available]),
                "family_positive_rejection_all_datasets": proportion(
                    [r[name]["rejects_zero_positive"] for r in sample]
                ),
            }
        result["P2"] = {
            "task_permutation_rejection_005": proportion(
                [r["P2"].get("p_paired_gain", 1) <= 0.05 for r in sample]
            )
        }
        metrics["scenarios"][scenario] = result
    path = write_once(folder / "metrics.json", finite_json(metrics))
    finish(
        folder,
        stage="monte-carlo-calibration-summary",
        context={"source": digest(source)},
        inputs=[source, *manifests],
        outputs=[path],
        metrics={"scenarios": len(records)},
    )
