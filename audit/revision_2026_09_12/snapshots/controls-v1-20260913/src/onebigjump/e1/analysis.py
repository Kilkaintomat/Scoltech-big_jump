"""Descriptive pilot P1-P3 measurements; a pilot never supplies confirmatory decisions."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..experiments.p2_localization import (
    _by_length,
    _permutation_null,
    _rank_of,
    _roc,
    localization_rates,
)
from ..stats import gpd_fit, gpd_from_order_statistics, hill, moment, select_k
from .artifacts import digest, finish, write_once
from .stages import completed, configuration, generation_inputs, rows


def finite_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): finite_json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [finite_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return finite_json(value.tolist())
    if isinstance(value, np.generic):
        return finite_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def tail(part: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    positive = part[part["z"] > 0]
    x = positive["z"].to_numpy(dtype=float)
    result: dict[str, Any] = {
        "n_steps": len(part),
        "n_positive": len(x),
        "n_traces": int(part["trace_id"].nunique()),
        "n_tasks": int(part["prompt_id"].nunique()),
        "decision": "inconclusive",
        "reason": "development pilot; no confirmatory inference",
        "bootstrap_unit": "task",
        "ci": None,
        "hill": None,
        "moment": None,
        "gpd": None,
    }
    if len(x) < 50:
        result["fit_status"] = "insufficient_positive_steps"
        return result
    selection = select_k(
        x,
        "double_bootstrap",
        k_min=20,
        resamples=config["statistics"]["inner_bootstrap"],
        seed=config["seed"],
    )
    k = selection.k
    result.update(k=k, k_selection=selection.as_dict())
    result["tail_tasks"] = int(
        positive.loc[positive["z"] > np.sort(x)[::-1][k], "prompt_id"].nunique()
    )
    estimators = {
        "hill": hill,
        "moment": moment,
        "gpd": lambda y, kk: gpd_from_order_statistics(y, kk).shape_estimate,
    }
    errors = {}
    for name, fn in estimators.items():
        try:
            if name == "gpd":
                fit = gpd_from_order_statistics(x, k)
                result["gpd_fit"] = fit.as_dict()
                if not fit.converged:
                    raise ValueError(fit.message)
                result[name] = fit.shape_estimate
            else:
                result[name] = float(fn(x, k))
        except (ValueError, FloatingPointError) as exc:
            errors[name] = str(exc)
    result["xi_by_estimator"] = {
        name: max(result[name], 0)
        if result[name] is not None and np.isfinite(result[name])
        else None
        for name in estimators
    }
    result["fit_errors"] = errors
    result["fit_status"] = "partial_fit" if errors else "point_estimates"
    try:
        result["secondary_ks"] = select_k(x, "ks", k_min=20, k_max_frac=0.5).as_dict()
    except ValueError as exc:
        result["secondary_ks"] = {"error": str(exc)}
    grid = np.unique(np.geomspace(20, len(x) // 2, min(40, len(x) // 2 - 19)).astype(int))
    result["stability"] = {
        "k": grid.tolist(),
        "hill": [hill(x, int(kk)) for kk in grid],
        "moment": [moment(x, int(kk)) for kk in grid],
        "bands": None,
        "bands_reason": "fewer than 20 independent pilot tasks",
    }
    return finite_json(result)


def localization(part: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    traces = []
    for trace_id, group in part[part["outcome"] == "refuted"].groupby("trace_id", sort=True):
        group = group.sort_values("t")
        traces.append(
            {
                "trace_id": trace_id,
                "prompt_id": group["prompt_id"].iloc[0],
                "z": group["z"].to_numpy(),
                "surprisal": group["surprisal"].to_numpy(),
                "t_star": int(group["t_star"].iloc[0]),
                "L": len(group),
            }
        )
    result: dict[str, Any] = {
        "n_traces": len(traces),
        "n_tasks": len({r["prompt_id"] for r in traces}),
        "decision": "inconclusive",
        "reason": "development pilot; too few independent tasks",
        "paired_ci": None,
    }
    if not traces:
        return result
    paired = [r for r in traces if np.isfinite(r["surprisal"]).all()]
    result.update(
        jump=localization_rates(traces),
        surprisal=localization_rates(paired, "surprisal"),
        chance=float(np.mean([1 / r["L"] for r in traces])),
        by_length=_by_length(traces),
        permutation=_permutation_null(traces, config["statistics"]["permutations"], config["seed"]),
        roc=_roc(traces),
        roc_surprisal=_roc(paired, "surprisal"),
    )
    result["paired_difference"] = (
        float(
            np.mean(
                [
                    int(_rank_of(r["z"], r["t_star"]) == 1)
                    - int(_rank_of(r["surprisal"], r["t_star"]) == 1)
                    for r in paired
                ]
            )
        )
        if paired
        else None
    )
    result["n_paired"] = len(paired)
    result["displacements"] = [int(np.argmax(r["z"])) - r["t_star"] for r in traces]
    result["L_gt_1"] = localization_rates([r for r in traces if r["L"] > 1])
    result["L_gt_3"] = localization_rates([r for r in traces if r["L"] > 3])
    prefixes = [
        {
            **r,
            "z": r["z"][: r["t_star"] + 1],
            "surprisal": r["surprisal"][: r["t_star"] + 1],
            "L": r["t_star"] + 1,
        }
        for r in traces
    ]
    result["prefix_through_failure"] = {
        "jump": localization_rates(prefixes),
        "surprisal": localization_rates(prefixes, "surprisal"),
    }
    result["permutation"]["interpretation"] = "descriptive; assumes position exchangeability"
    return finite_json(result)


def overshoot(calibration: pd.DataFrame, evaluation: pd.DataFrame, q: float) -> dict[str, Any]:
    calibration = calibration[calibration["outcome"] == "verified"]
    result: dict[str, Any] = {
        "q": q,
        "decision": "inconclusive",
        "gpd": None,
        "ci": None,
        "reason": "development pilot; independent-task and exceedance requirements not met",
        "calibration_steps": len(calibration),
        "calibration_tasks": int(calibration["prompt_id"].nunique()),
    }
    if calibration.empty:
        result["reason"] = "no verified calibration steps"
        return result
    tau = float(np.quantile(calibration["z"], 1 - q))
    refuted = evaluation[evaluation["outcome"] == "refuted"]
    failure = refuted[refuted["t"] == refuted["t_star"]]
    accepted = evaluation[
        (evaluation["outcome"] == "verified") | (evaluation["t"] < evaluation["t_star"])
    ]
    excess = failure["z"].to_numpy() - tau
    calibration_tail = calibration[calibration["z"] > tau]
    result.update(
        tau=tau,
        n_failures=len(failure),
        calibration_exceedances=len(calibration_tail),
        calibration_tail_tasks=int(calibration_tail["prompt_id"].nunique()),
        positive_excesses=int(np.sum(excess > 0)),
        positive_excess_tasks=int(failure.loc[excess > 0, "prompt_id"].nunique()),
        failure_coverage=float(np.mean(excess > 0)) if len(excess) else None,
        accepted_step_exceedance=float(np.mean(accepted["z"] > tau)) if len(accepted) else None,
    )
    if tau > 0:
        result["all_failure_ratios"] = (failure["z"].to_numpy() / tau).tolist()
        u = np.sort(failure.loc[excess > 0, "z"].to_numpy() / tau)[::-1]
        result["conditioned_survival"] = {
            "ratio": u.tolist(),
            "survival": (np.arange(1, len(u) + 1) / len(u)).tolist() if len(u) else [],
        }
    if np.sum(excess > 0) >= 5:
        try:
            fit = gpd_fit(excess[excess > 0], threshold=tau)
            result["gpd"] = fit.as_dict()
            result["fit_status"] = "point_estimate" if fit.converged else "failed_fit"
        except (ValueError, FloatingPointError) as exc:
            result["fit_error"] = str(exc)
    return finite_json(result)


def analyze(root: Path, phase: str, source: Path) -> None:
    if phase != "pilot":
        raise ValueError("pilot analysis cannot be used for main confirmatory decisions")
    config = configuration(root, phase)
    directory = root / phase / "analysis"
    if completed(directory):
        return
    upstream = root / phase / "measurement"
    if not completed(upstream):
        raise ValueError("measurement must complete before analysis")
    samples, _ = generation_inputs(root, phase)
    labels = rows(root / phase / "verification/labels.jsonl")
    extracted = rows(root / phase / "extraction/trajectories.jsonl")
    table = pd.read_parquet(upstream / "deviations.parquet")
    if len(samples) != len(labels) or len(labels) != len(extracted):
        raise ValueError("attempts lost between stages")
    payload: dict[str, Any] = {
        "phase": phase,
        "scientific_decision": "inconclusive",
        "planned_attempts": len(samples),
        "generation_attempts": len(samples),
        "labelled_attempts": len(labels),
        "extraction_accounted_attempts": len(extracted),
        "extracted_attempts": sum(r["extraction_status"] == "extracted" for r in extracted),
        "measured_traces": int(table["trace_id"].nunique()),
        "measurement_status": "available" if not table.empty else "no_usable_traces",
        "categories": dict(Counter(r["category"] for r in labels)),
        "extraction_categories": dict(Counter(r["extraction_status"] for r in extracted)),
        "generation_tokens": sum(len(r["completion_token_ids"]) for r in samples),
        "unexplained_disagreements": sum(r["unexplained_disagreement"] for r in labels),
        "cells": [],
        "scope": "real model/Lean development pilot; full E1 main gates remain mandatory",
    }
    for temperature in config["temperatures"]:
        for layer in config["layers"]:
            for statistic in ("raw", "whitened", "innovation"):
                cell = table[
                    (table["temperature"] == temperature)
                    & (table["layer"] == layer)
                    & (table["statistic"] == statistic)
                ]
                evaluation = cell[(cell["role"] == "evaluation") & cell["primary_eligible"]]
                calibration = cell[cell["role"] == "calibration"]
                refuted = evaluation[evaluation["outcome"] == "refuted"]
                subsets = {
                    "verified": evaluation[evaluation["outcome"] == "verified"],
                    "refuted_all": refuted,
                    "pre": refuted[refuted["t"] < refuted["t_star"]],
                    "at": refuted[refuted["t"] == refuted["t_star"]],
                    "post": refuted[refuted["t"] > refuted["t_star"]],
                    "at_post": refuted[refuted["t"] >= refuted["t_star"]],
                }
                p1 = {name: tail(part, config) for name, part in subsets.items()}
                payload["cells"].append(
                    {
                        "temperature": temperature,
                        "layer": layer,
                        "statistic": statistic,
                        "available": not cell.empty,
                        "P1": p1,
                        "P2": localization(evaluation, config),
                        "P3": [overshoot(calibration, evaluation, q) for q in (0.01, 0.02, 0.005)],
                        "P1_exclude_first": {
                            name: tail(part[part["t"] > 0], config)
                            for name, part in subsets.items()
                        },
                        "family_counts": evaluation.groupby("task_family")["prompt_id"]
                        .nunique()
                        .to_dict(),
                    }
                )
    path = write_once(directory / "metrics.json", finite_json(payload))
    lines = [
        "# E1: первый эксперимент на настоящей prover-модели",
        "",
        "Статус научных выводов: **inconclusive**. Это development pilot; независимых задач "
        "недостаточно для подтверждающих выводов P1–P3.",
        "",
        "| Стадия | Попытки |",
        "|---|---:|",
    ]
    for name in (
        "planned_attempts",
        "generation_attempts",
        "labelled_attempts",
        "extraction_accounted_attempts",
        "extracted_attempts",
        "measured_traces",
    ):
        lines.append(f"| {name} | {payload[name]} |")
    if payload["measurement_status"] == "no_usable_traces":
        lines += ["", "**Нет пригодных трасс: активации и статистические результаты отсутствуют.**"]
    lines += ["", "| Категория Lean | Попытки |", "|---|---:|"]
    lines += [f"| {name} | {count} |" for name, count in sorted(payload["categories"].items())]
    lines += [
        "",
        "Исходные токены и причины исключений сохранены; ответы Lean и состояния доступны для обработанных трасс.",
        "Whitening обучается только на verified calibration; температуры не смешиваются.",
        "Отрицательные moment/GPD сохраняются. CI не подменяются bootstrap по зависимым попыткам.",
        "",
        "Полные измерения всех ячеек: [metrics.json](metrics.json).",
        "Протокол основного E1, симуляционная калибровка и его дополнительные проверки "
        "остаются отдельными обязательными этапами.",
    ]
    report = directory / "REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    finish(
        directory,
        stage="pilot-analysis",
        context={"source": digest(source), "config": digest(root / phase / "protocol.json")},
        inputs=[source, root / phase / "protocol.json", upstream / "manifest.json"],
        outputs=[path, report],
        metrics={"scientific_decision": "inconclusive", "attempts": len(samples)},
    )
