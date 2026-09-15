"""Separate transform/threshold calibration and task-refitted transform stress tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import linalg

from ..e1.analysis import finite_json, overshoot
from ..e1.artifacts import Journal, digest, finish, identity, read_json, verify_manifest, write_once
from ..e1.main_analysis import estimate
from ..e1.stages import rows


def fit_whitening(states: list[np.ndarray], shrinkage: float) -> dict[str, Any]:
    if not states or not 0 < shrinkage <= 1:
        raise ValueError("states and positive shrinkage required")
    x = np.concatenate([np.diff(s.astype(np.float64), axis=0) for s in states])
    if len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("insufficient finite increments")
    mean = x.mean(axis=0)
    _, singular, vectors = linalg.svd(
        (x - mean) / np.sqrt(len(x) - 1), full_matrices=False, check_finite=False
    )
    average = float(np.sum(singular**2) / x.shape[1])
    if average <= 0:
        raise ValueError("constant calibration")
    return {
        "mean": mean,
        "vectors": vectors,
        "eigenvalues": np.maximum(
            (1 - shrinkage) * singular**2 + shrinkage * average, 1e-8 * average
        ),
        "base": max(shrinkage * average, 1e-8 * average),
        "n": len(x),
        "d": x.shape[1],
    }


def norms(states: np.ndarray, fit: dict[str, Any]) -> np.ndarray:
    x = np.diff(states.astype(np.float64), axis=0) - fit["mean"]
    projected = x @ fit["vectors"].T
    orthogonal = x - projected @ fit["vectors"]
    return np.sqrt(
        np.sum(projected**2 / fit["eigenvalues"], axis=1)
        + np.sum(orthogonal**2, axis=1) / fit["base"]
    )


def replace_scores(
    table: pd.DataFrame, states: dict[str, np.ndarray], fit: dict[str, Any]
) -> pd.DataFrame:
    pieces = []
    for trace_id, group in table.groupby("trace_id", sort=True):
        part = group.sort_values("t").copy()
        z = norms(states[str(trace_id)], fit)
        if len(z) != len(part):
            raise ValueError("state/step mismatch")
        part["z"] = z
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True) if pieces else table.copy()


def paired_gain(evaluation: pd.DataFrame) -> float | None:
    scores = []
    for _, part in evaluation[evaluation["outcome"] == "refuted"].groupby("trace_id"):
        part = part.sort_values("t")
        if not np.isfinite(part[["z", "surprisal"]].to_numpy()).all():
            continue
        failure = int(part["t_star"].iloc[0])
        scores.append(
            int(np.argmax(part["z"]) == failure) - int(np.argmax(part["surprisal"]) == failure)
        )
    return float(np.mean(scores)) if scores else None


def run(
    folder: Path, model_root: Path, phase: str, source: Path, shard: int = -1, per_shard: int = 5
) -> None:
    extraction = model_root / phase / "extraction/manifest.json"
    measurement = model_root / phase / "measurement/manifest.json"
    verify_manifest(extraction)
    verify_manifest(measurement)
    config = read_json(model_root / phase / "protocol.json")
    table = pd.read_parquet(measurement.parent / "deviations.parquet")
    table = table[
        (table["temperature"] == config["primary_temperature"])
        & (table["layer"] == config["primary_layer"])
        & (table["statistic"] == "raw")
        & table["primary_eligible"]
    ]
    record = {
        r["trace_id"]: r
        for r in rows(extraction.parent / "trajectories.jsonl")
        if r["extraction_status"] == "extracted"
    }
    states = {}
    for rid in table["trace_id"].unique():
        r = record[rid]
        if digest(r["states_path"]) != r["states_sha256"]:
            raise ValueError("states changed")
        with np.load(r["states_path"], allow_pickle=False) as bundle:
            states[str(rid)] = bundle[f"states_{config['primary_layer']}"]
    verified = table[(table["role"] == "calibration") & (table["outcome"] == "verified")]
    task_ids = sorted(verified["prompt_id"].unique(), key=lambda x: identity([20260911, str(x)]))
    by_task = {
        str(task): list(part["trace_id"].unique()) for task, part in verified.groupby("prompt_id")
    }
    context = {
        "source": digest(source),
        "measurement": digest(measurement),
        "shard": shard,
        "per_shard": per_shard,
    }
    if len(task_ids) < 2:
        path = write_once(
            folder / "metrics.json",
            {"status": "insufficient_verified_calibration", "tasks": len(task_ids)},
        )
        finish(
            folder,
            stage="whitening-readiness",
            context=context,
            inputs=[source, measurement, extraction],
            outputs=[path],
            metrics={"available": False},
        )
        return
    specifications = []
    if shard < 0:
        for shrinkage in (0.05, 0.1, 0.2):
            specifications.append(
                (f"all-calibration-{shrinkage}", list(task_ids), list(task_ids), shrinkage)
            )
        specifications.append(
            ("disjoint-transform-and-threshold", list(task_ids[::2]), list(task_ids[1::2]), 0.1)
        )
    else:
        for index in range(shard * per_shard, (shard + 1) * per_shard):
            rng = np.random.default_rng(20260911 + index)
            specifications.append(
                (
                    f"refit-{index}",
                    rng.choice(task_ids, len(task_ids), replace=True).tolist(),
                    list(task_ids),
                    0.1,
                )
            )
    path = folder / "results.jsonl"
    with Journal(path, context) as journal:
        for name, fit_tasks, tau_tasks, shrinkage in specifications:
            spec = {
                "name": name,
                "fit_tasks": fit_tasks,
                "tau_tasks": tau_tasks,
                "shrinkage": shrinkage,
            }
            if journal.existing(name, identity(spec)) is not None:
                continue
            fitted = fit_whitening([states[r] for t in fit_tasks for r in by_task[t]], shrinkage)
            transformed = replace_scores(table, states, fitted)
            cal = transformed[
                (transformed["role"] == "calibration") & transformed["prompt_id"].isin(tau_tasks)
            ]
            evaluation = transformed[transformed["role"] == "evaluation"]
            p1 = {}
            for outcome in ("verified", "refuted"):
                x = evaluation.loc[evaluation["outcome"] == outcome, "z"].to_numpy()
                p1[outcome] = estimate(x, config, 20260911).tolist()
            journal.append(
                finite_json(
                    {
                        "trace_id": name,
                        "specification": spec,
                        "fit_tasks": len(set(fit_tasks)),
                        "threshold_tasks": len(set(tau_tasks)),
                        "n_over_d": fitted["n"] / fitted["d"],
                        "P1_estimator_order": ["hill", "moment", "gpd"],
                        "P1": p1,
                        "P2_paired_gain": paired_gain(evaluation),
                        "P3": overshoot(cal, evaluation, 0.01),
                        "interpretation": "transform sensitivity conditional on fixed evaluation; no confidence interval",
                        "decision": "inconclusive",
                    }
                ),
                identity(spec),
            )
            print(name, "complete", flush=True)
    finish(
        folder,
        stage="whitening-readiness",
        context=context,
        inputs=[source, measurement, extraction],
        outputs=[path, path.with_suffix(".identity.json")],
        metrics={"variants": len(specifications), "phase": phase, "shard": shard},
    )
