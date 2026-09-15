"""Trace-level bootstrap and the cluster variance it is standing in for.

Theorem 6(ii) gives `sqrt(k) (gamma_hat - gamma) => N(lambda/(1-rho), gamma^2 sigma_cl^2)` with

    sigma_cl^2 = lim_x Var( sum_{t<=L} g_x(Z_t) ) / ( gamma^2 L Fbar(x) ),
    g_x(z) = log+(z/x) - gamma 1{z > x}.

Traces are exactly independent, so resampling *traces* keeps the within-trace clusters intact
and reproduces that variance; resampling individual steps destroys them and underestimates the
variance by the factor `sigma_cl^2`. When several samples share a prompt, prompts are the
resampling unit instead, because traces from one prompt are not independent.

Two cautions from Section 4, both enforced here rather than left to the caller:

* the resampled estimator must use the *same fraction* `k/n` as the point estimate, not the
  same absolute `k`;
* this is a **variance approximation only**. The full-sample bootstrap of an intermediate order
  statistic is not consistent for its distribution and does not capture the bias `lambda/(1-rho)`
  (Hall, 1990), so the intervals below are variance-based, and `m_out` exposes the `m' -> inf`,
  `m'/m -> 0` subsampling scheme for callers who need a consistent one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from .hill import log_moments, sorted_positive_desc

__all__ = ["BootstrapResult", "cluster_variance", "effective_sample", "group_bootstrap"]

Estimator = Callable[[np.ndarray, int], float]
Unit = Literal["trace", "prompt", "step"]


@dataclass
class BootstrapResult:
    """Point estimate with a resampling-based standard error and percentile interval."""

    estimate: float
    se: float
    ci_low: float
    ci_high: float
    level: float
    n_resamples: int
    n_valid: int
    unit: str
    replicates: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))

    def as_dict(self, keep_replicates: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {
            "estimate": self.estimate,
            "se": self.se,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "level": self.level,
            "n_resamples": self.n_resamples,
            "n_valid": self.n_valid,
            "unit": self.unit,
        }
        if keep_replicates:
            out["replicates"] = self.replicates.tolist()
        return out


def _group_slices(groups: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    """Index arrays, one per distinct group, in order of first appearance."""
    uniq, inverse = np.unique(groups, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    counts = np.bincount(inverse, minlength=uniq.size)
    bounds = np.concatenate([[0], np.cumsum(counts)])
    return uniq, [order[bounds[i] : bounds[i + 1]] for i in range(uniq.size)]


def group_bootstrap(
    z: np.ndarray,
    groups: Sequence[Any] | np.ndarray | None,
    estimator: Estimator,
    *,
    k: int,
    resamples: int = 500,
    level: float = 0.95,
    unit: Unit = "trace",
    seed: int = 0,
    m_out: int | None = None,
) -> BootstrapResult:
    """Resample whole groups with replacement and recompute `estimator(z, k')`.

    `k' = round(k/n * n')` keeps the tail *fraction* fixed, as Section 4 requires. `groups` is
    the trace id (or the prompt id when several traces share a prompt); pass `unit="step"` only
    to demonstrate the variance understatement it causes, never for a reported interval.
    `m_out` selects the consistent `m' out of m` scheme (`m' -> inf`, `m'/m -> 0`).
    """
    z = np.asarray(z, dtype=np.float64).ravel()
    n = z.size
    if n < 10:
        raise ValueError(f"need at least 10 observations, got {n}")
    frac = float(k) / float(n)
    point = float(estimator(z, int(k)))
    rs = np.random.default_rng(seed)

    if unit == "step" or groups is None:
        blocks = [np.array([i]) for i in range(n)]
    else:
        g = np.asarray(groups).ravel()
        if g.size != n:
            raise ValueError(f"groups has length {g.size}, expected {n}")
        _, blocks = _group_slices(g)

    m = len(blocks)
    draw = m if m_out is None else int(min(max(m_out, 2), m))

    reps: list[float] = []
    for _ in range(int(resamples)):
        pick = rs.integers(0, m, size=draw)
        idx = np.concatenate([blocks[j] for j in pick]) if draw else np.empty(0, dtype=int)
        sample = z[idx]
        n_b = sample.size
        k_b = round(frac * int(n_b))
        if n_b < 10 or k_b < 2 or k_b >= n_b:
            continue
        try:
            val = float(estimator(sample, k_b))
        except (ValueError, FloatingPointError):
            continue
        if np.isfinite(val):
            reps.append(val)

    arr = np.asarray(reps, dtype=np.float64)
    if arr.size < 2:
        return BootstrapResult(
            point,
            float("nan"),
            float("nan"),
            float("nan"),
            level,
            int(resamples),
            int(arr.size),
            unit,
            arr,
        )

    a = (1.0 - float(level)) / 2.0
    lo, hi = np.quantile(arr, [a, 1.0 - a])
    return BootstrapResult(
        estimate=point,
        se=float(arr.std(ddof=1)),
        ci_low=float(lo),
        ci_high=float(hi),
        level=float(level),
        n_resamples=int(resamples),
        n_valid=int(arr.size),
        unit=unit if groups is not None else "step",
        replicates=arr,
    )


def cluster_variance(z: np.ndarray, groups: Sequence[Any] | np.ndarray, k: int) -> dict[str, float]:
    """Direct estimate of `sigma_cl^2` from the trace contributions of Theorem 6(ii).

    With threshold `b = Z_(k+1)` and `Y_j = sum_t g_b(Z_t^{(j)})`, the theorem's normalisation
    `Var(Y) / (gamma^2 L Fbar(b))` becomes `m Var(Y) / (gamma^2 k)`, since `L Fbar(b) ~ k/m`.
    A value near 1 says the steps behave independently in the tail; a value above 1 is the
    variance inflation caused by the clusters Theorem 5 predicts (a jump followed by its
    geometric relaxation), and is exactly what a step-level bootstrap would miss.
    """
    z = np.asarray(z, dtype=np.float64).ravel()
    g = np.asarray(groups).ravel()
    if g.size != z.size:
        raise ValueError("z and groups must have the same length")

    x = sorted_positive_desc(z)
    k = int(k)
    if not 1 <= k < x.size:
        raise ValueError(f"k must be in [1, n-1]; got k={k}, n={x.size}")
    b = float(x[k])
    _, m1, _ = log_moments(x, k_max=k)
    gamma = float(m1[-1])
    if gamma <= 0:
        return {"sigma2_cl": float("nan"), "gamma": gamma, "threshold": b, "n_groups": 0}

    contrib = np.where(z > b, np.log(np.maximum(z, b) / b) - gamma, 0.0)
    _, blocks = _group_slices(g)
    y = np.array([contrib[idx].sum() for idx in blocks], dtype=np.float64)
    m = y.size
    if m < 2:
        return {"sigma2_cl": float("nan"), "gamma": gamma, "threshold": b, "n_groups": m}

    sigma2 = float(m * y.var(ddof=1) / (gamma * gamma * k))
    return {
        "sigma2_cl": sigma2,
        "gamma": gamma,
        "threshold": b,
        "n_groups": int(m),
        "mean_exceedances_per_group": float(np.mean([np.sum(z[idx] > b) for idx in blocks])),
    }


def effective_sample(sigma2_cl: float, k: int) -> float:
    """`k / sigma_cl^2`: the number of *independent* exceedances the clustered sample is worth."""
    if not np.isfinite(sigma2_cl) or sigma2_cl <= 0:
        return float("nan")
    return float(k) / float(sigma2_cl)
