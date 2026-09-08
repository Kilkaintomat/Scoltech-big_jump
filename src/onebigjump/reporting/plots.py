"""Figures. Every one is drawn from a metrics file, never from numbers typed in by hand."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .style import DASHES, ESTIMATOR, GRID, INK, MUTED, apply_style, p_colour

__all__ = [
    "figure_grokking",
    "figure_hill_plots",
    "figure_length_law",
    "figure_one",
    "figure_overshoot",
    "figure_roc",
    "hill_plot_figure",
]


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


def figure_grokking(payload: dict[str, Any], out_dir: Path | str, *, seed: int = 0) -> list[Path]:
    """P4: the order parameter against training, next to accuracy and the progress measures.

    Three stacked panels sharing a log-scaled step axis, because everything interesting about
    grokking happens over two decades of training and a linear axis compresses it into the right
    edge. The grokking step is marked in all three, so whether `gamma_hat` moves *there* rather
    than somewhere else is a question the figure answers rather than invites.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_style()
    cps = payload["checkpoints"]
    step = np.array([c["step"] for c in cps], dtype=float)
    step_plot = np.maximum(step, 1.0)  # step 0 has no place on a log axis
    grok_at = payload.get("grokking_step")

    fig = plt.figure(figsize=(5.4, 7.6))
    gs = fig.add_gridspec(4, 1, height_ratios=[1.0, 1.0, 1.0, 1.15])
    ax_acc = fig.add_subplot(gs[0])
    ax_prog = fig.add_subplot(gs[1], sharex=ax_acc)
    ax_tail = fig.add_subplot(gs[2], sharex=ax_acc)
    ax_zoom = fig.add_subplot(gs[3])
    axes = [ax_acc, ax_prog, ax_tail]

    ax_acc.plot(step_plot, [c["train_acc"] for c in cps], color=INK, lw=1.3, label="train")
    ax_acc.plot(
        step_plot,
        [c["test_acc"] for c in cps],
        color=ESTIMATOR["hill"],
        lw=1.3,
        dashes=(4, 1.5),
        label="test",
    )
    ax_acc.set_ylabel("accuracy")
    ax_acc.set_ylim(-0.03, 1.03)
    ax_acc.set_title("(a) generalization", loc="left")
    ax_acc.legend(loc="center left")

    ax_prog.plot(
        step_plot,
        [c["restricted_loss"] for c in cps],
        color=ESTIMATOR["gpd"],
        lw=1.3,
        label="restricted loss",
    )
    ax_prog.plot(
        step_plot,
        [c["excluded_loss"] for c in cps],
        color=ESTIMATOR["moment"],
        lw=1.3,
        dashes=(3, 1.5),
        label="excluded loss",
    )
    ax_prog.set_yscale("log")
    # The restricted loss falls below 1e-6 once the circuit is exact; showing five further
    # decades of numerical noise would compress everything that happens before it.
    ax_prog.set_ylim(1e-4, None)
    ax_prog.set_ylabel("loss")
    ax_prog.set_title("(b) progress measures (Nanda et al.)", loc="left")
    ax_prog.legend(loc="center left")

    ax_tail.plot(
        step_plot,
        [c["hill"] for c in cps],
        color=ESTIMATOR["hill"],
        lw=1.3,
        label=r"Hill $\hat{\gamma}$",
    )
    ax_tail.plot(
        step_plot,
        [c["moment"] for c in cps],
        color=ESTIMATOR["moment"],
        lw=1.3,
        dashes=(3, 1.5),
        label="moment",
    )
    full = [(c["step"], c["full"]) for c in cps if c.get("full")]
    if full:
        xs = np.maximum(np.array([f[0] for f in full], dtype=float), 1.0)
        lo = [f[1]["bootstrap"]["hill"]["ci_low"] for f in full]
        hi = [f[1]["bootstrap"]["hill"]["ci_high"] for f in full]
        ax_tail.fill_between(
            xs, lo, hi, color=ESTIMATOR["hill"], alpha=0.18, lw=0, label="95% CI (full protocol)"
        )
    ax_tail.axhline(0.0, color=GRID, lw=0.8, zorder=0)
    ax_tail.set_ylabel(r"$\hat{\gamma}$   ($\xi = \max(\hat{\gamma}, 0)$)")
    ax_tail.set_title("(c) order parameter", loc="left")
    ax_tail.legend(loc="upper left")
    ax_tail.set_xlabel("training step (log)")
    # (a)-(c) share the log axis, so only the lowest of them carries tick labels.
    ax_acc.tick_params(labelbottom=False)
    ax_prog.tick_params(labelbottom=False)

    if grok_at:
        for ax in axes:
            ax.axvline(
                max(float(grok_at), 1.0), color=MUTED, dashes=DASHES["tolerance"], lw=0.9, zorder=0
            )
        ax_acc.annotate(
            f"grokking at step {grok_at}",
            xy=(max(float(grok_at), 1.0), 0.5),
            xytext=(-6, 0),
            textcoords="offset points",
            color=MUTED,
            fontsize=7,
            va="center",
            ha="right",
        )

    ax_tail.set_xscale("log")

    # --- (d) the transition on a linear axis -------------------------------------------------
    # A log axis over 40k steps compresses the transition into a sliver, and the transition is
    # where the whole question lives: whether gamma_hat turns at the same step as the progress
    # measures. So the last panel is that curve again, linear, over a window around the drop.
    analysis = payload.get("analysis") or {}
    drop_at = analysis.get("sharpest_drop_step")
    centre = float(drop_at or grok_at or step[-1])
    half = max(2000.0, 0.06 * float(step[-1]))
    window = (step >= centre - half) & (step <= centre + half)
    if int(window.sum()) >= 3:
        hill = np.array([c["hill"] for c in cps], dtype=float)
        ax_zoom.plot(step[window], hill[window], color=ESTIMATOR["hill"], lw=1.4)
        marks = [
            (analysis.get("restricted_turn_step"), "restricted loss turns", ESTIMATOR["gpd"]),
            (drop_at, r"$\hat{\gamma}$ falls", ESTIMATOR["hill"]),
            (grok_at, "test acc. crosses 0.9", MUTED),
        ]
        for i, (at, label, colour) in enumerate(marks):
            if at is None:
                continue
            x = float(at)
            ax_zoom.axvline(x, color=colour, dashes=DASHES["tolerance"], lw=1.0, zorder=0)
            ax_zoom.annotate(
                f"{label}\n{int(x)}",
                xy=(x, 1.0 - 0.30 * i),
                xycoords=("data", "axes fraction"),
                xytext=(4, -4),
                textcoords="offset points",
                color=colour,
                fontsize=6.5,
                va="top",
                ha="left",
            )
        ax_zoom.set_ylabel(r"$\hat{\gamma}$")
        ax_zoom.set_xlabel("training step")
        ax_zoom.set_title("(d) the transition, linear axis", loc="left")
        ax_zoom.margins(y=0.32)
    else:  # pragma: no cover - only for runs too short to have a transition
        ax_zoom.set_axis_off()

    paths = _save(fig, Path(out_dir), f"p4_grokking_seed{seed}")
    plt.close(fig)
    return paths


