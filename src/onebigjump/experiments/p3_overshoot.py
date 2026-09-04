"""P3: the overshoot at the rejected step is Pareto-like, not concentrated at 1.

Proposition 1 is the operative statement, and it needs no independence: with
`Q_u(y) = P(Z > uy | Z > u)`,

    regularly varying tail  =>  Q_u(y) -> y^{-alpha}   (the failing step overshoots by a
                                                        Pareto factor: a catastrophe)
    rapidly varying tail    =>  Q_u(y) -> 0 for y > 1  (Z/u -> 1: the failing step is barely
                                                        over the line: a marginal failure)

So the test is the distribution of `Z_{t*}/tau` over refuted traces. `tau` is the `(1-q)`-quantile
of `Z` on **verified** traces for `q` in `{1e-2, 1e-3}` -- taken on verified traces so the
threshold is not chosen using the very steps whose overshoot is being measured -- and the fitted
GPD shape is compared with the pooled `gamma_hat` of Table 1: under `Hheur` they should agree,
under `Halg` the shape should be at most 0.

**Three overshoots are reported, not one, because they do not agree.** Measured on the Kesten
surrogate at `p = 0.05`, where `gamma = 0.357` exactly, at the 99.9% threshold:

    unconditional  P(Z > tau y | Z > tau)   shape  +0.454     <- Proposition 1, confirmed
    trace maximum  Z_{T^max} / tau          shape  +0.478
    first exceedance Z_{t*} / tau           shape  +0.127     <- what P3 as written measures

The first exceedance is attenuated by a factor of three, and it is not a pre-asymptotic effect:
raising the threshold across two decades leaves the shape at 0.06-0.13 while the unconditional
overshoot sits at 0.38-0.45. The cause is clustering. The extremal index at those thresholds is
`theta = 0.41` and `0.13`, so exceedances arrive in clusters -- a jump followed by its geometric
relaxation, exactly as Theorem 5 predicts -- and conditioning on being the *first* exceedance of
a cluster selects systematically smaller overshoots. Theorem 4(ii) derives
`P(Z_{t*} > tau y | V_L = 0) -> y^{-alpha}` **under extremal independence**, an assumption this
model violates by construction.

The consequence for the paper is that a small fitted shape in the `Z_{t*}` column is not evidence
against `Hheur`; it has to be read against the extremal index, which is why `theta` is reported
in every result here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd

from ..logging import get_logger
from ..stats import gpd_fit, group_bootstrap
from .dataset import subset, validate_table

__all__ = ["P3Result", "run_p3"]


def _as_int(value: Any) -> int:
    """Narrow a pandas groupby key to `int`; the stubs type these as bare `Hashable`."""
    return int(cast(int, value))


log = get_logger(__name__)


@dataclass
class P3Result:
    """The overshoot at one tolerance level, for one (model, layer, statistic) cell."""

    model: str
    layer: int
    statistic: str
    q: float
    tau: float
    n_refuted: int
    n_over_tau: int
    gpd_shape: float
    gpd_scale: float
    shape_ci: tuple[float, float]
    median_overshoot: float
    theta: float = float("nan")
    variants: dict[str, dict[str, Any]] = field(default_factory=dict)
    frac_above: dict[str, float] = field(default_factory=dict)
    survival: dict[str, list[float]] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "layer": self.layer,
            "statistic": self.statistic,
            "q": self.q,
            "tau": self.tau,
            "n_refuted": self.n_refuted,
            "n_over_tau": self.n_over_tau,
            "gpd_shape": self.gpd_shape,
            "shape_lo": self.shape_ci[0],
            "shape_hi": self.shape_ci[1],
            "median_overshoot": self.median_overshoot,
            "theta": self.theta,
            **{
                f"{name}_{field_}": value
                for name, variant in self.variants.items()
                for field_, value in variant.items()
                if field_ in {"shape", "median_u", "n"}
            },
            **{f"frac_above_{k}": v for k, v in self.frac_above.items()},
            **{f"cmp_{k}": v for k, v in self.comparison.items()},
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.row(),
            "survival": self.survival,
            "comparison": self.comparison,
            "variants": self.variants,
        }


def _overshoots(cell: pd.DataFrame, tau: float) -> tuple[np.ndarray, np.ndarray]:
    """`Z_{t*}` for every refuted trace whose failing deviation exceeded `tau`, and its trace ids."""
    refuted = cell[cell["outcome"] == "refuted"]
    at_star = refuted[refuted["t"] == refuted["t_star"]]
    z = at_star["z"].to_numpy(dtype=float)
    keep = np.isfinite(z) & (z > tau)
    return z[keep], at_star["trace_id"].to_numpy()[keep]


def _variant(values: np.ndarray, tau: float, label: str) -> dict[str, Any]:
    """Fit one of the three overshoot variants, or report why it could not be fitted."""
    values = values[np.isfinite(values) & (values > tau)]
    if values.size < 20:
        return {
            "label": label,
            "n": int(values.size),
            "shape": float("nan"),
            "median_u": float("nan"),
        }
    return {
        "label": label,
        "n": int(values.size),
        "shape": float(gpd_fit(values - tau, threshold=tau).gamma),
        "median_u": float(np.median(values / tau)),
    }


def _overshoot_variants(cell: pd.DataFrame, tau: float) -> tuple[dict[str, dict[str, Any]], float]:
    """The three overshoots of the module docstring, plus the extremal index at this `tau`.

    They are computed together because the gap between them is only interpretable next to
    `theta`: at `theta = 1` they coincide, and the further `theta` falls below 1 the more the
    first-exceedance variant is attenuated relative to the other two.
    """
    from ..stats import extremal_index, traces_from_groups

    refuted = cell[cell["outcome"] == "refuted"]
    series = traces_from_groups(
        refuted["z"].to_numpy(dtype=float),
        refuted["trace_id"].to_numpy(),
        refuted["t"].to_numpy(),
    )
    theta = float("nan")
    if series:
        theta = extremal_index(series, threshold=tau).theta

    first, _ = _overshoots(cell, tau)
    trace_max = np.array([s.max() for s in series]) if series else np.empty(0)
    unconditional = cell["z"].to_numpy(dtype=float)

    return (
        {
            "first": _variant(first, tau, "first exceedance Z_{t*} (P3 as written)"),
            "trace_max": _variant(trace_max, tau, "trace maximum Z_{T^max}"),
            "unconditional": _variant(unconditional, tau, "unconditional (Proposition 1)"),
        },
        theta,
    )


def run_p3(
    df: pd.DataFrame,
    *,
    thresholds_q: tuple[float, ...] = (1e-2, 1e-3),
    bootstrap_resamples: int = 500,
    ci_level: float = 0.95,
    seed: int = 0,
    min_over_tau: int = 20,
    pooled_gamma: dict[tuple[str, int, str], float] | None = None,
    tau_override: float | None = None,
) -> list[P3Result]:
    """Fit the overshoot distribution at each tolerance level.

    `pooled_gamma`, when given, is the Table 1 estimate for the same cell; the result then
    records whether the overshoot shape is compatible with it, which is what Section 5.1 asks
    ("the fitted shape should agree with gamma_hat from Table 1").

    `tau_override` exists for the calibration case and should not be used on real traces. Where
    the labels themselves came from a threshold -- as in the Kesten surrogate, where Hypothesis 1
    is imposed with its own `tau` -- every `Z_{t*}` is already conditioned on exceeding *that*
    threshold. Fitting the excesses over a lower, separately chosen `tau` then fits a
    distribution whose support starts well above zero, and the GPD shape comes out strongly
    negative no matter how heavy the tail is: measured at `p = 0.05`, shape -0.704 against a true
    `gamma` of 0.357. With the labelling threshold passed in, the fit is on the right sample.
    On Lean traces `t*` comes from the kernel and no such conditioning exists, so the quantile of
    the verified traces is the correct threshold and this argument stays unused.
    """
    validate_table(df)
    results: list[P3Result] = []

    for (model, layer, statistic), cell in df.groupby(["model", "layer", "statistic"], sort=True):
        verified_z = subset(cell, "verified")["z"].to_numpy(dtype=float)
        if verified_z.size < 100:
            log.info("skipping P3 for %s/L%s/%s: too few verified steps", model, layer, statistic)
            continue
        n_refuted = int(cell[cell["outcome"] == "refuted"]["trace_id"].nunique())

        for q in thresholds_q:
            tau = (
                float(tau_override)
                if tau_override is not None
                else float(np.quantile(verified_z, 1.0 - q))
            )
            z_star, trace_ids = _overshoots(cell, tau)
            if z_star.size < min_over_tau:
                log.info(
                    "skipping P3 for %s/L%s/%s at q=%.0e: only %d traces exceed tau",
                    model,
                    layer,
                    statistic,
                    q,
                    z_star.size,
                )
                continue

            excess = z_star - tau
            fit = gpd_fit(excess, threshold=tau)
            # The GPD here is fitted to *all* the excesses, not to an upper order statistic, so
            # there is no tail fraction to hold fixed; `k = n - 1` keeps `group_bootstrap`'s
            # `k < n` guard satisfied while the estimator ignores `k` entirely.
            boot = group_bootstrap(
                excess,
                trace_ids,
                lambda y, _k: float(gpd_fit(y).gamma),
                k=max(excess.size - 1, 2),
                resamples=bootstrap_resamples,
                level=ci_level,
                seed=seed,
            )

            variants, theta = _overshoot_variants(cell, tau)
            u = np.sort(z_star / tau)[::-1]
            surv = np.arange(1, u.size + 1, dtype=float) / u.size
            pooled = (pooled_gamma or {}).get((str(model), _as_int(layer), str(statistic)))
            comparison: dict[str, Any] = {}
            if pooled is not None:
                comparison = {
                    "pooled_gamma": float(pooled),
                    "difference": float(fit.gamma - pooled),
                    "compatible": bool(boot.ci_low <= pooled <= boot.ci_high),
                }

            res = P3Result(
                model=str(model),
                layer=_as_int(layer),
                statistic=str(statistic),
                q=float(q),
                tau=tau,
                n_refuted=n_refuted,
                n_over_tau=int(z_star.size),
                gpd_shape=float(fit.gamma),
                gpd_scale=float(fit.sigma),
                shape_ci=(float(boot.ci_low), float(boot.ci_high)),
                median_overshoot=float(np.median(u)),
                theta=theta,
                variants=variants,
                frac_above={
                    "1.5": float(np.mean(u > 1.5)),
                    "2": float(np.mean(u > 2.0)),
                    "5": float(np.mean(u > 5.0)),
                },
                survival={"u": u.tolist(), "s": surv.tolist()},
                comparison=comparison,
            )
            results.append(res)
            log.info(
                "P3 %s/L%s/%s q=%.0e: tau=%.3f n=%d shape=%.3f [%.3f, %.3f] median u=%.3f",
                model,
                layer,
                statistic,
                q,
                tau,
                res.n_over_tau,
                res.gpd_shape,
                res.shape_ci[0],
                res.shape_ci[1],
                res.median_overshoot,
            )
    return results
