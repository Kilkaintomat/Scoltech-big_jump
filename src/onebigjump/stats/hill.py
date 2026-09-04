"""Hill estimator and the pooled-trace log-moments it shares with the moment estimator.

The estimator is equation 3 of the paper,

    gamma_hat_H(k) = (1/k) sum_{i=1..k} log( Z_(i) / Z_(k+1) ),

on the pooled sample of all steps of all traces, `Z_(1) >= ... >= Z_(n)`. Theorem 6 says the
pooling is legitimate for arbitrary within-trace dependence as long as `k -> inf`, `k/n -> 0`
and `L/k -> 0`; nothing here assumes independence.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "hill",
    "hill_curve",
    "log_moments",
    "sorted_positive_desc",
]


def sorted_positive_desc(z: np.ndarray) -> np.ndarray:
    """Descending order statistics of the strictly positive, finite entries of `z`."""
    z = np.asarray(z, dtype=np.float64).ravel()
    z = z[np.isfinite(z) & (z > 0.0)]
    if z.size == 0:
        raise ValueError("no strictly positive finite observations")
    z.sort()
    return z[::-1]


def log_moments(
    z: np.ndarray, k_max: int | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised `M^(1)_k` and `M^(2)_k` for every `k = 1 .. k_max`.

    Returns `(k_grid, M1, M2)` where

        M^(r)_k = (1/k) sum_{i<=k} ( log Z_(i) - log Z_(k+1) )^r.

    `M1` is the Hill estimator itself. Computing both from prefix sums costs one pass, which
    matters because the trace bootstrap re-evaluates this hundreds of times.
    """
    x = sorted_positive_desc(z)
    n = x.size
    if n < 3:
        raise ValueError(f"need at least 3 positive observations, got {n}")
    hi = n - 1 if k_max is None else int(min(k_max, n - 1))
    if hi < 1:
        raise ValueError("k_max must leave at least one order statistic below the threshold")

    lx = np.log(x)
    c1 = np.cumsum(lx)
    c2 = np.cumsum(lx * lx)
    k = np.arange(1, hi + 1, dtype=np.float64)
    thr = lx[1 : hi + 1]  # log Z_(k+1)

    s1 = c1[:hi]
    s2 = c2[:hi]
    m1 = s1 / k - thr
    # sum (lx_i - thr)^2 = sum lx_i^2 - 2 thr sum lx_i + k thr^2
    m2 = (s2 - 2.0 * thr * s1) / k + thr * thr
    # Ties at the threshold can push a float-noise negative value into m1/m2.
    np.clip(m1, 0.0, None, out=m1)
    np.clip(m2, 0.0, None, out=m2)
    return k.astype(np.int64), m1, m2


def hill_curve(z: np.ndarray, k_max: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """The full Hill plot `k -> gamma_hat_H(k)`, which the paper always reports alongside a point estimate."""
    k, m1, _ = log_moments(z, k_max=k_max)
    return k, m1


def hill(z: np.ndarray, k: int) -> float:
    """Hill estimate at a single `k`.

    Biased upward under `H_alg`: it is the MLE of `gamma > 0` for a Pareto tail and cannot
    return a nonpositive value, which is why the moment and GPD estimators are reported with it.
    """
    k = int(k)
    if k < 1:
        raise ValueError("k must be >= 1")
    grid, m1, _ = log_moments(z, k_max=k)
    if grid[-1] != k:
        raise ValueError(f"k={k} exceeds the available order statistics ({grid[-1]})")
    return float(m1[-1])