def figure_hill_plots(payload: dict[str, Any], out_dir: Path | str) -> list[Path]:
    """The full Hill and moment plots for every setting, with the selected `k` marked.

    Section 4 requires this alongside any point estimate, and it is what the identifiability
    criterion is read off: a plateau over a decade of `k` *together with* agreement of the
    estimators. Showing the curve makes the criterion checkable instead of asserted -- and it is
    where the difference between the two estimators is visible, since Hill cannot go below zero
    while the moment estimator can.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_style()
    settings = {float(s["p"]): s for s in payload["settings"]}
    rates = sorted(settings)
    positive = [p for p in rates if p > 0]

    fig, (ax_h, ax_m) = plt.subplots(1, 2, figsize=(7.2, 3.2), sharex=True)
    for p in rates:
        s = settings[p]
        hp = s["tail"].get("hill_plot") or {}
        if not hp.get("k"):
            continue
        colour = p_colour(p, positive)
        k = np.asarray(hp["k"], dtype=float)
        label = f"$p={p:.2f}$"
        ax_h.plot(k, hp["hill"], color=colour, lw=1.2, label=label)
        ax_m.plot(k, hp["moment"], color=colour, lw=1.2, label=label)
        if "ci_low" in hp:
            ax_h.fill_between(k, hp["ci_low"], hp["ci_high"], color=colour, alpha=0.15, lw=0)

        xi = s.get("xi_theory")
        if xi is not None and np.isfinite(xi):
            for ax in (ax_h, ax_m):
                ax.axhline(xi, color=colour, dashes=DASHES["theory"], lw=0.7, zorder=0)
        chosen = s["tail"].get("k")
        if chosen:
            for ax, series in ((ax_h, hp["hill"]), (ax_m, hp["moment"])):
                i = int(np.argmin(np.abs(k - float(chosen))))
                ax.plot([k[i]], [series[i]], marker="o", ms=4, color=colour, zorder=3)

    for ax, name in ((ax_h, r"Hill $\hat{\gamma}^H_k$"), (ax_m, r"moment $\hat{\gamma}^M_k$")):
        ax.set_xscale("log")
        ax.set_xlabel("$k$ (upper order statistics)")
        ax.set_ylabel(name)
        ax.axhline(0.0, color=GRID, lw=0.8, zorder=0)
    ax_h.set_title("(a) Hill plot; dashed: closed form; dot: selected $k$", loc="left")
    ax_m.set_title("(b) moment plot", loc="left")
    # Headroom first, then the legend into it. A figure-level legend below the panels lands on
    # the x-axis labels, and inside a panel without headroom it lands on the curves.
    lo, hi = ax_h.get_ylim()
    ax_h.set_ylim(lo, hi + 0.30 * (hi - lo))
    ax_h.legend(loc="upper left", ncol=3, fontsize=6.5, columnspacing=1.0, handlelength=1.4)

    paths = _save(fig, Path(out_dir), "hill_plots_kesten")
    plt.close(fig)
    return paths


def figure_overshoot(
    results: list[dict[str, Any]], out_dir: Path | str, stem: str = "p3_overshoot"
) -> list[Path]:
    """P3: the survival of `Z_{t*}/tau` on log-log axes, one panel per tolerance.

    Three curves per panel, not one, because they disagree and the disagreement is the finding:
    the unconditional overshoot is what Proposition 1 states, the trace maximum is what a
    cluster's largest step does, and the first exceedance is what P3 as written measures. Under
    clustering the last is attenuated, so the extremal index is printed next to them -- a small
    fitted shape is not evidence against `Hheur` unless `theta` is near 1.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_style()
    results = [r for r in results if r.get("survival", {}).get("u")]
    if not results:
        return []

    fig, axes = plt.subplots(1, len(results), figsize=(3.6 * len(results), 3.2), squeeze=False)
    for ax, res in zip(axes[0], results, strict=True):
        u = np.asarray(res["survival"]["u"], dtype=float)
        sv = np.asarray(res["survival"]["s"], dtype=float)
        ax.plot(
            u,
            sv,
            color=ESTIMATOR["hill"],
            lw=1.6,
            label=rf"first exceedance $Z_{{t^*}}$  $\hat\gamma$={res.get('gpd_shape', float('nan')):+.3f}",
        )

        shape = res.get("gpd_shape")
        if shape is not None and np.isfinite(shape) and shape > 0:
            uu = np.geomspace(1.0, max(float(u.max()), 2.0), 60)
            ax.plot(
                uu,
                uu ** (-1.0 / shape),
                color=INK,
                dashes=DASHES["asymptote"],
                lw=0.9,
                label=rf"Pareto $u^{{-1/\hat\gamma}}$, $\hat\gamma={shape:.3f}$",
            )

        # All three survival curves, so the attenuation of the first-exceedance variant under
        # clustering is visible rather than asserted.
        for name, colour, dash in (
            ("unconditional", ESTIMATOR["gpd"], (4, 1.5)),
            ("trace_max", ESTIMATOR["moment"], (2, 1.5)),
        ):
            v = res.get("variants", {}).get(name) or {}
            curve = v.get("survival") or {}
            if not curve.get("u"):
                continue
            ax.plot(
                curve["u"],
                curve["s"],
                color=colour,
                lw=1.2,
                dashes=dash,
                label=f"{v['label'].split('(')[0].strip()}  $\\hat\\gamma$={v['shape']:+.3f}",
            )

        theta = res.get("theta")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(r"overshoot $u = Z_{t^*}/\tau$")
        ax.set_ylabel(r"$\mathbb{P}(Z_{t^*}/\tau > u)$")
        ax.set_title(
            f"$q={res['q']:.0e}$, $n={res['n_over_tau']}$"
            + (f", $\\theta={theta:.2f}$" if theta is not None and np.isfinite(theta) else ""),
            loc="left",
        )
        ax.legend(loc="lower left", fontsize=6)

    paths = _save(fig, Path(out_dir), stem)
    plt.close(fig)
    return paths


