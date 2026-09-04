"""Generalized Pareto MLE on the k excesses over Z_(k+1), plus the light-tailed alternatives.

Section 4 of the paper asks for three things from this module:

1. `gamma_hat_GPD(k)`, the third estimator of equation 3;
2. exponential and Weibull fits of the same excesses;
3. likelihood-ratio comparisons among them, so that `H_alg` can be a *positive* finding -- a
   light-tailed fit that beats the Pareto fit -- rather than merely the absence of a Hill plateau.

The GPD fit uses Grimshaw's (1993) profile reparameterisation. With excesses `y_i > 0` and
`theta = gamma / sigma`, the profile maximiser in `gamma` is available in closed form,

    gamma(theta) = (1/k) sum_i log(1 + theta y_i),      sigma(theta) = gamma(theta) / theta,

so the two-parameter fit collapses to a bounded one-dimensional search over
`theta > -1/max(y)`, which is far more stable than a joint quasi-Newton step on (gamma, sigma).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import optimize, stats

__all__ = [
    "FitComparison",
    "GPDFit",
    "compare_tail_models",
    "exponential_fit",
    "gpd_fit",
    "gpd_from_order_statistics",
    "gpd_nll",
    "weibull_fit",
]

_TINY = 1e-12


@dataclass
class GPDFit:
    """Result of a GPD maximum-likelihood fit to excesses over a threshold."""

    gamma: float
    sigma: float
    threshold: float
    n_excesses: int
    loglik: float
    converged: bool
    message: str = ""

    @property
    def alpha(self) -> float:
        """Tail index `alpha = 1/gamma`; infinite in the light-tailed case `gamma <= 0`."""
        return float("inf") if self.gamma <= 0 else 1.0 / self.gamma

    def as_dict(self) -> dict[str, Any]:
        return {
            "gamma": self.gamma,
            "sigma": self.sigma,
            "threshold": self.threshold,
            "n_excesses": self.n_excesses,
            "loglik": self.loglik,
            "converged": self.converged,
            "message": self.message,
        }


def _clean_excesses(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64).ravel()
    y = y[np.isfinite(y) & (y > 0.0)]
    if y.size < 5:
        raise ValueError(f"need at least 5 strictly positive excesses, got {y.size}")
    return y


def gpd_nll(gamma: float, sigma: float, y: np.ndarray) -> float:
    """Negative log-likelihood of the GPD with shape `gamma` and scale `sigma` at excesses `y`."""
    y = np.asarray(y, dtype=np.float64)
    if sigma <= 0:
        return math.inf
    if abs(gamma) < _TINY:
        return float(y.size * math.log(sigma) + y.sum() / sigma)
    t = 1.0 + gamma * y / sigma
    if np.any(t <= 0):
        return math.inf
    return float(y.size * math.log(sigma) + (1.0 + 1.0 / gamma) * np.log(t).sum())


def _profile_nll(theta: float, y: np.ndarray) -> float:
    """Negative profile log-likelihood in `theta = gamma/sigma`, up to an additive constant."""
    if abs(theta) < 1e-10:
        # theta -> 0 is the exponential limit; sigma -> mean(y).
        return float(y.size * (math.log(y.mean()) + 1.0))
    t = 1.0 + theta * y
    if np.any(t <= 0):
        return math.inf
    g = float(np.log(t).mean())
    if g <= 0 and theta > 0:
        return math.inf
    sigma = g / theta
    if sigma <= 0:
        return math.inf
    return float(y.size * (math.log(sigma) + g + 1.0))


def gpd_fit(excesses: np.ndarray, threshold: float = 0.0) -> GPDFit:
    """Maximum-likelihood GPD fit to `excesses` (already measured above `threshold`).

    Asymptotically normal for `gamma > -1/2` and consistent for `gamma > -1`
    (de Haan & Ferreira, 2006, Ch. 3), which is the range this project cares about.
    """
    y_raw = _clean_excesses(excesses)

    # Work in units of the median. `gamma` is scale-free, and in these units the maximiser sits
    # at `theta = 2^gamma - 1`, so a fixed bracket covers every shape this project can meet --
    # unlike a bracket scaled by the mean, which collapses as the mean diverges at gamma -> 1.
    scale_unit = float(np.median(y_raw))
    if not (scale_unit > 0 and math.isfinite(scale_unit)):
        scale_unit = float(y_raw.mean())
    y = y_raw / scale_unit

    lower = -1.0 / float(y.max()) + 1e-12  # support constraint 1 + theta*y_i > 0 for all i
    upper = 64.0  # gamma up to ~6; far beyond anything a residual stream produces
    grid = np.concatenate(
        [
            np.linspace(lower, -1e-8, 300),
            np.array([0.0]),
            np.geomspace(1e-8, upper, 400),
        ]
    )
    vals = np.array([_profile_nll(float(t), y) for t in grid])
    best = int(np.argmin(vals))
    lo = grid[max(best - 1, 0)]
    hi = grid[min(best + 1, grid.size - 1)]

    converged = True
    message = ""
    theta = float(grid[best])
    if hi > lo:
        res = optimize.minimize_scalar(
            _profile_nll,
            bounds=(lo, hi),
            args=(y,),
            method="bounded",
            options={"xatol": 1e-14},
        )
        if res.success and math.isfinite(res.fun) and res.fun <= vals[best] + 1e-9:
            theta = float(res.x)
        else:
            converged = bool(res.success)
            message = str(getattr(res, "message", ""))

    if abs(theta) < 1e-10:
        gamma, sigma = 0.0, float(y.mean())
    else:
        gamma = float(np.log1p(theta * y).mean())
        sigma = gamma / theta
        if sigma <= 0:  # numerical corner; fall back to the exponential limit
            gamma, sigma = 0.0, float(y.mean())
            converged = False
            message = message or "non-positive profile scale; fell back to the exponential limit"

    sigma *= scale_unit  # back to the original units; gamma is unchanged
    y = y_raw

    return GPDFit(
        gamma=gamma,
        sigma=sigma,
        threshold=float(threshold),
        n_excesses=int(y.size),
        loglik=-gpd_nll(gamma, sigma, y),
        converged=converged,
        message=message,
    )


def gpd_from_order_statistics(z: np.ndarray, k: int) -> GPDFit:
    """Fit the GPD to the `k` excesses over `Z_(k+1)`, the parametrisation of equation 3."""
    from .hill import sorted_positive_desc

    x = sorted_positive_desc(z)
    k = int(k)
    if not 1 <= k < x.size:
        raise ValueError(f"k must be in [1, n-1]; got k={k}, n={x.size}")
    thr = float(x[k])
    return gpd_fit(x[:k] - thr, threshold=thr)


def exponential_fit(excesses: np.ndarray) -> dict[str, Any]:
    """Exponential MLE -- the `gamma = 0` boundary of the GPD, i.e. the nested light-tailed null."""
    y = _clean_excesses(excesses)
    scale = float(y.mean())
    ll = float(-y.size * math.log(scale) - y.sum() / scale)
    return {"family": "exponential", "scale": scale, "loglik": ll, "n_params": 1}


def weibull_fit(excesses: np.ndarray) -> dict[str, Any]:
    """Two-parameter Weibull MLE (`scipy` `weibull_min` with location fixed at 0).

    A stretched-exponential alternative: shape `c < 1` is subexponential but still rapidly
    varying, so it belongs on the `H_alg` side of the dichotomy.
    """
    y = _clean_excesses(excesses)
    c, loc, scale = stats.weibull_min.fit(y, floc=0.0)
    ll = float(np.sum(stats.weibull_min.logpdf(y, c, loc=loc, scale=scale)))
    return {
        "family": "weibull",
        "shape": float(c),
        "scale": float(scale),
        "loglik": ll,
        "n_params": 2,
    }


@dataclass
class FitComparison:
    """GPD against its light-tailed competitors on one set of excesses."""

    gpd: GPDFit
    exponential: dict[str, Any]
    weibull: dict[str, Any]
    lr_gpd_vs_exponential: float
    p_gpd_vs_exponential: float
    vuong_gpd_vs_weibull: float
    p_gpd_vs_weibull: float
    aic: dict[str, float] = field(default_factory=dict)

    @property
    def favours(self) -> str:
        """Which side of the dichotomy the comparisons point to.

        `heavy` / `light` mean a decisive comparison against both competitors; the `-weak`
        variants mean the Pareto-versus-exponential comparison decided it but the non-nested
        Weibull comparison did not. A Weibull win is read as evidence for `H_alg`: a Weibull
        with any shape is rapidly varying, hence `xi = 0`.
        """
        beats_exp = self.p_gpd_vs_exponential < 0.05
        weibull_wins = self.vuong_gpd_vs_weibull < 0 and self.p_gpd_vs_weibull < 0.05
        gpd_wins_weibull = self.vuong_gpd_vs_weibull > 0 and self.p_gpd_vs_weibull < 0.05

        if weibull_wins:
            return "light"
        if self.gpd.gamma > 0 and beats_exp:
            return "heavy" if gpd_wins_weibull else "heavy-weak"
        if self.gpd.gamma <= 0 and beats_exp:
            return "light"
        if not beats_exp:
            return "light-weak"
        return "inconclusive"

    def as_dict(self) -> dict[str, Any]:
        return {
            "gpd": self.gpd.as_dict(),
            "exponential": self.exponential,
            "weibull": self.weibull,
            "lr_gpd_vs_exponential": self.lr_gpd_vs_exponential,
            "p_gpd_vs_exponential": self.p_gpd_vs_exponential,
            "vuong_gpd_vs_weibull": self.vuong_gpd_vs_weibull,
            "p_gpd_vs_weibull": self.p_gpd_vs_weibull,
            "aic": self.aic,
            "favours": self.favours,
        }


def _gpd_logpdf(y: np.ndarray, gamma: float, sigma: float) -> np.ndarray:
    if abs(gamma) < _TINY:
        return -math.log(sigma) - y / sigma
    return -math.log(sigma) - (1.0 + 1.0 / gamma) * np.log1p(gamma * y / sigma)


def compare_tail_models(excesses: np.ndarray, threshold: float = 0.0) -> FitComparison:
    """Fit GPD / exponential / Weibull to the same excesses and compare them.

    GPD versus exponential is a *nested* comparison (the exponential is `gamma = 0`), so the
    likelihood ratio is referred to a chi-square with one degree of freedom. GPD versus Weibull
    is *non-nested* with equal parameter counts, so it is compared by Vuong's (1989) test, whose
    statistic is asymptotically standard normal under the null of equal fit; a positive value
    favours the GPD. AIC is reported alongside for readers who want a single ranking.
    """
    y = _clean_excesses(excesses)
    g = gpd_fit(y, threshold=threshold)
    e = exponential_fit(y)
    w = weibull_fit(y)

    lr = 2.0 * (g.loglik - e["loglik"])
    # Nested, interior null in the two-sided sense: gamma may be negative, so the usual chi2_1
    # reference applies rather than the one-sided 50:50 mixture.
    p_lr = float(stats.chi2.sf(max(lr, 0.0), df=1))

    li_g = _gpd_logpdf(y, g.gamma, g.sigma)
    li_w = stats.weibull_min.logpdf(y, w["shape"], loc=0.0, scale=w["scale"])
    diff = np.asarray(li_g - li_w, dtype=np.float64)
    sd = float(diff.std(ddof=1))
    if sd < _TINY:
        vuong, p_v = 0.0, 1.0
    else:
        vuong = float(diff.mean() * math.sqrt(diff.size) / sd)
        p_v = float(2.0 * stats.norm.sf(abs(vuong)))

    aic = {
        "gpd": float(2 * 2 - 2 * g.loglik),
        "exponential": float(2 * 1 - 2 * e["loglik"]),
        "weibull": float(2 * 2 - 2 * w["loglik"]),
    }
    return FitComparison(
        gpd=g,
        exponential=e,
        weibull=w,
        lr_gpd_vs_exponential=float(lr),
        p_gpd_vs_exponential=p_lr,
        vuong_gpd_vs_weibull=vuong,
        p_gpd_vs_weibull=p_v,
        aic=aic,
    )
