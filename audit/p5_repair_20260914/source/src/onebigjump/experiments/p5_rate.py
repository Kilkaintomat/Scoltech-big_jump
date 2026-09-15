"""Identified length-only rate; tail/tolerance inference is a separate operation."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from numbers import Integral
from typing import Any

import numpy as np
from scipy.optimize import brentq
from scipy.special import xlogy


def _arrays(counts: Mapping[int, tuple[int, int]]):
    if len(counts) < 3:
        raise ValueError("at least three distinct assigned lengths are required")
    for length, (successes, count) in counts.items():
        if any(
            isinstance(v, bool) or not isinstance(v, Integral) for v in (length, successes, count)
        ):
            raise ValueError("lengths and counts must be integers")
        if length <= 0 or count <= 0 or not 0 <= successes <= count:
            raise ValueError("invalid assigned length or binomial counts")
    lengths = np.array(sorted(counts), dtype=float)
    success = np.array([counts[int(v)][0] for v in lengths], dtype=float)
    total = np.array([counts[int(v)][1] for v in lengths], dtype=float)
    return lengths, success, total


def _loglik(rate: float, lengths, success, failure) -> float:
    if math.isinf(rate):
        return 0.0 if not np.any(success) else -math.inf
    if rate == 0:
        return 0.0 if not np.any(failure) else -math.inf
    log_success = -rate * lengths
    log_failure = np.log(-np.expm1(-rate * lengths))
    return float(np.sum(success * log_success + failure * log_failure))


def fit_length_rate(counts: Mapping[int, tuple[int, int]]) -> dict[str, Any]:
    """MLE of P(success|L)=exp(-c L), including both boundary cases.

    No activation data, GPD fit, theta estimate or success-rate threshold is used.
    LR is descriptive: attempts sharing a prompt are not independent observations.
    """
    lengths, success, total = _arrays(counts)
    failure = total - success
    if not np.any(failure):
        rate, status = 0.0, "all_success_boundary"
    elif not np.any(success):
        rate, status = math.inf, "all_failure_boundary"
    else:

        def score(c):
            if c == 0:
                return math.inf
            with np.errstate(over="ignore"):
                term = failure * lengths / np.expm1(c * lengths)
            return float(-np.sum(success * lengths) + np.sum(term))

        upper = 1.0
        while score(upper) > 0:
            upper *= 2
        rate = float(brentq(score, 0.0, upper, xtol=1e-14))
        status = "interior"
    loglik = _loglik(rate, lengths, success, failure)
    saturated = float(np.sum(xlogy(success, success / total) + xlogy(failure, failure / total)))
    probabilities = np.zeros_like(lengths) if math.isinf(rate) else np.exp(-rate * lengths)
    return {
        "status": status,
        "rate_per_step": None if math.isinf(rate) else rate,
        "rate_is_infinite": math.isinf(rate),
        "loglik": loglik,
        "loglik_saturated": saturated,
        "lr_statistic": max(0.0, 2 * (saturated - loglik)),
        "identified_parameters": 1,
        "p_value": None,
        "p_value_status": "not_reported_without_dependence_calibration",
        "theta": None,
        "tau": None,
        "tolerance_status": "not_identified_from_length_counts",
        "predictions": [
            {
                "length": int(length),
                "verified": int(s),
                "attempts": int(n),
                "predicted_success": float(p),
            }
            for length, s, n, p in zip(lengths, success, total, probabilities, strict=True)
        ],
    }


def score_heldout(fit: dict[str, Any], counts: Mapping[int, tuple[int, int]]) -> dict[str, Any]:
    lengths, success, total = _arrays(counts)
    rate = math.inf if fit["rate_is_infinite"] else float(fit["rate_per_step"])
    probabilities = np.zeros_like(lengths) if math.isinf(rate) else np.exp(-rate * lengths)
    ll = _loglik(rate, lengths, success, total - success)
    brier = float(
        np.sum(success * (1 - probabilities) ** 2 + (total - success) * probabilities**2)
        / np.sum(total)
    )
    return {
        "loglik": ll if math.isfinite(ll) else None,
        "loglik_status": "finite"
        if math.isfinite(ll)
        else "negative_infinity_zero_probability_event",
        "brier": brier,
        "attempts": int(np.sum(total)),
        "predictions": [
            {"length": int(length), "predicted_success": float(p)}
            for length, p in zip(lengths, probabilities, strict=True)
        ],
        "scope": "prediction from calibration tasks; evaluation outcomes were not used to fit the rate",
    }


def diagnose_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len({r["trace_id"] for r in records}) != len(records):
        raise ValueError("duplicate attempt identifiers")
    roles: dict[str, set[str]] = {}
    for r in records:
        role = r["role"].removeprefix("pilot_")
        if role not in {"calibration", "evaluation"}:
            raise ValueError("unrecognised task role")
        roles.setdefault(role, set()).add(r["problem_id"])
    if roles.get("calibration", set()) & roles.get("evaluation", set()):
        raise ValueError("calibration and evaluation tasks overlap")
    results = []
    for temperature in sorted({r["temperature"] for r in records}):
        subsets: dict[str, dict[str, Any]] = {}
        for role in ("calibration", "evaluation"):
            chosen = [
                r
                for r in records
                if r["temperature"] == temperature and r["role"].removeprefix("pilot_") == role
            ]
            counts = {
                length: (
                    sum(bool(r["verified"]) for r in chosen if r["length"] == length),
                    sum(r["length"] == length for r in chosen),
                )
                for length in sorted({r["length"] for r in chosen})
            }
            fit = fit_length_rate(counts) if len(counts) >= 3 else None
            subsets[role] = {
                "counts": counts,
                "rate_fit": fit,
                "attempts": len(chosen),
                "tasks": len({r["problem_id"] for r in chosen}),
                "format_fraction": sum(bool(r["format_eligible"]) for r in chosen) / len(chosen)
                if chosen
                else None,
                "categories": dict(Counter(r["category"] for r in chosen)),
            }
        train = subsets["calibration"]["rate_fit"]
        heldout = (
            score_heldout(train, subsets["evaluation"]["counts"])
            if train and len(subsets["evaluation"]["counts"]) >= 3
            else None
        )
        results.append({"temperature": temperature, **subsets, "heldout_prediction": heldout})
    return {
        "attempts": len(records),
        "categories": dict(Counter(r["category"] for r in records)),
        "temperatures": results,
        "decision": "inconclusive",
        "limitations": [
            "Rate fitting is descriptive and does not establish a heavy-tail mechanism.",
            "All assigned attempts, including malformed and truncated outputs, remain in the denominator.",
            "Format failures confound interpretation as a law of valid inference opportunities.",
            "No chi-square p-value, confidence interval, theta or tau is inferred from these small pilots.",
            "Tail/tolerance inference requires separate calibration and is not repaired by fitting a rate.",
        ],
    }
