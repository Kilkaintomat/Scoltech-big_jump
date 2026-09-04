"""One call that produces everything Table 1 of the paper needs from one pooled sample.

`estimate_tail` runs the whole Section 4 protocol: select `k`, evaluate the three estimators of
equation 3 at that `k`, attach trace-bootstrap intervals to each, estimate the cluster variance
of Theorem 6(ii), compare the GPD fit against its light-tailed alternatives, and record whether
the tail is identified in the paper's sense. Nothing downstream re-implements any of this.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..config import TailEstimationConfig
from .bootstrap import BootstrapResult, cluster_variance, effective_sample, group_bootstrap
from .diagnostics import hill_plot, identified_tail
from .gpd import compare_tail_models, gpd_from_order_statistics
from .hill import hill, sorted_positive_desc
from .moment import moment
from .thresholds import select_k

__all__ = ["TailEstimate", "estimate_tail", "xi_from_gamma"]


def xi_from_gamma(gamma: float) -> float:
    """The order parameter `xi = max(gamma, 0)`.

    Section 2 defines `xi = 1/alpha*` with `alpha* = sup{s : E Z^s < inf}`, and notes that
    `xi = max(gamma, 0)` whenever the extreme value index `gamma` is defined. A negative `gamma`
    means bounded support, which is still `xi = 0`: algorithmic.
    """
    if not np.isfinite(gamma):
        return float("nan")
    return float(max(gamma, 0.0))


@dataclass
class TailEstimate:
    """Everything about one (model, subset, layer, statistic) cell of Table 1."""

    n: int
    n_traces: int
    k: int
    k_selection: dict[str, Any]
    hill: float
    moment: float
    gpd: float
    xi: float
    boot: dict[str, dict[str, Any]] = field(default_factory=dict)
    cluster: dict[str, float] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)
    identification: dict[str, Any] = field(default_factory=dict)
    hill_plot: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "n_traces": self.n_traces,
            "k": self.k,
            "k_selection": self.k_selection,
            "hill": self.hill,
            "moment": self.moment,
            "gpd": self.gpd,
            "xi": self.xi,
            "bootstrap": self.boot,
            "cluster": self.cluster,
            "comparison": self.comparison,
            "identification": self.identification,
            "hill_plot": self.hill_plot,
            "meta": self.meta,
        }

    def row(self) -> dict[str, Any]:
        """The flat record that becomes one line of Table 1."""

        def ci(name: str) -> tuple[float, float]:
            b = self.boot.get(name, {})
            return b.get("ci_low", float("nan")), b.get("ci_high", float("nan"))

        h_lo, h_hi = ci("hill")
        m_lo, m_hi = ci("moment")
        g_lo, g_hi = ci("gpd")
        return {
            "m_traces": self.n_traces,
            "n_steps": self.n,
            "k": self.k,
            "hill": self.hill,
            "hill_lo": h_lo,
            "hill_hi": h_hi,
            "moment": self.moment,
            "moment_lo": m_lo,
            "moment_hi": m_hi,
            "gpd": self.gpd,
            "gpd_lo": g_lo,
            "gpd_hi": g_hi,
            "xi": self.xi,
            "sigma2_cl": self.cluster.get("sigma2_cl", float("nan")),
            "favours": self.comparison.get("favours", ""),
            "identified": self.identification.get("identified", False),
            **{f"meta_{k}": v for k, v in self.meta.items()},
        }


def _gpd_at(z: np.ndarray, k: int) -> float:
    return float(gpd_from_order_statistics(z, k).gamma)


def estimate_tail(
    z: np.ndarray,
    groups: Sequence[Any] | np.ndarray | None = None,
    cfg: TailEstimationConfig | None = None,
    *,
    seed: int = 0,
    with_hill_plot: bool = True,
    hill_plot_resamples: int = 0,
    meta: dict[str, Any] | None = None,
) -> TailEstimate:
    """Run the full Section 4 estimation protocol on one pooled sample.

    `groups` is the resampling unit -- the trace id, or the prompt id when several traces share
    a prompt. Passing `None` falls back to step-level resampling, which understates the variance
    by the cluster factor and is only ever appropriate for genuinely independent observations.
    """
    cfg = cfg or TailEstimationConfig()
    x = np.asarray(z, dtype=np.float64).ravel()
    finite = np.isfinite(x) & (x > 0)
    if groups is not None:
        g = np.asarray(groups).ravel()
        if g.size != x.size:
            raise ValueError(f"groups has length {g.size}, expected {x.size}")
        g = g[finite]
    else:
        g = None
    x = x[finite]

    n = x.size
    if n < 50:
        raise ValueError(f"too few positive deviations to estimate a tail: n={n}")

    sel = select_k(
        x,
        cfg.k_selector,
        k_min=cfg.k_min,
        k_max_frac=cfg.k_max_frac,
        fixed_frac=cfg.k_fixed_frac,
        resamples=cfg.double_bootstrap_resamples,
        n1_exponent=cfg.double_bootstrap_n1_exponent,
        seed=seed,
    )
    k = sel.k

    point = {
        "hill": hill(x, k),
        "moment": moment(x, k),
        "gpd": _gpd_at(x, k),
    }
    point = {name: v for name, v in point.items() if name in cfg.estimators}

    fns = {"hill": hill, "moment": moment, "gpd": _gpd_at}
    boot: dict[str, dict[str, Any]] = {}
    for name in point:
        res: BootstrapResult = group_bootstrap(
            x,
            g,
            fns[name],
            k=k,
            resamples=cfg.bootstrap_resamples,
            level=cfg.ci_level,
            unit=cfg.bootstrap_unit,
            seed=seed + 1,
        )
        boot[name] = res.as_dict()

    cluster: dict[str, float] = {}
    if g is not None:
        cluster = cluster_variance(x, g, k)
        cluster["effective_k"] = effective_sample(cluster.get("sigma2_cl", float("nan")), k)

    xs = sorted_positive_desc(x)
    comparison = compare_tail_models(xs[:k] - xs[k], threshold=float(xs[k])).as_dict()
    ident = identified_tail(x, point, k_min=cfg.k_min, k_max_frac=cfg.k_max_frac).as_dict()

    hp: dict[str, Any] = {}
    if with_hill_plot:
        hp = hill_plot(
            x,
            g,
            k_min=cfg.k_min,
            k_max_frac=max(cfg.k_max_frac, 0.5),
            resamples=hill_plot_resamples,
            level=cfg.ci_level,
            seed=seed + 2,
        )

    gamma_headline = point.get("hill", float("nan"))
    return TailEstimate(
        n=int(n),
        n_traces=int(np.unique(g).size) if g is not None else int(n),
        k=int(k),
        k_selection=sel.as_dict(),
        hill=float(point.get("hill", float("nan"))),
        moment=float(point.get("moment", float("nan"))),
        gpd=float(point.get("gpd", float("nan"))),
        xi=xi_from_gamma(point.get("moment", gamma_headline)),
        boot=boot,
        cluster=cluster,
        comparison=comparison,
        identification=ident,
        hill_plot=hp,
        meta=dict(meta or {}),
    )
