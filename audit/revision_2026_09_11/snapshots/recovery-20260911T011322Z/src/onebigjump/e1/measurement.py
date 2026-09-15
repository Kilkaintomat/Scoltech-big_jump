"""Frozen, problem-disjoint regularized transforms and deviation tables for E1."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import linalg

from ..experiments.dataset import COLUMNS, validate_table
from .artifacts import digest, finish, write_once
from .stages import completed, configuration, rows


def fit_transform(
    states: list[np.ndarray], shrinkage: float, ridge: float
) -> dict[str, np.ndarray]:
    if not states or not 0 < shrinkage <= 1 or ridge <= 0:
        raise ValueError("positive shrinkage, ridge and calibration states required")
    previous = np.concatenate([x[:-1] for x in states]).astype(np.float64)
    following = np.concatenate([x[1:] for x in states]).astype(np.float64)
    increments = following - previous
    n, d = increments.shape
    if n < 2 or not np.isfinite(increments).all():
        raise ValueError("insufficient or nonfinite calibration increments")
    mean = increments.mean(axis=0)
    centred = increments - mean
    _, singular, vectors = linalg.svd(
        centred / np.sqrt(n - 1), full_matrices=False, check_finite=False
    )
    average = float(np.sum(singular**2) / d)
    if average <= 0:
        raise ValueError("constant calibration increments")
    base = max(shrinkage * average, 1e-8 * average)
    eigenvalues = np.maximum((1 - shrinkage) * singular**2 + shrinkage * average, 1e-8 * average)
    x_mean, y_mean = previous.mean(axis=0), following.mean(axis=0)
    xc, yc = previous - x_mean, following - y_mean
    if n < d:
        ridge_basis = xc
        ridge_coef = linalg.solve(xc @ xc.T + ridge * np.eye(n), yc, assume_a="pos")
    else:
        ridge_basis = np.eye(d)
        ridge_coef = linalg.solve(xc.T @ xc + ridge * np.eye(d), xc.T @ yc, assume_a="pos")
    return {
        "mean": mean,
        "vectors": vectors,
        "eigenvalues": eigenvalues,
        "base": np.asarray(base),
        "average_eigenvalue": np.asarray(average),
        "x_mean": x_mean,
        "y_mean": y_mean,
        "ridge_basis": ridge_basis,
        "ridge_coef": ridge_coef,
        "n_increments": np.asarray(n),
        "shrinkage": np.asarray(shrinkage),
        "ridge": np.asarray(ridge),
    }


def transformed_norms(
    states: np.ndarray, fit: dict[str, np.ndarray] | None
) -> dict[str, np.ndarray]:
    states = states.astype(np.float64)
    increment = np.diff(states, axis=0)
    out = {"raw": np.linalg.norm(increment, axis=1)}
    if fit is not None:
        centred = increment - fit["mean"]
        projected = centred @ fit["vectors"].T
        # Preserve the orthogonal component explicitly to avoid cancellation of large terms.
        orthogonal = centred - projected @ fit["vectors"]
        square = np.sum(projected**2 / fit["eigenvalues"], axis=1)
        square += np.sum(orthogonal**2, axis=1) / float(fit["base"])
        out["whitened"] = np.sqrt(square)
        predicted = (states[:-1] - fit["x_mean"]) @ fit["ridge_basis"].T @ fit["ridge_coef"] + fit[
            "y_mean"
        ]
        out["innovation"] = np.linalg.norm(states[1:] - predicted, axis=1)
    return out


def measure(root: Path, phase: str, source: Path) -> None:
    config = configuration(root, phase)
    directory = root / phase / "measurement"
    if completed(directory):
        return
    upstream = root / phase / "extraction"
    if not completed(upstream):
        raise ValueError("extraction must complete before measurement")
    records = rows(upstream / "trajectories.jsonl")
    labels = {r["trace_id"]: r for r in rows(root / phase / "verification/labels.jsonl")}
    good = [r for r in records if r["extraction_status"] == "extracted"]
    loaded: dict[str, dict[str, np.ndarray]] = {}
    for row in good:
        if digest(row["states_path"]) != row["states_sha256"]:
            raise ValueError("saved state digest mismatch")
        with np.load(row["states_path"], allow_pickle=False) as bundle:
            loaded[row["trace_id"]] = {key: bundle[key] for key in bundle.files}
    calibration_tasks = {r["problem_id"] for r in records if r["role"] == "calibration"}
    evaluation_tasks = {r["problem_id"] for r in records if r["role"] == "evaluation"}
    if calibration_tasks & evaluation_tasks:
        raise ValueError("calibration/evaluation task leakage")
    directory.mkdir(parents=True, exist_ok=True)
    transforms = {}
    diagnostics = []
    output_files: list[Path] = []
    settings = config["whitening"]
    table_rows = []
    for temperature in config["temperatures"]:
        for layer in config["layers"]:
            subset = [r for r in good if r["temperature"] == temperature]
            calibration = [
                r for r in subset if r["role"] == "calibration" and r["category"] == "verified"
            ]
            states = [loaded[r["trace_id"]][f"states_{layer}"] for r in calibration]
            n = sum(len(s) - 1 for s in states)
            tasks = len({r["problem_id"] for r in calibration})
            enough = (
                tasks >= settings[f"min_{phase}_tasks"] and n >= settings[f"min_{phase}_increments"]
            )
            fit = (
                fit_transform(states, settings["shrinkage"], settings["ridge"]) if enough else None
            )
            transforms[temperature, layer] = fit
            diagnostic: dict[str, Any] = {
                "temperature": temperature,
                "layer": layer,
                "after_block_1based": layer + 1,
                "calibration_tasks": tasks,
                "calibration_increments": n,
                "calibration_ids": [r["trace_id"] for r in calibration],
                "available": enough,
                "reason": None if enough else "insufficient_verified_calibration",
            }
            if fit is not None:
                path = directory / f"calibration-T{temperature}-layer{layer}.npz"
                temporary = path.with_suffix(".tmp")
                with temporary.open("wb") as stream:
                    np.savez_compressed(stream, allow_pickle=False, **fit)
                os.replace(temporary, path)
                output_files.append(path)
                diagnostic.update(
                    n_over_d=n / len(fit["mean"]),
                    condition_number=float(fit["eigenvalues"].max() / fit["base"]),
                    shrinkage=float(fit["shrinkage"]),
                )
            diagnostics.append(diagnostic)
            for row in subset:
                label = labels[row["trace_id"]]
                if label["category"] != "verified" and label["t_star"] is None:
                    continue  # No invented failing step for a whole-proof-only exclusion.
                states_one = loaded[row["trace_id"]][f"states_{layer}"]
                values = transformed_norms(states_one, fit)
                length = len(label["steps"])
                if len(states_one) != length + 1:
                    raise ValueError("state/step count mismatch")
                for statistic, deviations in values.items():
                    for t, value in enumerate(deviations):
                        step = label["steps"][t]
                        table_rows.append(
                            {
                                "trace_id": row["trace_id"],
                                "prompt_id": row["problem_id"],
                                "model": config["model_id"],
                                "layer": layer,
                                "statistic": statistic,
                                "t": t,
                                "L": length,
                                "z": float(value),
                                "valid": step["valid"],
                                "t_star": label["t_star"],
                                "outcome": "verified"
                                if label["category"] == "verified"
                                else "refuted",
                                "surprisal": float(loaded[row["trace_id"]]["surprisal"][t]),
                                "status": step["status"],
                                "temperature": temperature,
                                "task_family": row["task_family"],
                                "role": row["role"],
                                "category": row["category"],
                                "primary_eligible": row["category"]
                                in {"verified", "localized_tactic_failure"},
                            }
                        )
    table = pd.DataFrame(
        table_rows,
        columns=[
            *COLUMNS,
            "status",
            "temperature",
            "task_family",
            "role",
            "category",
            "primary_eligible",
        ],
    )
    if not table.empty:
        validate_table(table)
    path = directory / "deviations.parquet"
    table.to_parquet(path, index=False)
    output_files.extend([path, write_once(directory / "calibration.json", diagnostics)])
    finish(
        directory,
        stage="measurement",
        context={"source": digest(source), "config": digest(root / phase / "protocol.json")},
        inputs=[source, root / phase / "protocol.json", upstream / "manifest.json"],
        outputs=output_files,
        metrics={
            "table_rows": len(table),
            "input_attempts": len(records),
            "table_traces": int(table["trace_id"].nunique()),
        },
    )