def figure_length_law(
    result: dict[str, Any], out_dir: Path | str, stem: str = "p5_length_law"
) -> list[Path]:
    """P5: chain accuracy against length, with the fitted law and its residuals.

    Corollary 3's point is not that accuracy decays exponentially -- it does so under both
    hypotheses -- so the panel that matters is the residual one: whether the *shape* of the decay
    is the one the law predicts, or whether a free per-length model would do better.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_style()
    observed = result.get("observed") or []
    if len(observed) < 3:
        return []
    lengths = np.array([o["L"] for o in observed], dtype=float)
    acc = np.array([o["accuracy"] for o in observed], dtype=float)
    n = np.array([o["n"] for o in observed], dtype=float)
    rate = float(result.get("rate_per_step", result.get("fit", {}).get("rate_per_step", 0.0)))
    predicted = np.exp(-rate * lengths)
    # Binomial standard error, so a residual can be read against what the counts can resolve.
    se = np.sqrt(np.clip(acc * (1 - acc), 0, None) / np.maximum(n, 1))

    fig, (ax, ax_r) = plt.subplots(
        2, 1, figsize=(4.4, 4.2), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]}
    )
    ax.errorbar(
        lengths,
        acc,
        yerr=se,
        fmt="o",
        ms=4,
        color=ESTIMATOR["hill"],
        lw=1,
        capsize=2,
        label="observed",
    )
    grid = np.linspace(lengths.min(), lengths.max(), 100)
    ax.plot(
        grid,
        np.exp(-rate * grid),
        color=INK,
        dashes=DASHES["theory"],
        lw=1.2,
        label=rf"$\exp(-\theta L \bar F(\tau))$, $c={rate:.4f}$",
    )
    ax.set_ylabel(r"$\mathbb{P}(V_L = 1)$")
    ax.set_title("(a) chain accuracy against length", loc="left")
    ax.legend(loc="lower left")

    ax_r.axhline(0.0, color=GRID, lw=0.8)
    ax_r.errorbar(
        lengths, acc - predicted, yerr=se, fmt="o", ms=4, color=ESTIMATOR["moment"], lw=1, capsize=2
    )
    ax_r.set_xlabel("chain length $L$")
    ax_r.set_ylabel("observed - fitted")
    p = result.get("p_value", result.get("fit", {}).get("p_value"))
    df = result.get("df", result.get("fit", {}).get("df"))
    ax_r.set_title(
        "(b) residuals"
        + (
            f"; LR test against a free per-length model: $p={p:.3f}$ ($df={df}$)"
            if p is not None
            else ""
        ),
        loc="left",
    )

    paths = _save(fig, Path(out_dir), stem)
    plt.close(fig)
    return paths


def figure_roc(results: list[Any], out_dir: Path | str, stem: str = "p2_roc") -> list[Path]:
    """P2: the jump statistic as a per-step detector of the first rejection.

    The surprisal baseline is on the same axes because that is the comparison that decides
    whether the residual stream says anything the output distribution did not already say.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_style()
    rows = [r if isinstance(r, dict) else r.as_dict() for r in results]
    rows = [r for r in rows if (r.get("roc") or {}).get("curve")]
    if not rows:
        return []

    fig, ax = plt.subplots(figsize=(3.8, 3.6))
    palette = [*ESTIMATOR.values(), INK, MUTED]
    for i, row in enumerate(rows):
        colour = palette[i % len(palette)]
        curve = row["roc"]["curve"]
        label = f"{row['model']} $Z^{{{row['statistic']}}}$, $\\ell={row['layer']}$"
        ax.plot(
            curve["fpr"],
            curve["tpr"],
            color=colour,
            lw=1.4,
            label=f"{label}  AUC {row['roc']['auc']:.3f}",
        )
        base = (row.get("roc_surprisal") or {}).get("curve")
        if base:
            ax.plot(
                base["fpr"],
                base["tpr"],
                color=colour,
                lw=1.0,
                dashes=(3, 1.5),
                label=f"    surprisal  AUC {row['roc_surprisal']['auc']:.3f}",
            )

    ax.plot([0, 1], [0, 1], color=GRID, lw=0.9, zorder=0, label="chance")
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_title("(a) jump size as a per-step detector of $t^*$", loc="left")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right", fontsize=6)

    paths = _save(fig, Path(out_dir), stem)
    plt.close(fig)
    return paths
