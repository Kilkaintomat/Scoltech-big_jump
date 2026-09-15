"""Prespecified secondary controls; never select or overwrite the primary E1 cell."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..e1.analysis import finite_json
from ..e1.artifacts import digest, finish, identity, read_json, verify_manifest, write_once
from ..e1.main_analysis import estimate
from ..e1.stages import rows
from . import controls, whitening

PLAN: dict[str, Any] = {
    "version": "whitening-position-20260912-v1",
    "seed": 20260912,
    "split_seed": 20260911,
    "shrinkages": [0.05, 0.1, 0.2],
    "q": 0.01,
    "interpretation": "prespecified secondary sensitivity; primary cell unchanged",
}


def variants() -> list[dict[str, Any]]:
    return [
        {"drop_first": drop, "disjoint": separate, "shrinkage": shrinkage}
        for drop in (False, True)
        for separate in (False, True)
        for shrinkage in PLAN["shrinkages"]
    ]


def quantiles(values: np.ndarray) -> dict[str, Any]:
    return {
        "n": len(values),
        "probabilities": [0, 0.5, 0.9, 0.99, 1],
        "values": np.quantile(values, [0, 0.5, 0.9, 0.99, 1]).tolist() if len(values) else [],
    }


def threshold_audit(cal: pd.DataFrame, evaluation: pd.DataFrame) -> dict[str, Any]:
    cal = cal[cal["outcome"] == "verified"]
    tau = float(np.quantile(cal["z"], 1 - PLAN["q"])) if len(cal) else None
    accepted = (evaluation["outcome"] == "verified") | (evaluation["t"] < evaluation["t_star"])
    groups = {
        "verified_evaluation": evaluation[evaluation["outcome"] == "verified"],
        "accepted_evaluation": evaluation[accepted],
        "accepted_first": evaluation[accepted & (evaluation["t"] == 0)],
        "accepted_later": evaluation[accepted & (evaluation["t"] > 0)],
        "first_failure": evaluation[
            (evaluation["outcome"] == "refuted") & (evaluation["t"] == evaluation["t_star"])
        ],
    }

    def sample(part: pd.DataFrame) -> dict[str, Any]:
        return {
            "steps": len(part),
            "tasks": int(part["prompt_id"].nunique()),
            "traces": int(part["trace_id"].nunique()),
            "exceedances": int((part["z"] > tau).sum()) if tau is not None else None,
            "exceedance_rate": float((part["z"] > tau).mean())
            if tau is not None and len(part)
            else None,
            "scores": quantiles(part["z"].to_numpy()),
        }

    return {
        "q": PLAN["q"],
        "tau": tau,
        "calibration": sample(cal),
        "evaluation": {name: sample(part) for name, part in groups.items()},
    }


def paired_views(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Keep original step indices, pair every score with surprisal on the same trace."""
    result = {}
    refuted = frame[frame["outcome"] == "refuted"]
    for name in ("all", "failure_after_first", "failure_after_first_drop_first"):
        selected = []
        records: list[dict[str, Any]] = []
        omitted = {"first_failure": 0, "nonfinite_pair": 0, "missing_target": 0}
        for rid, original in refuted.groupby("trace_id", sort=True):
            original = original.sort_values("t")
            fail = int(original["t_star"].iloc[0])
            if name != "all" and fail == 0:
                omitted["first_failure"] += 1
                continue
            part = original[original["t"] > 0] if name.endswith("drop_first") else original
            if fail not in set(part["t"]):
                omitted["missing_target"] += 1
                continue
            if not np.isfinite(part[["z", "surprisal"]].to_numpy()).all():
                omitted["nonfinite_pair"] += 1
                continue
            positions = part["t"].to_numpy()
            jump_position = int(positions[np.argmax(part["z"].to_numpy())])
            base_position = int(positions[np.argmax(part["surprisal"].to_numpy())])
            records.append(
                {
                    "trace_id": str(rid),
                    "task": str(part["prompt_id"].iloc[0]),
                    "jump": int(jump_position == fail),
                    "surprisal": int(base_position == fail),
                    "chance": 1 / len(part),
                    "jump_at_first": int(jump_position == 0),
                }
            )
            selected.append(part)
        tasks = sorted({r["task"] for r in records})
        row: dict[str, Any] = {
            "n_traces": len(records),
            "n_tasks": len(tasks),
            "omitted_traces": omitted,
            "paired_trace_ids": [r["trace_id"] for r in records],
            "paired_trace_ids_sha256": identity([r["trace_id"] for r in records]),
            "jump_top1": None,
            "surprisal_top1": None,
            "paired_gain": None,
            "chance": None,
            "paired_ci95": None,
            "decision": "inconclusive",
            "ci_scope": "secondary descriptive task bootstrap, conditional on fitted transform",
        }
        if records:
            jump = float(np.mean([r["jump"] for r in records]))
            base = float(np.mean([r["surprisal"] for r in records]))
            row.update(
                jump_top1=jump,
                surprisal_top1=base,
                paired_gain=jump - base,
                chance=float(np.mean([r["chance"] for r in records])),
                jump_at_first=float(np.mean([r["jump_at_first"] for r in records])),
            )
            if len(tasks) >= max(20, config["statistics"]["min_tasks"]):
                totals = np.array(
                    [
                        [
                            sum(r["jump"] - r["surprisal"] for r in records if r["task"] == task),
                            sum(r["task"] == task for r in records),
                        ]
                        for task in tasks
                    ]
                )
                rng = np.random.default_rng(PLAN["seed"])
                indices = rng.integers(
                    len(tasks), size=(config["statistics"]["bootstrap"], len(tasks))
                )
                draws = totals[indices].sum(axis=1)
                row["paired_ci95"] = np.quantile(draws[:, 0] / draws[:, 1], [0.025, 0.975]).tolist()
            paired = pd.concat(selected, ignore_index=True)
            row["position_null"] = controls.positional_null(
                paired, config["statistics"]["permutations"], PLAN["seed"]
            )
        result[name] = row
    return finite_json(result)


