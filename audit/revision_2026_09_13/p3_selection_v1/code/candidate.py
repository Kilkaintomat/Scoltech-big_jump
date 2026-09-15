"""Experimental constrained GPD fit; primary onebigjump.stats.gpd is untouched.

Grimshaw (1993), sections 2.1-2.2, with project gamma = -paper k.
Enumerate interior stationary solutions with gamma > -1 and compare their
likelihood to the uniform boundary gamma=-1, sigma=max(excesses). Boundary wins
are retained diagnostically but never supplied as ordinary bootstrap estimates.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, asdict

import numpy as np
from scipy.optimize import brentq


@dataclass
class CandidateFit:
    gamma: float
    sigma: float
    loglik: float
    n_excesses: int
    converged: bool
    reason: str
    interior_candidates: int
    boundary_loglik: float

    @property
    def shape_estimate(self):
        return self.gamma if self.converged else float("nan")

    def as_dict(self):
        return {**asdict(self), "shape_estimate": self.shape_estimate}


def constrained_gpd_fit(excesses, grid_size=513):
    raw = np.asarray(excesses, dtype=np.float64).ravel()
    raw = raw[np.isfinite(raw) & (raw > 0)]
    if len(raw) < 5:
        raise ValueError("need at least 5 positive finite excesses")
    n = len(raw)
    maximum = float(raw.max())
    r = raw / maximum
    boundary_ll = -n * math.log(maximum)
    boundary = CandidateFit(-1.0, maximum, boundary_ll, n, False,
                            "uniform_boundary_wins", 0, boundary_ll)
    if np.all(r == 1):
        return boundary
    log_r = np.log(r)
    with np.errstate(divide="ignore"):
        log_one_minus_r = np.log1p(-r)
    moments = np.array([np.mean(r ** k) for k in range(9)])
    # h(s) = (1+mean(log(1+s*r)))*mean(1/(1+s*r))-1.
    # h(s)/s**2 removes the spurious double zero at s=0. Use its
    # analytic series near zero, rather than subtracting nearly equal numbers.
    a = np.zeros(9)
    b = np.array([(-1.0) ** k * moments[k] for k in range(9)])
    for k in range(1, 9):
        a[k] = (-1.0) ** (k + 1) * moments[k] / k
    coefficients = np.array([
        b[k] + sum(a[j] * b[k-j] for j in range(1, k+1))
        for k in range(2, 9)
    ])

    def logs_at(x):
        x = np.atleast_1d(x)
        # x=log(1+s), s=gamma*max(raw)/sigma.
        logs = np.logaddexp(log_one_minus_r[None, :], log_r[None, :] + x[:, None])
        close = np.abs(x) < 0.1
        if np.any(close):
            logs[close] = np.log1p(np.expm1(x[close, None]) * r[None, :])
        return logs

    def gamma_at(x):
        return float(logs_at(x).mean())

    # mean(log(1+s*r)) reaches -1 no later than x=-n because at
    # least one r equals 1 and every other logarithm is nonpositive.
    lower = brentq(lambda x: gamma_at(x) + 1, -float(n), 0,
                   xtol=1e-12, rtol=1e-12)
    minimum = float(r.min())
    positive_bound = 2 * (float(r.mean()) - minimum) / minimum ** 2
    upper = math.log1p(positive_bound)
    if not math.isfinite(upper) or upper > 300:
        boundary.reason = "numerical_search_range_exceeded"
        return boundary

    def score_array(x):
        x = np.atleast_1d(x)
        s = np.expm1(x)
        result = np.empty_like(s)
        near = np.abs(s) < 1e-3
        result[near] = np.polynomial.polynomial.polyval(s[near], coefficients)
        if np.any(~near):
            logs = logs_at(x[~near])
            g = logs.mean(axis=1)
            inv_mean = np.exp(-logs).mean(axis=1)
            result[~near] = ((1 + g) * inv_mean - 1) / s[~near] ** 2
        return result

    def score(x):
        return float(score_array(np.array([x]))[0])

    # Log-coordinate grids and explicit near-zero points are fixed numerical
    # search parameters. The preflight compares against a fourfold denser grid
    # and an independent two-dimensional SciPy likelihood optimization.
    grid = np.unique(np.concatenate([
        np.linspace(lower, 0, grid_size),
        np.linspace(0, upper, grid_size),
        np.array([-1e-5, -1e-7, 0, 1e-7, 1e-5]),
    ]))
    grid = grid[(grid >= lower) & (grid <= upper)]
    scores = score_array(grid)
    roots = []
    for i in np.flatnonzero(scores[:-1] * scores[1:] < 0):
        # A profile log-likelihood maximum has h going positive to negative.
        if scores[i] > 0 and scores[i+1] < 0:
            roots.append(brentq(score, float(grid[i]), float(grid[i+1]),
                                xtol=1e-12, rtol=1e-12))
    for i in range(1, len(grid)-1):
        if scores[i] == 0 and scores[i-1] > 0 and scores[i+1] < 0:
            roots.append(float(grid[i]))
    candidates = []
    for x in roots:
        s = math.expm1(x)
        if abs(s) < 1e-12:
            gamma = 0.0
            scale = float(r.mean())
        else:
            gamma = gamma_at(x)
            scale = gamma / s
        if gamma <= -1 or scale <= 0 or not math.isfinite(scale):
            continue
        # Check the representable scale/shape support, not just transformed x.
        if np.any(1 + gamma * r / scale <= 0):
            continue
        ll = -n * (math.log(scale) + gamma + 1 + math.log(maximum))
        candidates.append(CandidateFit(gamma, scale * maximum, ll, n, True,
                                       "interior_stationary_maximum", len(roots), boundary_ll))
    # An exponential stationary point is possible in the exact moment-equality case.
    if abs(coefficients[0]) <= 1e-14 * max(moments[2], 1e-300):
        scale = float(r.mean())
        candidates.append(CandidateFit(0.0, scale * maximum,
            -n * (math.log(scale) + 1 + math.log(maximum)), n, True,
            "exponential_stationary_point", len(roots), boundary_ll))
    boundary.interior_candidates = len(candidates)
    if not candidates:
        return boundary
    best = max(candidates, key=lambda fit: fit.loglik)
    best.interior_candidates = len(candidates)
    # Fixed likelihood tie tolerance in per-observation units. No arbitrary
    # epsilon shift of the support can turn a boundary result into a usable fit.
    if best.loglik <= boundary_ll + n * 1e-10:
        return boundary
    return best
