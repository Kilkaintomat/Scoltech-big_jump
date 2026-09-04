"""Tail diagnostics: Hill plots with bands, survival and mean-excess curves, identifiability.

Section 4 fixes what "well identified" means in this project, and it is not a single number:
a stable plateau of the Hill plot over a decade of `k`, *together with* agreement of the three
estimators of equation 3. `identified_tail` implements exactly that test, so the phrase can be
used in the paper with a definition behind it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .bootstrap import group_bootstrap
from .hill import hill, hill_curve, log_moments, sorted_positive_desc
from .moment import moment_curve

__all__ = [
    "IdentifiedTail",
    "hill_plot",
    "identified_tail",
    "mean_excess",
    "pareto_qq",
    "survival",
]


def survival(z: np.ndarray, n_points: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Empirical survival `(x, P(Z > x))` on the observed points, for log-log plots.

    Uses `i/n` at the `i`-th largest value, so the largest observation plots at `1/n` rather
    than at zero and survives a log axis.
    """
    x = sorted_positive_desc(z)
    n = x.size
    s = np.arange(1, n + 1, dtype=np.float64) / n
    if n_points is not None and n > n_points:
        # Keep the whole extreme tail and thin the bulk; the tail is what the plot is about.
        head = min(n_points // 2, n)
        idx = np.unique(
            np.concatenate(
                [np.arange(head), np.geomspace(head, n - 1, n_points - head).astype(np.int64)]
            )
        )
        return x[idx], s[idx]
    return x, s


def mean_excess(z: np.ndarray, n_points: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """Mean residual life `u -> E[Z - u | Z > u]`.

    Linear and increasing in `u` under a GPD with `gamma > 0`, flat at `gamma = 0`, decreasing
    for `gamma < 0` -- the classical visual counterpart to the estimators.
    """
    x = sorted_positive_desc(z)
    n = x.size
    ks = np.unique(np.geomspace(2, max(n - 1, 3), n_points).astype(np.int64))
    ks = ks[ks < n]
    u = x[ks]
    csum = np.cumsum(x)
    me = csum[ks - 1] / ks - u
    return u, me


def pareto_qq(z: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Exponential QQ plot of the `k` log-exceedances; a straight line means a Pareto tail.

    Returns `(theoretical, empirical)` with slope `gamma` under `Hheur`.
    """
    x = sorted_positive_desc(z)
    k = int(k)
    if not 1 <= k < x.size:
        raise ValueError(f"k must be in [1, n-1]; got k={k}, n={x.size}")
    emp = np.log(x[:k] / x[k])[::-1]
    theo = -np.log(1.0 - np.arange(1, k + 1, dtype=np.float64) / (k + 1.0))
    return theo, emp


def hill_plot(
    z: np.ndarray,
    groups: Sequence[Any] | np.ndarray | None = None,
    *,
    k_min: int = 20,
    k_max_frac: float = 0.5,
    n_points: int = 60,
    resamples: int = 0,
    level: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    """`k -> gamma_hat_H(k)` with optional pointwise trace-bootstrap bands.

    The paper always shows this curve; `resamples=0` returns the curve alone, which is the cheap
    path used inside sweeps.
    """
    x = sorted_positive_desc(z)
    n = x.size
    k_hi = min(int(k_max_frac * n), n - 2)
    if k_hi <= k_min:
        raise ValueError(f"empty k range: k_min={k_min}, k_max={k_hi}, n={n}")
    ks = np.unique(np.geomspace(k_min, k_hi, n_points).astype(np.int64))

    _, m1 = hill_curve(x, k_max=int(ks[-1]))
    gamma = m1[ks - 1]
    _, gm = moment_curve(x, k_max=int(ks[-1]))
    gamma_m = gm[ks - 1]

    out: dict[str, Any] = {
        "k": ks.tolist(),
        "hill": gamma.tolist(),
        "moment": gamma_m.tolist(),
        "n": int(n),
    }
    if resamples > 0:
        lo, hi = [], []
        for k in ks:
            b = group_bootstrap(
                z, groups, hill, k=int(k), resamples=int(resamples), level=level, seed=seed
            )
            lo.append(b.ci_low)
            hi.append(b.ci_high)
        out["ci_low"] = lo
        out["ci_high"] = hi
        out["level"] = float(level)
        out["resamples"] = int(resamples)
    return out


@dataclass
class IdentifiedTail:
    """The paper's operational identifiability check, with its two parts kept separate."""

    identified: bool
    plateau: bool
    agreement: bool
    decades: float
    plateau_k_range: tuple[int, int] | None
    spread: float
    estimator_spread: float
    detail: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "identified": self.identified,
            "plateau": self.plateau,
            "agreement": self.agreement,
            "decades": self.decades,
            "plateau_k_range": list(self.plateau_k_range) if self.plateau_k_range else None,
            "spread": self.spread,
            "estimator_spread": self.estimator_spread,
            "detail": self.detail,
        }


def identified_tail(
    z: np.ndarray,
    estimates: dict[str, float],
    *,
    k_min: int = 20,
    k_max_frac: float = 0.5,
    rel_tol: float = 0.15,
    min_decades: float = 1.0,
    estimator_tol: float = 0.10,
) -> IdentifiedTail:
    """Is the tail well identified? Plateau over `min_decades` of `k` **and** estimator agreement.

    `estimates` holds the three point estimates (`hill`, `moment`, `gpd`) at the selected `k`.
    Agreement is judged on an absolute scale as well as a relative one, because near `gamma = 0`
    a relative criterion is meaningless -- which is precisely the `H_alg` regime.
    """
    x = sorted_positive_desc(z)
    n = x.size
    k_hi = min(int(k_max_frac * n), n - 2)
    kk, m1, _ = log_moments(x, k_max=k_hi)
    lo_i = max(k_min - 1, 0)
    kk, m1 = kk[lo_i:], m1[lo_i:]

    best: tuple[float, int, int] = (0.0, 0, 0)
    if kk.size >= 5:
        i = 0
        for j in range(1, kk.size):
            while i < j:
                seg = m1[i : j + 1]
                centre = float(np.median(seg))
                if centre > 0 and (seg.max() - seg.min()) / centre <= rel_tol:
                    break
                i += 1
            if i < j:
                dec = math.log10(float(kk[j]) / float(kk[i]))
                if dec > best[0]:
                    best = (dec, int(kk[i]), int(kk[j]))

    decades, k_lo, k_hi_plateau = best
    plateau = decades >= float(min_decades)

    vals = np.array(
        [v for v in estimates.values() if v is not None and np.isfinite(v)], dtype=np.float64
    )
    if vals.size < 2:
        agreement, est_spread = False, float("nan")
    else:
        est_spread = float(vals.max() - vals.min())
        scale = max(float(np.mean(np.abs(vals))), 1e-3)
        agreement = bool(est_spread <= estimator_tol or est_spread / scale <= estimator_tol * 3)

    return IdentifiedTail(
        identified=bool(plateau and agreement),
        plateau=plateau,
        agreement=agreement,
        decades=float(decades),
        plateau_k_range=(k_lo, k_hi_plateau) if decades > 0 else None,
        spread=float(rel_tol),
        estimator_spread=est_spread,
        detail={
            "n": int(n),
            "estimates": {
                k: (None if v is None or not np.isfinite(v) else float(v))
                for k, v in estimates.items()
            },
            "min_decades": float(min_decades),
            "estimator_tol": float(estimator_tol),
        },
    )
