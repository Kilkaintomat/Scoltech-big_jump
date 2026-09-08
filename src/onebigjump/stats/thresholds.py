"""Choosing `k`, the number of upper order statistics.

The paper's primary rule is the double bootstrap of Danielsson, de Haan, Peng and de Vries
(2001) with `n1 = n^0.9` and 200 resamples, cross-checked against the Kolmogorov-Smirnov
criterion of Clauset, Shalizi and Newman (2009). Both are implemented here, together with a
plateau rule used only as a diagnostic and a fixed-fraction fallback.

`k` is never chosen by eye: whichever rule is used, `select_k` records the rule, the candidate
grid and the objective so the choice can be audited from the run manifest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from .hill import log_moments, sorted_positive_desc

__all__ = ["KSelection", "double_bootstrap_k", "ks_distance_k", "plateau_k", "select_k"]

KMethod = Literal["double_bootstrap", "ks", "plateau", "fixed_frac"]


@dataclass
class KSelection:
    """The chosen `k` together with everything needed to reproduce the choice."""

    k: int
    method: str
    n: int
    objective: float | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "method": self.method,
            "n": self.n,
            "objective": self.objective,
            "diagnostics": self.diagnostics,
        }


def _k_grid(n: int, k_min: int, k_max: int) -> np.ndarray:
    k_min = max(int(k_min), 2)
    k_max = min(int(k_max), n - 1)
    if k_max <= k_min:
        raise ValueError(f"empty k grid: k_min={k_min}, k_max={k_max}, n={n}")
    return np.arange(k_min, k_max + 1, dtype=np.int64)


def _control_variate(z: np.ndarray, k_max: int) -> tuple[np.ndarray, np.ndarray]:
    """`Q(k) = M^(2)_k - 2 (M^(1)_k)^2`, the quantity the double bootstrap drives to zero.

    Under a Pareto tail `E M^(1)_k -> gamma` and `E M^(2)_k -> 2 gamma^2`, so `Q(k) -> 0`; its
    mean square is the bootstrap's proxy for the asymptotic mean squared error of Hill.
    """
    k, m1, m2 = log_moments(z, k_max=k_max)
    return k, m2 - 2.0 * m1 * m1


def double_bootstrap_k(
    z: np.ndarray,
    *,
    n1_exponent: float = 0.9,
    resamples: int = 200,
    k_min: int = 2,
    k_max_frac: float = 0.5,
    seed: int = 0,
    max_pool: int | None = None,
) -> KSelection:
    """Danielsson et al. (2001) two-stage bootstrap choice of `k`.

    Stage 1 resamples `n1 = n^{n1_exponent}` points and minimises the mean square of the control
    variate over `k1`; stage 2 does the same at `n2 = n1^2 / n`. The optimal `k` for the full
    sample is then

        k = (k1*)^2 / k2* * [ (log k1*)^2 / (2 log n1 - log k1*)^2 ]^{(log n1 - log k1*)/log n1}.

    Returns the fixed-fraction fallback with `method="double_bootstrap:fallback"` when the
    sample is too small for the two stages to be separated or the stage-2 minimum lands above
    the stage-1 minimum, which is the documented failure mode of the rule.
    """
    x = sorted_positive_desc(z)
    n = x.size
    if max_pool is not None and n > max_pool:
        rs = np.random.default_rng(seed)
        x = np.sort(rs.choice(x, size=int(max_pool), replace=False))[::-1]
        n = x.size

    n1 = round(n ** float(n1_exponent))
    n2 = round(n1 * n1 / n)
    fallback = KSelection(
        k=max(k_min, min(int(0.05 * n), n - 2)),
        method="double_bootstrap:fallback",
        n=n,
        diagnostics={"n1": n1, "n2": n2, "reason": ""},
    )
    # Below roughly n = 80 the two stages are not separated enough for the AMSE expansion the
    # rule is built on; returning a fraction of a tiny sample would look like a choice but be noise.
    if n1 < 50 or n2 < 20 or n1 >= n:
        fallback.diagnostics["reason"] = "sample too small to separate the two bootstrap stages"
        return fallback

    rs = np.random.default_rng(seed)

    def _stage(sub_n: int) -> tuple[int, np.ndarray, np.ndarray]:
        k_hi = max(int(k_max_frac * sub_n), 3)
        # The full-sample minimum can exceed the entire smaller bootstrap tail.
        grid = _k_grid(sub_n, min(k_min, k_hi - 1), k_hi)
        acc = np.zeros(grid.size, dtype=np.float64)
        seen = np.zeros(grid.size, dtype=np.int64)
        offset = int(grid[0]) - 1  # the control-variate curve is indexed from k = 1
        for _ in range(int(resamples)):
            sample = rs.choice(x, size=sub_n, replace=True)
            _, q = _control_variate(sample, k_max=int(grid[-1]))
            seg = q[offset : offset + grid.size]
            acc[: seg.size] += np.square(seg)
            seen[: seg.size] += 1
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_sq = np.where(seen > 0, acc / np.maximum(seen, 1), np.inf)
        return int(grid[int(np.argmin(mean_sq))]), grid, mean_sq

    k1, grid1, obj1 = _stage(n1)
    k2, _, _ = _stage(n2)

    if not (0 < k2 < k1):
        fallback.diagnostics.update(
            {"k1": k1, "k2": k2, "reason": "stage-2 minimum did not fall below stage-1 minimum"}
        )
        return fallback

    log_n1 = math.log(n1)
    log_k1 = math.log(k1)
    denom = 2.0 * log_n1 - log_k1
    if denom <= 0 or log_k1 <= 0:
        fallback.diagnostics.update({"k1": k1, "k2": k2, "reason": "degenerate logarithms"})
        return fallback

    ratio = (log_k1**2) / (denom**2)
    power = (log_n1 - log_k1) / log_n1
    k_opt = (k1**2) / k2 * (ratio**power)
    k_final = int(max(k_min, min(round(k_opt), n - 2)))

    return KSelection(
        k=k_final,
        method="double_bootstrap",
        n=n,
        objective=float(np.min(obj1)),
        diagnostics={
            "n1": n1,
            "n2": n2,
            "k1_star": k1,
            "k2_star": k2,
            "k_raw": float(k_opt),
            "resamples": int(resamples),
            "n1_exponent": float(n1_exponent),
            "k_grid_stage1": [int(grid1[0]), int(grid1[-1])],
        },
    )


def ks_distance_k(
    z: np.ndarray, *, k_min: int = 10, k_max_frac: float = 0.5, n_candidates: int = 200
) -> KSelection:
    """Clauset et al. (2009): pick `k` minimising the KS distance to the fitted Pareto tail.

    For each candidate the threshold is `Z_(k+1)`, the shape is the Hill estimate at that `k`,
    and the distance is `sup_x |F_n(x) - F_pareto(x)|` over the `k` exceedances.
    """
    x = sorted_positive_desc(z)
    n = x.size
    grid = _k_grid(n, k_min, int(k_max_frac * n))
    if grid.size > n_candidates:
        grid = np.unique(np.linspace(grid[0], grid[-1], n_candidates).round().astype(np.int64))

    _, m1, _ = log_moments(x, k_max=int(grid[-1]))
    dists = np.full(grid.size, np.inf)
    for i, k in enumerate(grid):
        gamma = float(m1[int(k) - 1])
        if not (gamma > 1e-8):
            continue
        thr = float(x[int(k)])
        if thr <= 0:
            continue
        ratios = x[: int(k)] / thr  # >= 1 by construction
        # Empirical CDF of the exceedances against 1 - r^{-1/gamma}.
        theo = 1.0 - np.power(ratios, -1.0 / gamma)
        emp_hi = np.arange(int(k), 0, -1) / int(k)  # ratios are descending
        emp_lo = np.arange(int(k) - 1, -1, -1) / int(k)
        dists[i] = float(max(np.max(np.abs(theo - emp_lo)), np.max(np.abs(theo - emp_hi))))

    best = int(np.argmin(dists))
    return KSelection(
        k=int(grid[best]),
        method="ks",
        n=n,
        objective=float(dists[best]),
        diagnostics={"k_grid": [int(grid[0]), int(grid[-1])], "n_candidates": int(grid.size)},
    )


def plateau_k(
    z: np.ndarray, *, k_min: int = 20, k_max_frac: float = 0.5, window: int = 0, tol: float = 0.05
) -> KSelection:
    """Longest stretch of the Hill plot whose relative spread stays within `tol`.

    Diagnostic only. The paper's operational definition of a well-identified tail is a stable
    plateau over a decade of `k` *together with* agreement of the three estimators, so this
    reports where the plateau is rather than being trusted on its own.
    """
    x = sorted_positive_desc(z)
    n = x.size
    k_hi = min(int(k_max_frac * n), n - 1)
    kk, m1, _ = log_moments(x, k_max=k_hi)
    lo = max(int(k_min) - 1, 0)
    kk, m1 = kk[lo:], m1[lo:]
    if kk.size < 5:
        raise ValueError("Hill plot too short for a plateau search")
    w = int(window) if window > 0 else max(5, kk.size // 20)

    best_i, best_spread = 0, math.inf
    for i in range(kk.size - w):
        seg = m1[i : i + w]
        centre = float(np.median(seg))
        if centre <= 0:
            continue
        spread = float(seg.max() - seg.min()) / centre
        if spread < best_spread:
            best_spread, best_i = spread, i

    k = int(kk[best_i + w // 2])
    return KSelection(
        k=k,
        method="plateau",
        n=n,
        objective=best_spread,
        diagnostics={"window": w, "tol": tol, "stable": bool(best_spread <= tol)},
    )


def select_k(
    z: np.ndarray,
    method: KMethod = "double_bootstrap",
    *,
    k_min: int = 20,
    k_max_frac: float = 0.25,
    fixed_frac: float = 0.05,
    resamples: int = 200,
    n1_exponent: float = 0.9,
    seed: int = 0,
    max_pool: int | None = None,
) -> KSelection:
    """Dispatch to one of the `k` rules, clipping the result into `[k_min, k_max_frac * n]`."""
    x = sorted_positive_desc(z)
    n = x.size
    k_hi = max(int(k_max_frac * n), k_min + 1)

    if method == "double_bootstrap":
        sel = double_bootstrap_k(
            x,
            n1_exponent=n1_exponent,
            resamples=resamples,
            k_min=k_min,
            k_max_frac=k_max_frac,
            seed=seed,
            max_pool=max_pool,
        )
    elif method == "ks":
        sel = ks_distance_k(x, k_min=k_min, k_max_frac=k_max_frac)
    elif method == "plateau":
        sel = plateau_k(x, k_min=k_min, k_max_frac=k_max_frac)
    elif method == "fixed_frac":
        sel = KSelection(k=int(fixed_frac * n), method=f"fixed_frac:{fixed_frac}", n=n)
    else:  # pragma: no cover - guarded by the config Literal
        raise ValueError(f"unknown k selector: {method}")

    clipped = int(np.clip(sel.k, k_min, min(k_hi, n - 2)))
    if clipped != sel.k:
        sel.diagnostics["k_before_clip"] = sel.k
        sel.k = clipped
    return sel
