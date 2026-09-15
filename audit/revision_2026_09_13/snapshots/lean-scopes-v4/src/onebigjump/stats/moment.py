"""Moment estimator of Dekkers, Einmahl and de Haan (1989).

    gamma_hat_M(k) = M^(1)_k + 1 - (1/2) ( 1 - (M^(1)_k)^2 / M^(2)_k )^{-1}

Consistent for every real `gamma`, so unlike Hill it can return a nonpositive value and can
therefore reject `H_heur`: an interval containing 0 is the outcome `H_alg` predicts.
"""

from __future__ import annotations

import numpy as np

from .hill import log_moments

__all__ = ["moment", "moment_curve"]

_EPS = 1e-300


def _from_moments(m1: np.ndarray, m2: np.ndarray) -> np.ndarray:
    m1 = np.asarray(m1, dtype=np.float64)
    m2 = np.asarray(m2, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(m2 > _EPS, m1 * m1 / np.maximum(m2, _EPS), np.nan)
        inner = 1.0 - ratio
        gamma = m1 + 1.0 - 0.5 / np.where(np.abs(inner) > 1e-12, inner, np.nan)
    return gamma


def moment_curve(z: np.ndarray, k_max: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """`k -> gamma_hat_M(k)` over the whole grid."""
    k, m1, m2 = log_moments(z, k_max=k_max)
    return k, _from_moments(m1, m2)


def moment(z: np.ndarray, k: int) -> float:
    k = int(k)
    if k < 1:
        raise ValueError("k must be >= 1")
    grid, g = moment_curve(z, k_max=k)
    if grid[-1] != k:
        raise ValueError(f"k={k} exceeds the available order statistics ({grid[-1]})")
    return float(g[-1])
