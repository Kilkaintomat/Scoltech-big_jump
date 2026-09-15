"""Supplementary finite-sample estimands, independent of tail-model assumptions.

No change to the frozen P1-P5 primary analyses. Task means retain all eligible attempts
without treating their steps or repeated attempts as independent observations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest


def bounded_mean(
    values: list[float], lower: float, upper: float, alpha: float = 0.05
) -> dict[str, Any]:
    """Hoeffding interval for independent bounded task values, including small n.

    This covers the average task expectation under independence (not necessarily iid).
    It is deliberately conservative, conditional on an independently fitted transform.
    A fixed benchmark alone does not justify generalization to all mathematical tasks.
    """
    if not lower < upper or not 0 < alpha < 1:
        raise ValueError("invalid bounds or alpha")
    x = np.asarray(values, dtype=float)
    if not np.isfinite(x).all() or np.any((x < lower) | (x > upper)):
        raise ValueError("nonfinite or out-of-bounds task score")
    if not len(x):
        return {"tasks": 0, "mean": None, "interval": None, "alpha": alpha}
    mean = float(x.mean())
    radius = float((upper - lower) * np.sqrt(np.log(2 / alpha) / (2 * len(x))))
    return {
        "tasks": len(x),
        "mean": mean,
        "interval": [max(lower, mean - radius), min(upper, mean + radius)],
        "alpha": alpha,
        "method": "Hoeffding; independent bounded task averages",
        "radius_before_clipping": radius,
    }


def sign_screen(values: list[float], alpha: float = 0.05) -> dict[str, Any]:
    """Exact sign test for win probability among non-tied task effects, not mean gain.

    Requires independent, identically distributed task signs conditional on non-ties.
    Does not assume symmetric effect magnitudes or permute algorithm identities.
    """
    x = np.asarray(values, dtype=float)
    if not 0 < alpha < 1 or not np.isfinite(x).all():
        raise ValueError("invalid alpha or task differences")
    positive, negative = int((x > 0).sum()), int((x < 0).sum())
    n = positive + negative
    result: dict[str, Any] = {
        "wins": positive,
        "losses": negative,
        "ties": int((x == 0).sum()),
        "non_tied_tasks": n,
        "p_two_sided": None,
        "win_probability_interval": None,
        "estimand": "probability of positive task effect conditional on nonzero effect",
        "scope": "secondary exact sign screen; not a test of average gain",
    }
    if n:
        test = binomtest(positive, n, p=0.5, alternative="two-sided")
        ci = test.proportion_ci(confidence_level=1 - alpha, method="exact")
        result.update(
            p_two_sided=float(test.pvalue), win_probability_interval=[float(ci.low), float(ci.high)]
        )
    return result


def localization_effects(frame: pd.DataFrame, drop_first: bool = False) -> dict[str, Any]:
    """Paired top-1 and rank scores on identical traces; task-weighted target.

    Ties select the earliest step, matching the positional controls. Dropping the first
    step excludes failures at that step, explicitly changing the eligible population.
    """
    tasks: dict[str, list[dict[str, float]]] = defaultdict(list)
    records = []
    omitted = {"failure_at_first": 0, "missing_target": 0, "nonfinite_pair": 0}
    for rid, original in frame[frame["outcome"] == "refuted"].groupby("trace_id", sort=True):
        original = original.sort_values("t")
        if original["prompt_id"].nunique() != 1 or original["t"].duplicated().any():
            raise ValueError("trace contains mixed tasks or duplicate step positions")
        fail = int(original["t_star"].iloc[0])
        if drop_first and fail == 0:
            omitted["failure_at_first"] += 1
            continue
        part = original[original["t"] > 0] if drop_first else original
        positions = part["t"].to_numpy()
        if fail not in positions:
            omitted["missing_target"] += 1
            continue
        if not np.isfinite(part[["z", "surprisal"]].to_numpy(dtype=float)).all():
            omitted["nonfinite_pair"] += 1
            continue
        hits = {}
        ranks = {}
        for key, column in (("jump", "z"), ("surprisal", "surprisal")):
            order = np.argsort(-part[column].to_numpy(dtype=float), kind="stable")
            rank = int(np.flatnonzero(positions[order] == fail)[0])
            hits[key] = float(rank == 0)
            ranks[key] = 1.0 if len(part) == 1 else 1 - rank / (len(part) - 1)
        score = {
            **hits,
            "gain": hits["jump"] - hits["surprisal"],
            "rank_gain": ranks["jump"] - ranks["surprisal"],
            "first_position": float(fail == positions[0]),
            "chance_reference": 1 / len(part),
        }
        task = str(part["prompt_id"].iloc[0])
        tasks[task].append(score)
        records.append({"trace_id": str(rid), "task": task, "length": len(part), **score})
    means = {
        task: {name: float(np.mean([row[name] for row in group])) for name in group[0]}
        for task, group in sorted(tasks.items())
    }
    summaries = {
        name: bounded_mean(
            [group[name] for group in means.values()],
            -1 if name in {"gain", "rank_gain"} else 0,
            1,
        )
        for name in ("jump", "surprisal", "gain", "rank_gain", "first_position", "chance_reference")
    }
    gain = [group["gain"] for group in means.values()]
    return {
        "estimand": "equal-weight mean over tasks with at least one paired eligible refuted trace",
        "conditional_on": "fitted transform and trace eligibility; fixed benchmark scope",
        "drop_first": drop_first,
        "tasks": len(tasks),
        "traces": len(records),
        "omitted": omitted,
        "task_scores": means,
        "records": records,
        "estimates": summaries,
        "sign_screen": sign_screen(gain),
        "family_gain_interval": bounded_mean(gain, -1, 1, alpha=0.05 / 3),
        "family_scope": "three models, primary whitened cell only; secondary amendment",
        "decision": "descriptive supplementary analysis; original primary analysis unchanged",
    }


def threshold_rates(frame: pd.DataFrame, tau: float) -> dict[str, Any]:
    """Task-weighted finite-threshold rates. No extrapolation or GPD fit.

    Threshold and transform must be fitted independently of evaluation tasks.
    Reusing transform-fitting tasks for threshold estimation still impairs calibration.
    """
    if not np.isfinite(tau):
        raise ValueError("threshold must be finite")
    refuted = frame["outcome"] == "refuted"
    accepted = (frame["outcome"] == "verified") | (refuted & (frame["t"] < frame["t_star"]))
    failure = refuted & (frame["t"] == frame["t_star"])
    masks = {
        "accepted": accepted,
        "first_failure": failure,
        "accepted_first": accepted & (frame["t"] == 0),
        "accepted_later": accepted & (frame["t"] > 0),
    }
    result: dict[str, Any] = {"tau": tau, "conditional_on_fixed_threshold": True, "groups": {}}
    for name, mask in masks.items():
        part = frame[mask]
        if not np.isfinite(part["z"].to_numpy(dtype=float)).all():
            raise ValueError("nonfinite evaluation score")
        task_rates = {
            str(task): float((group["z"] > tau).mean())
            for task, group in part.groupby("prompt_id", sort=True)
        }
        result["groups"][name] = {
            "steps": len(part),
            "traces": int(part["trace_id"].nunique()),
            "exceedances": int((part["z"] > tau).sum()),
            "task_rates": task_rates,
            "task_weighted": bounded_mean(list(task_rates.values()), 0, 1),
        }
    a = result["groups"]["accepted"]["task_rates"]
    f = result["groups"]["first_failure"]["task_rates"]
    shared = sorted(set(a) & set(f))
    result["paired_discrimination"] = {
        "task_ids": shared,
        "estimate": bounded_mean([f[key] - a[key] for key in shared], -1, 1),
        "estimand": "failure minus accepted exceedance rate on tasks with both kinds of steps",
    }
    return result