def fit_specification(
    table: pd.DataFrame,
    states: dict[str, np.ndarray],
    spec: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    verified = table[(table["role"] == "calibration") & (table["outcome"] == "verified")]
    tasks = sorted(
        verified["prompt_id"].unique(), key=lambda t: identity([PLAN["split_seed"], str(t)])
    )
    fit_tasks = tasks[::2] if spec["disjoint"] else tasks
    tau_tasks = tasks[1::2] if spec["disjoint"] else tasks
    evaluation_tasks = set(table.loc[table["role"] == "evaluation", "prompt_id"])
    if evaluation_tasks & set(tasks):
        raise ValueError("calibration and evaluation task overlap")
    if spec["disjoint"] and set(fit_tasks) & set(tau_tasks):
        raise ValueError("transform/threshold overlap")
    fit_ids = verified.loc[verified["prompt_id"].isin(fit_tasks), "trace_id"].unique()
    fit_states = [states[str(rid)][int(spec["drop_first"]) :] for rid in fit_ids]
    fit_states = [s for s in fit_states if len(s) >= 2]
    result: dict[str, Any] = {
        "specification": spec,
        "fit_task_ids": list(fit_tasks),
        "threshold_task_ids": list(tau_tasks),
        "overlap_tasks": len(set(fit_tasks) & set(tau_tasks)),
        "input_evaluation_traces": int(
            table.loc[table["role"] == "evaluation", "trace_id"].nunique()
        ),
        "input_first_failure_traces": int(
            table.loc[
                (table["role"] == "evaluation")
                & (table["outcome"] == "refuted")
                & (table["t_star"] == 0),
                "trace_id",
            ].nunique()
        ),
        "fit_trace_ids": list(fit_ids),
        "decision": "inconclusive",
        "status": "insufficient_calibration",
    }
    if not fit_states or sum(len(s) - 1 for s in fit_states) < 2 or not tau_tasks:
        return result
    fitted = whitening.fit_whitening(fit_states, spec["shrinkage"])
    pieces = []
    for rid, group in table.groupby("trace_id", sort=True):
        part = group.sort_values("t").copy()
        z = whitening.norms(states[str(rid)], fitted)
        if not np.array_equal(part["t"].to_numpy(), np.arange(len(z))):
            raise ValueError("noncontiguous original state/step indices")
        part["z"] = z
        if spec["drop_first"]:
            part = part[part["t"] > 0]
        pieces.append(part)
    transformed = pd.concat(pieces, ignore_index=True)
    cal = transformed[
        (transformed["role"] == "calibration") & transformed["prompt_id"].isin(tau_tasks)
    ]
    evaluation = transformed[transformed["role"] == "evaluation"]
    effective_fit_tasks = verified[
        verified["prompt_id"].isin(fit_tasks)
        & ((verified["t"] > 0) if spec["drop_first"] else True)
    ]["prompt_id"].nunique()
    result.update(
        status="complete",
        fit_increments=fitted["n"],
        dimension=fitted["d"],
        n_over_d=fitted["n"] / fitted["d"],
        output_evaluation_traces=int(evaluation["trace_id"].nunique()),
        empty_evaluation_traces_after_exclusion=result["input_evaluation_traces"]
        - int(evaluation["trace_id"].nunique()),
        effective_fit_tasks=int(effective_fit_tasks),
        threshold=threshold_audit(cal, evaluation),
        P2=paired_views(evaluation, config),
        estimator_order=["hill", "moment", "gpd"],
        P1={
            outcome: estimate(
                evaluation.loc[evaluation["outcome"] == outcome, "z"].to_numpy(),
                config,
                PLAN["seed"],
            ).tolist()
            for outcome in ("verified", "refuted")
        },
        interpretation="secondary sensitivity; no calibrated tail confidence interval",
    )
    return finite_json(result)


def run(folder: Path, model_root: Path, phase: str, source: Path, shard: int = -1) -> None:
    measurement = model_root / phase / "measurement/manifest.json"
    extraction = model_root / phase / "extraction/manifest.json"
    protocol = model_root / phase / "protocol.json"
    verify_manifest(measurement)
    verify_manifest(extraction)
    config = read_json(protocol)
    table = pd.read_parquet(measurement.parent / "deviations.parquet")
    table = table[
        (table["temperature"] == config["primary_temperature"])
        & (table["layer"] == config["primary_layer"])
        & table["primary_eligible"]
    ]
    context = {
        "source": digest(source),
        "measurement": digest(measurement),
        "plan": identity(PLAN),
        "shard": shard,
    }
    inputs = [source, measurement, extraction, protocol]
    metrics: dict[str, Any] = {
        "plan": PLAN,
        "phase": phase,
        "model_root": str(model_root),
        "primary_cell": {
            "temperature": config["primary_temperature"],
            "layer": config["primary_layer"],
            "statistic": config.get("primary_statistic", "whitened"),
        },
        "decision": "inconclusive",
    }
    if shard < 0:
        metrics["cells"] = {}
        for statistic, frame in table.groupby("statistic"):
            cal = frame[frame["role"] == "calibration"]
            evaluation = frame[frame["role"] == "evaluation"]
            metrics["cells"][str(statistic)] = {
                "threshold": threshold_audit(cal, evaluation),
                "P2": paired_views(evaluation, config),
            }
    else:
        spec = variants()[shard]
        table = table[table["statistic"] == "raw"]
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
            inputs.append(Path(r["states_path"]))
            with np.load(r["states_path"], allow_pickle=False) as bundle:
                states[str(rid)] = bundle[f"states_{config['primary_layer']}"]
        metrics["variant"] = fit_specification(table, states, spec, config)
    path = write_once(folder / "metrics.json", finite_json(metrics))
    finish(
        folder,
        stage="whitening-position-diagnostics",
        context=context,
        inputs=inputs,
        outputs=[path],
        metrics={"phase": phase, "shard": shard, "decision": "inconclusive"},
    )
