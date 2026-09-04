"""Figures. Every one is drawn from a metrics file, never from numbers typed in by hand."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .style import DASHES, ESTIMATOR, GRID, INK, MUTED, apply_style, p_colour

__all__ = ["figure_one", "hill_plot_figure"]


def _save(fig: Any, out_dir: Path, stem: str) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "png"):
        p = out_dir / f"{stem}.{ext}"
        fig.savefig(p)
        paths.append(p)
    return paths


def figure_one(payload: dict[str, Any], out_dir: Path | str) -> list[Path]:
    """The four panels of Figure 1, drawn from `figure1_metrics.json`.

    (a) one trace per regime; (b) survival of `Z_t` with the closed-form slopes;
    (c) the order parameter against `p`; (d) the overshoot at the failing step.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_style()
    settings = {float(s["p"]): s for s in payload["settings"]}
    rates = sorted(settings)
    positive = [p for p in rates if p > 0]
    setting = payload["caption_setting"]
    p_focus = min(positive, key=lambda p: abs(p - 0.05)) if positive else None

    fig, axes = plt.subplots(2, 2, figsize=(7.0, 5.2))
    ax_a, ax_b, ax_c, ax_d = axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]

    # --- (a) one trace per regime -------------------------------------------------------
    for p in [r for r in (0.0, p_focus) if r is not None and r in settings]:
        s = settings[p]
        trace = np.asarray(s["exemplar_trace"])
        ax_a.plot(
            np.arange(trace.size),
            trace,
            color=p_colour(p, positive),
            dashes=DASHES["solid"] if p > 0 else (2, 1),
            lw=1.1,
            label="algorithmic ($p=0$)" if p == 0 else f"heuristic mixture ($p={p:g}$)",
        )
    if p_focus is not None:
        tau = settings[p_focus]["tau"]
        ax_a.axhline(tau, color=MUTED, dashes=DASHES["tolerance"], lw=0.9)
        ax_a.annotate(
            r"$\tau$",
            xy=(0.985, tau),
            xycoords=("axes fraction", "data"),
            va="bottom",
            ha="right",
            color=MUTED,
            fontsize=7.5,
        )
    ax_a.set_yscale("log")
    ax_a.set_xlabel("reasoning step $t$")
    ax_a.set_ylabel("step deviation $Z_t$")
    ax_a.set_title("(a) one trace per regime", loc="left")
    ax_a.legend(loc="upper left")

    # --- (b) survival of Z_t ------------------------------------------------------------
    for p in rates:
        s = settings[p]
        z = np.asarray(s["survival"]["z"])
        sv = np.asarray(s["survival"]["s"])
        # alpha is infinite at p = 0 (no root of E a^alpha = 1 exists), which the strict JSON
        # writer stores as null: there is no power-law slope to draw, and that is the point.
        alpha = s["alpha_theory"]
        finite_alpha = alpha is not None and np.isfinite(alpha) and alpha > 0
        label = "$p=0$ (algorithmic)" if not finite_alpha else rf"$p={p:.2f}$, $\alpha={alpha:.2f}$"
        ax_b.plot(z, sv, color=p_colour(p, positive), lw=1.2, label=label)
        if finite_alpha:
            # Anchor the closed-form slope on the empirical curve at the 1e-3 level.
            i = int(np.argmin(np.abs(sv - 1e-3)))
            zz = np.geomspace(z[i], z.max(), 40)
            ax_b.plot(
                zz,
                sv[i] * (zz / z[i]) ** (-alpha),
                color=p_colour(p, positive),
                dashes=DASHES["asymptote"],
                lw=0.9,
            )
    ax_b.set_xscale("log")
    ax_b.set_yscale("log")
    ax_b.set_xlabel("$z$")
    ax_b.set_ylabel(r"$\mathbb{P}(Z_t > z)$")
    ax_b.set_title(r"(b) survival of $Z_t$; dotted: slope $-\alpha$", loc="left")
    # Upper right is the empty corner of a survival plot; lower left is where the curves land.
    ax_b.legend(loc="upper right")

    # --- (c) the order parameter --------------------------------------------------------
    p_c = setting["p_critical"]
    from ..simulation.kesten import xi_two_heuristics

    grid = np.linspace(0.0, min(max(rates) * 1.05, p_c * 0.98), 200)
    theory = [xi_two_heuristics(float(p), setting["rho"], setting["kappa"]) for p in grid]
    ax_c.plot(
        grid,
        theory,
        color=INK,
        dashes=DASHES["theory"],
        lw=1.2,
        label=r"theory: root of $(1-p)\rho^\alpha + p\kappa^\alpha = 1$",
    )

    hill = np.array([settings[p]["tail"]["hill"] for p in rates])
    lo = np.array([settings[p]["tail"]["bootstrap"]["hill"]["ci_low"] for p in rates])
    hi = np.array([settings[p]["tail"]["bootstrap"]["hill"]["ci_high"] for p in rates])
    mom = np.array([settings[p]["tail"]["moment"] for p in rates])
    ax_c.fill_between(rates, lo, hi, color=ESTIMATOR["hill"], alpha=0.18, lw=0)
    ax_c.plot(
        rates,
        hill,
        color=ESTIMATOR["hill"],
        marker="o",
        ms=3.5,
        lw=1.2,
        label="Hill, trace-bootstrap 95% CI",
    )
    ax_c.plot(
        rates,
        mom,
        color=ESTIMATOR["moment"],
        marker="s",
        ms=3.5,
        lw=1.2,
        dashes=(3, 1.5),
        label="moment estimator (DEdH)",
    )
    ax_c.axhline(0.0, color=GRID, lw=0.8, zorder=0)
    ax_c.set_xlabel("off-support heuristic rate $p$")
    # The estimators return the extreme value index, which may be negative; the order parameter
    # is its positive part. Plotting the raw estimate keeps the sign visible -- a negative moment
    # estimate at p = 0 is the positive evidence for H_alg, and clipping it would hide that.
    ax_c.set_ylabel(r"$\hat{\gamma}$   ($\xi = \max(\hat{\gamma}, 0)$)")
    ax_c.set_title(r"(c) tail index as order parameter", loc="left")
    ax_c.legend(loc="upper left")

    # --- (d) overshoot at the failing step ----------------------------------------------
    for p in [r for r in (0.0, p_focus) if r is not None and r in settings]:
        s = settings[p]
        ov = s["overshoot"]
        if not ov.get("n"):
            continue
        u = np.asarray(ov["u"])
        sv = np.asarray(ov["survival"])
        label = (
            f"algorithmic ($p=0$)  ($n={ov['n']}$)"
            if p == 0
            else f"heuristic mixture ($p={p:g}$)  ($n={ov['n']}$)"
        )
        ax_d.plot(
            u,
            sv,
            color=p_colour(p, positive),
            lw=1.2,
            dashes=DASHES["solid"] if p > 0 else (2, 1),
            label=label,
        )
    if p_focus is not None:
        alpha = settings[p_focus]["alpha_theory"]
        uu = np.geomspace(1.0, 4.0, 50)
        ax_d.plot(
            uu,
            uu**-alpha,
            color=INK,
            dashes=DASHES["asymptote"],
            lw=0.9,
            label=rf"Pareto asymptote $u^{{-\alpha}}$, $\alpha={alpha:.2f}$",
        )
    ax_d.set_xscale("log")
    ax_d.set_yscale("log")
    ax_d.set_xlabel(r"overshoot $u = Z_{t^*}/\tau$ at the failing step")
    ax_d.set_ylabel(r"$\mathbb{P}(Z_{t^*}/\tau > u)$")
    ax_d.set_title("(d) catastrophe vs. marginal failure", loc="left")
    ax_d.legend(loc="lower left")

    fig.suptitle("", y=0.99)
    paths = _save(fig, Path(out_dir), "figure1_kesten_dichotomy")
    plt.close(fig)
    return paths


def hill_plot_figure(
    curves: dict[str, dict[str, Any]], out_dir: Path | str, stem: str, title: str = ""
) -> list[Path]:
    """Hill plots with trace-bootstrap bands, one line per subset.

    Section 4 requires the full curve `k -> gamma_hat_H(k)` to be shown alongside any point
    estimate, so this is not an optional appendix figure.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_style()
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    palette = [*ESTIMATOR.values(), INK, MUTED]
    for i, (name, hp) in enumerate(curves.items()):
        colour = palette[i % len(palette)]
        k = np.asarray(hp["k"])
        ax.plot(k, hp["hill"], color=colour, lw=1.2, label=name)
        if "ci_low" in hp:
            ax.fill_between(k, hp["ci_low"], hp["ci_high"], color=colour, alpha=0.16, lw=0)
    ax.set_xscale("log")
    ax.set_xlabel("$k$ (upper order statistics)")
    ax.set_ylabel(r"$\hat{\gamma}^H_k$")
    if title:
        ax.set_title(title, loc="left")
    ax.legend(loc="best")
    paths = _save(fig, Path(out_dir), stem)
    plt.close(fig)
    return paths
