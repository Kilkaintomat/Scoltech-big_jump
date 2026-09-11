"""P5: chain accuracy against length is `P(V_L = 1) = exp(-theta L Fbar(tau))`.

Corollary 3: with `(Z_t)` stationary with extremal index `theta` and `tau = tau_L -> inf` such
that `L Fbar(tau_L) -> lambda`,

    P(V_L = 0) = P(M_L > tau_L) = 1 - e^{-theta lambda} + o(1),

so `P(V_L = 1) ~ exp(-theta L Fbar(tau))`. The corollary's point is *not* that accuracy decays
exponentially in length -- it does so under both hypotheses, and Dziri et al. already measured
that. What separates the hypotheses is the **dependence on the tolerance**: `Fbar(tau)` is
`tau^{-alpha} l(tau)` under `Hheur` and `o(tau^{-s})` for every `s` under `Halg`. Length alone
does not identify the mechanism; the tail does.

`Fbar` is the GPD tail fitted on verified traces. The fit is compared with an unconstrained
per-length model -- one probability per `L` -- by a likelihood-ratio test, which is what makes
"the law fits" a statement with a `p`-value behind it rather than a look at a plot.

**`(theta, tau)` is not identified by this likelihood, and treating it as two parameters
understates the degrees of freedom.** Appendix B.4 says to fit "by maximum likelihood in
`(theta, tau)`", but the two enter the likelihood only through their product:
`P(V_L = 1) = exp(-c L)` with `c = theta Fbar(tau)`. Any `theta` can be traded against a `tau`
that keeps `c` fixed. Measured on the surrogate with a labelling threshold of `tau = 7.871`, the
free fit returned `theta = 0.178, tau = 4.385` -- a different pair with the same product, and
equally good likelihood. The consequences are that the reported `tau` is arbitrary and that the
likelihood-ratio test has `n_lengths - 1` degrees of freedom, not `n_lengths - 2`.

This module therefore fits the identified quantity `c` and then **pins `theta` independently**,
from the extremal index of the step deviations, which is what `theta` means in Corollary 3 in the
first place. `tau` is then recovered by solving `Fbar(tau) = c / theta`, and is a real estimate
rather than one half of an underdetermined pair.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd
from scipy import optimize, stats

from ..logging import get_logger
from ..stats import gpd_fit, select_k, sorted_positive_desc
from .dataset import subset, validate_table

__all__ = ["LengthLawFit", "P5Result", "fit_length_law", "run_p5"]


def _as_int(value: Any) -> int:
    """Narrow a pandas groupby key to `int`; the stubs type these as bare `Hashable`."""
    return int(cast(int, value))


log = get_logger(__name__)


@dataclass
class LengthLawFit:
    """The fitted `(theta, tau)` and how well the law does against a free per-length model."""

    theta: float
    tau: float
    fbar_tau: float
    rate_per_step: float
    theta_source: str
    loglik: float
    loglik_saturated: float
    lr_statistic: float
    df: int
    p_value: float
    converged: bool
    gpd_shape: float
    gpd_scale: float
    gpd_threshold: float
    exceedance_rate: float
    tolerance_status: str

    @property
    def fits(self) -> bool:
        """The constrained law is not rejected against the free per-length model."""
        return bool(self.p_value >= 0.05)

    def as_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "fits": self.fits}


def _gpd_tail(z: np.ndarray, *, k: int | None = None) -> tuple[float, float, float, float]:
    """Fit the upper tail of `z` and return `(shape, scale, threshold, exceedance_rate)`.

    The survival above the GPD threshold `u` is then
    `Fbar(x) = zeta_u (1 + shape (x - u)/scale)^{-1/shape}`, with `zeta_u = P(Z > u)` estimated
    by the exceedance fraction. Below `u` the empirical survival is used instead, because the
    GPD says nothing there.
    """
    x = sorted_positive_desc(z)
    if k is None:
        k = select_k(x, "double_bootstrap", k_min=20, k_max_frac=0.25, resamples=100).k
    k = int(np.clip(k, 20, x.size - 2))
    u = float(x[k])
    fit = gpd_fit(x[:k] - u, threshold=u)
    if not fit.converged:
        raise ValueError("cannot extrapolate length law with failed GPD fit: " + fit.message)
    return float(fit.gamma), float(fit.sigma), u, float(k) / float(x.size)


def _survival(
    x: float, shape: float, scale: float, threshold: float, rate: float, empirical: np.ndarray
) -> float:
    """`Fbar(x)`: the GPD tail above the threshold, the empirical survival below it."""
    if x <= threshold:
        return float(np.mean(empirical > x))
    y = x - threshold
    if abs(shape) < 1e-12:
        return float(rate * math.exp(-y / scale))
    base = 1.0 + shape * y / scale
    if base <= 0:
        return 0.0
    return float(rate * base ** (-1.0 / shape))


def fit_length_law(
    counts: dict[int, tuple[int, int]],
    verified_z: np.ndarray,
    *,
    k: int | None = None,
    theta: float | None = None,
) -> LengthLawFit:
    """Fit `P(V_L = 1) = exp(-c L)` to per-length verified counts, then split `c` into `(theta, tau)`.

    `counts` maps `L` to `(n_verified, n_total)`. The likelihood is binomial in each length and
    depends on one parameter, `c = theta Fbar(tau)`. Pass `theta` (from the extremal index) to
    recover `tau` by inverting `Fbar`; without it, `theta = 1` is assumed and the reported `tau`
    is the tolerance a non-clustering process would need to produce the same accuracy curve.
    """
    lengths = np.array(sorted(counts), dtype=float)
    if lengths.size < 3:
        raise ValueError(f"need at least 3 distinct lengths, got {lengths.size}")
    ok = np.array([counts[int(length)][0] for length in lengths], dtype=float)
    total = np.array([counts[int(length)][1] for length in lengths], dtype=float)
    if np.any(total <= 0) or np.any(lengths <= 0):
        raise ValueError("lengths and total counts must be positive")
    if np.any(ok < 0) or np.any(ok > total) or not np.all(np.isfinite(total + ok)):
        raise ValueError("verified counts must lie between zero and total")
    if theta is not None and not (np.isfinite(theta) and 0 < theta <= 1):
        raise ValueError("theta must lie in (0, 1]")

    shape, scale, threshold, rate = _gpd_tail(verified_z, k=k)
    empirical = np.asarray(verified_z, dtype=float)

    def neg_loglik(log_c: float) -> float:
        c = math.exp(log_c)
        p_ok = np.clip(np.exp(-c * lengths), 1e-12, 1 - 1e-12)
        return float(-np.sum(ok * np.log(p_ok) + (total - ok) * np.log1p(-p_ok)))

    res = optimize.minimize_scalar(
        neg_loglik,
        bounds=(math.log(1e-12), math.log(10.0)),
        method="bounded",
        options={"xatol": 1e-12},
    )
    if not math.isfinite(res.fun):  # pragma: no cover - would need a degenerate sample
        raise RuntimeError("the length-law likelihood could not be optimised")
    c = math.exp(float(res.x))
    loglik = -float(res.fun)

    theta_hat = 1.0 if theta is None else float(theta)
    theta_source = (
        "assumed 1 (no extremal-index estimate supplied)" if theta is None else "extremal index"
    )
    fbar_target = c / theta_hat
    if fbar_target > 1:
        tau = fbar = float("nan")
        tolerance_status = "incompatible_rate_exceeds_theta"
    else:
        tau = _invert_survival(fbar_target, shape, scale, threshold, rate, empirical)
        fbar = _survival(tau, shape, scale, threshold, rate, empirical)
        tolerance_status = "empirical_body_quantile" if fbar_target >= rate else "gpd_tail"

    # Saturated model: one free probability per length.
    p_hat = np.clip(ok / total, 1e-12, 1 - 1e-12)
    loglik_sat = float(np.sum(ok * np.log(p_hat) + (total - ok) * np.log1p(-p_hat)))

    lr = 2.0 * (loglik_sat - loglik)
    # One free parameter, not two: only c = theta * Fbar(tau) enters the likelihood.
    df = int(lengths.size - 1)
    return LengthLawFit(
        theta=theta_hat,
        tau=tau,
        fbar_tau=fbar,
        rate_per_step=c,
        theta_source=theta_source,
        loglik=loglik,
        loglik_saturated=loglik_sat,
        lr_statistic=float(lr),
        df=df,
        p_value=float(stats.chi2.sf(max(lr, 0.0), df=df)) if df > 0 else float("nan"),
        converged=bool(res.success),
        gpd_shape=shape,
        gpd_scale=scale,
        gpd_threshold=threshold,
        exceedance_rate=rate,
        tolerance_status=tolerance_status,
    )


def _invert_survival(
    target: float,
    shape: float,
    scale: float,
    threshold: float,
    rate: float,
    empirical: np.ndarray,
) -> float:
    """Solve `Fbar(tau) = target` for `tau`, using the GPD tail above the threshold."""
    if target >= rate:
        # The target survival is inside the body, where the empirical distribution rules.
        return float(np.quantile(empirical, max(0.0, 1.0 - target)))
    if abs(shape) < 1e-12:
        return float(threshold + scale * math.log(rate / target))
    return float(threshold + scale / shape * ((target / rate) ** (-shape) - 1.0))


@dataclass
class P5Result:
    """The length law for one (model, layer, statistic) cell."""

    model: str
    layer: int
    statistic: str
    fit: LengthLawFit
    observed: list[dict[str, Any]] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "layer": self.layer,
            "statistic": self.statistic,
            "theta": self.fit.theta,
            "theta_source": self.fit.theta_source,
            "tau": self.fit.tau,
            "fbar_tau": self.fit.fbar_tau,
            "tolerance_status": self.fit.tolerance_status,
            "rate_per_step": self.fit.rate_per_step,
            "gpd_shape": self.fit.gpd_shape,
            "lr": self.fit.lr_statistic,
            "df": self.fit.df,
            "p_value": self.fit.p_value,
            "fits": self.fit.fits,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.row(), "fit": self.fit.as_dict(), "observed": self.observed}


def _estimate_theta(cell: pd.DataFrame, quantile: float = 0.99) -> float | None:
    """Extremal index of the step-deviation process, pooled over traces."""
    from ..stats import extremal_index, traces_from_groups

    series = traces_from_groups(
        cell["z"].to_numpy(dtype=float), cell["trace_id"].to_numpy(), cell["t"].to_numpy()
    )
    if not series:
        return None
    theta = extremal_index(series, quantile=quantile).theta
    return None if not np.isfinite(theta) else float(theta)


def run_p5(
    df: pd.DataFrame,
    *,
    min_traces_per_length: int = 20,
    k: int | None = None,
    theta_quantile: float = 0.99,
) -> list[P5Result]:
    """Fit the length law wherever the table contains enough distinct trace lengths."""
    validate_table(df)
    results: list[P5Result] = []

    for (model, layer, statistic), cell in df.groupby(["model", "layer", "statistic"], sort=True):
        per_trace = cell.groupby("trace_id").agg(L=("L", "first"), outcome=("outcome", "first"))
        counts: dict[int, tuple[int, int]] = {}
        observed: list[dict[str, Any]] = []
        for length, group in per_trace.groupby("L"):
            n_total = len(group)
            if n_total < min_traces_per_length:
                continue
            n_ok = int((group["outcome"] == "verified").sum())
            counts[_as_int(length)] = (n_ok, n_total)
            observed.append(
                {"L": _as_int(length), "n": n_total, "verified": n_ok, "accuracy": n_ok / n_total}
            )
        if len(counts) < 3:
            log.info(
                "skipping P5 for %s/L%s/%s: %d usable lengths (need 3)",
                model,
                layer,
                statistic,
                len(counts),
            )
            continue

        verified_z = subset(cell, "verified")["z"].to_numpy(dtype=float)
        if verified_z.size < 200:
            log.info("skipping P5 for %s/L%s/%s: too few verified steps", model, layer, statistic)
            continue

        # theta is what Corollary 3 means by an extremal index, so estimate it as one rather than
        # leaving it to trade against tau inside an unidentified likelihood.
        theta_hat = _estimate_theta(cell, quantile=theta_quantile)
        fit = fit_length_law(counts, verified_z, k=k, theta=theta_hat)
        results.append(
            P5Result(
                model=str(model),
                layer=_as_int(layer),
                statistic=str(statistic),
                fit=fit,
                observed=observed,
            )
        )
        log.info(
            "P5 %s/L%s/%s: c=%.4e theta=%.3f (%s) tau=%.3f Fbar=%.2e LR=%.2f (df=%d) p=%.3f fits=%s",
            model,
            layer,
            statistic,
            fit.rate_per_step,
            fit.theta,
            fit.theta_source,
            fit.tau,
            fit.fbar_tau,
            fit.lr_statistic,
            fit.df,
            fit.p_value,
            fit.fits,
        )
    return results
