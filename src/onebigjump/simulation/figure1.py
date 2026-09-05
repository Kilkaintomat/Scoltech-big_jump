"""Reproduce Figure 1 of the paper: the dichotomy on the heuristic-mixture model.

Figure 1 is the one place where the paper states a complete numeric result rather than a
placeholder, so it is the calibration target for everything downstream: if the estimators of
`onebigjump.stats` cannot recover `xi(p)` here, where the answer is known in closed form, no
estimate on real traces is worth reading.

The caption fixes the setting: `rho = 0.7`, `kappa = 2.5`, `d = 8`, 3000 traces of 64 steps per
value of `p`, tolerance `tau` at the 99.9% quantile, and closed-form indices
`alpha = 3.97, 2.80, 1.82` at `p = 0.02, 0.05, 0.10`.

`tau` is taken per setting, as the caption's own counts require: at the 99.9% quantile a setting
contributes about 192 exceedances, and the number of *traces* carrying one is 185 at `p = 0`
(exceedances isolated) against 114 at `p = 0.05` (exceedances clustered, several to a trace).
A single shared `tau` cannot produce both, and the ratio is the extremal index at work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..config import KestenConfig
from ..logging import get_logger
from ..manifests import run_manifest
from ..reproducibility import write_json
from ..stats import estimate_tail, extremal_index
from .kesten import KestenTraces, alpha_two_heuristics, p_critical, simulate, xi_two_heuristics

__all__ = ["SettingResult", "analyse_setting", "run_figure_one"]

log = get_logger(__name__)


@dataclass
class SettingResult:
    """Everything Figure 1 needs about one off-support rate `p`."""

    p: float
    alpha_theory: float
    xi_theory: float
    tau: float
    n_refuted: int
    n_traces: int
    n_steps: int
    top1: float
    top3: float
    chance: float
    theta: float
    tail: dict[str, Any]
    overshoot: dict[str, Any]
    survival: dict[str, list[float]]
    exemplar_trace: list[float]
    exemplar_t_star: int

    def as_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        return d


def _localization(traces: KestenTraces, tau: float) -> dict[str, Any]:
    """Theorem 4(ii): among refuted traces, is `T^max` the first exceedance `t*`?"""
    t_star = traces.first_exceedance(tau)
    refuted = t_star >= 0
    n_ref = int(refuted.sum())
    if n_ref == 0:
        return {"n_refuted": 0, "top1": float("nan"), "top3": float("nan"), "chance": float("nan")}

    z_ref = traces.z[refuted]
    ts = t_star[refuted]
    t_max = z_ref.argmax(axis=1)
    rows = np.arange(n_ref)
    # Rank of t* among the trace's deviations, 1 = largest.
    ranks = 1 + (z_ref > z_ref[rows, ts][:, None]).sum(axis=1)
    return {
        "n_refuted": n_ref,
        "top1": float(np.mean(t_max == ts)),
        "top3": float(np.mean(ranks <= 3)),
        "chance": float(1.0 / traces.n_steps),  # E[1/L] with L fixed
        "mean_rank": float(ranks.mean()),
    }


def _overshoot(traces: KestenTraces, tau: float) -> dict[str, Any]:
    """Proposition 1: the survival of `Z_{t*}/tau`, Pareto under `Hheur`, degenerate under `Halg`."""
    t_star = traces.first_exceedance(tau)
    refuted = t_star >= 0
    if not refuted.any():
        return {"n": 0}
    z_star = traces.z[refuted, t_star[refuted]]
    u = np.sort(z_star / tau)[::-1]
    surv = np.arange(1, u.size + 1, dtype=np.float64) / u.size

    out: dict[str, Any] = {
        "n": int(u.size),
        "u": u.tolist(),
        "survival": surv.tolist(),
        "median": float(np.median(u)),
        "q90": float(np.quantile(u, 0.9)),
        "frac_above_1_5": float(np.mean(u > 1.5)),
        "frac_above_2": float(np.mean(u > 2.0)),
    }
    if u.size >= 20:
        from ..stats import gpd_fit

        fit = gpd_fit(z_star[z_star > tau] - tau, threshold=tau)
        out["gpd_shape"] = fit.gamma
        out["gpd_scale"] = fit.sigma
    return out


def analyse_setting(
    p: float, cfg: KestenConfig, *, bootstrap_hill_plot: int = 0
) -> tuple[SettingResult, KestenTraces]:
    """Simulate one `p` and compute every quantity the four panels display."""
    tr = simulate(p, cfg)
    z, groups = tr.pooled()
    tau = tr.tolerance(cfg.tolerance_quantile)

    est = estimate_tail(
        z,
        groups,
        cfg.tail,
        seed=cfg.seed,
        with_hill_plot=True,
        hill_plot_resamples=bootstrap_hill_plot,
        meta={"p": p, "rho": cfg.rho, "kappa": cfg.kappa},
    )
    loc = _localization(tr, tau)
    over = _overshoot(tr, tau)
    theta = extremal_index([tr.z[i] for i in range(tr.n_traces)], threshold=tau).theta

    # Thin the survival curve for plotting: keep the whole tail, thin the bulk.
    order = np.sort(z)[::-1]
    surv = np.arange(1, order.size + 1, dtype=np.float64) / order.size
    keep = np.unique(
        np.concatenate(
            [
                np.arange(min(2000, order.size)),
                np.geomspace(2000, order.size - 1, 800).astype(np.int64),
            ]
        )
    )
    keep = keep[keep < order.size]

    # Exemplar for panel (a): a refuted trace whose first exceedance is not at the very edge.
    t_star = tr.first_exceedance(tau)
    refuted = np.flatnonzero(t_star >= 0)
    if refuted.size:
        mid = refuted[np.argmin(np.abs(t_star[refuted] - tr.n_steps // 2))]
        exemplar, t_ex = tr.z[mid], int(t_star[mid])
    else:
        exemplar, t_ex = tr.z[int(tr.z.max(axis=1).argmax())], -1

    result = SettingResult(
        p=float(p),
        alpha_theory=tr.alpha_theory,
        xi_theory=tr.xi_theory,
        tau=float(tau),
        n_refuted=int(loc["n_refuted"]),
        n_traces=tr.n_traces,
        n_steps=tr.n_steps,
        top1=float(loc["top1"]),
        top3=float(loc["top3"]),
        chance=float(loc["chance"]),
        theta=float(theta),
        tail=est.as_dict(),
        overshoot=over,
        survival={"z": order[keep].tolist(), "s": surv[keep].tolist()},
        exemplar_trace=exemplar.tolist(),
        exemplar_t_star=t_ex,
    )
    return result, tr


def run_figure_one(
    cfg: KestenConfig | None = None,
    *,
    out_dir: Path | str | None = None,
    figure_dir: Path | str = "paper_outputs/figures",
    metrics_dir: Path | str = "paper_outputs/metrics",
    bootstrap_hill_plot: int = 0,
    make_figure: bool = True,
) -> dict[str, Any]:
    """Run every `p`, write the metrics, and draw the figure."""
    cfg = cfg or KestenConfig()
    out = Path(out_dir or cfg.out_dir)

    with run_manifest(
        "figure1-kesten", "kesten", out, config=cfg.model_dump(mode="json"), seed=cfg.seed
    ) as man:
        results: list[SettingResult] = []
        for p in cfg.p_values:
            log.info("simulating heuristic-mixture model at p=%.3f", p)
            res, _ = analyse_setting(p, cfg, bootstrap_hill_plot=bootstrap_hill_plot)
            results.append(res)
            log.info(
                "  p=%.3f  xi_theory=%.4f  hill=%.4f  moment=%.4f  refuted=%d  top1=%.3f",
                p,
                res.xi_theory,
                res.tail["hill"],
                res.tail["moment"],
                res.n_refuted,
                res.top1,
            )

        payload: dict[str, Any] = {
            "caption_setting": {
                "rho": cfg.rho,
                "kappa": cfg.kappa,
                "d": cfg.d,
                "n_traces": cfg.n_traces,
                "n_steps": cfg.n_steps,
                "tolerance_quantile": cfg.tolerance_quantile,
                "p_critical": p_critical(cfg.rho, cfg.kappa),
            },
            "closed_form": {
                f"{p:.2f}": {
                    "alpha": alpha_two_heuristics(p, cfg.rho, cfg.kappa),
                    "xi": xi_two_heuristics(p, cfg.rho, cfg.kappa),
                }
                for p in cfg.p_values
            },
            "settings": [r.as_dict() for r in results],
        }
        metrics_path = write_json(out / "figure1_metrics.json", payload)
        man.add_output(metrics_path, "metrics")

        summary = _summary_table(results)
        summary_path = out / "figure1_summary.csv"
        summary_path.write_text(summary, encoding="utf-8")
        man.add_output(summary_path, "table")

        pm = Path(metrics_dir)
        pm.mkdir(parents=True, exist_ok=True)
        man.add_output(write_json(pm / "figure1.json", payload), "metrics")

        for r in results:
            man.add_metric(f"xi_theory_p{r.p:.2f}", r.xi_theory)
            man.add_metric(f"hill_p{r.p:.2f}", r.tail["hill"])
            man.add_metric(f"moment_p{r.p:.2f}", r.tail["moment"])

        if make_figure:
            from ..reporting.plots import figure_hill_plots, figure_one

            for fp in figure_one(payload, Path(figure_dir)):
                man.add_output(fp, "figure")
            # Section 4 requires the full Hill plot alongside any point estimate, and it is what
            # the identifiability criterion is read off; it is not an optional appendix figure.
            for fp in figure_hill_plots(payload, Path(figure_dir)):
                man.add_output(fp, "figure")

        return payload


def _summary_table(results: list[SettingResult]) -> str:
    """CSV mirroring the numbers the caption of Figure 1 states."""
    header = (
        "p,alpha_theory,xi_theory,hill,hill_lo,hill_hi,moment,moment_lo,moment_hi,"
        "gpd,k,tau,n_refuted,top1,top3,chance,theta,overshoot_gpd_shape\n"
    )
    rows = []
    for r in results:
        b = r.tail["bootstrap"]
        rows.append(
            f"{r.p:.4f},{r.alpha_theory:.4f},{r.xi_theory:.4f},"
            f"{r.tail['hill']:.4f},{b['hill']['ci_low']:.4f},{b['hill']['ci_high']:.4f},"
            f"{r.tail['moment']:.4f},{b['moment']['ci_low']:.4f},{b['moment']['ci_high']:.4f},"
            f"{r.tail['gpd']:.4f},{r.tail['k']},{r.tau:.4f},{r.n_refuted},"
            f"{r.top1:.4f},{r.top3:.4f},{r.chance:.4f},{r.theta:.4f},"
            f"{r.overshoot.get('gpd_shape', float('nan')):.4f}"
        )
    return header + "\n".join(rows) + "\n"
