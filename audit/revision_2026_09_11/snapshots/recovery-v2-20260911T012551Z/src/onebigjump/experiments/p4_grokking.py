"""P4: does the tail lighten when a circuit forms?

    For a model that acquires a circuit during training, gamma_hat drops abruptly at the
    transition, coinciding with the progress measures of Nanda et al. and the generalization
    jump of Wang et al. (Theorem 5(iv)).

The observable is the depth-wise step deviation of Appendix B.1: for the one-layer model the
deviation is the block output, `||h^(1) - h^(0)||`, pooled over all `p^2` inputs at each
checkpoint. That gives one deviation per input, so the inputs *are* the sampling units -- there
is no within-trace dependence here, and the cluster variance of Theorem 6 is 1 by construction.

Running the full Section 4 protocol at every one of 400 checkpoints is not affordable: the double
bootstrap alone is 200 resamples, and the trace bootstrap another 500. The compromise, recorded
in the manifest rather than left implicit, is a fast point estimate at every checkpoint and the
full protocol with intervals every `full_every` checkpoints.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..config import GrokkingConfig, TailEstimationConfig
from ..logging import get_logger
from ..manifests import run_manifest
from ..reproducibility import seed_everything, write_json
from ..stats import estimate_tail, hill, moment, sorted_positive_desc
from ..stats.gpd import gpd_from_order_statistics

__all__ = ["Checkpoint", "analyse_p4", "run_p4", "train_grokking"]

log = get_logger(__name__)


@dataclass
class Checkpoint:
    """One measurement point: losses, accuracies, progress measures and the tail index."""

    step: int
    train_loss: float
    test_loss: float
    train_acc: float
    test_acc: float
    restricted_loss: float
    excluded_loss: float
    hill: float
    moment: float
    gpd: float
    k: int
    n: int
    median_deviation: float
    key_frequencies: list[int] = field(default_factory=list)
    full: dict[str, Any] | None = None

    @property
    def gamma(self) -> float:
        """The signed EVT shape, which is what `gamma` means in the paper.

        Taken from the moment estimator, the same choice the Kesten analysis makes: Hill is a mean
        of log-ratios of upper order statistics and is non-negative by construction, so it cannot
        represent a light tail at all. Reading Hill as `gamma` -- which this module used to do --
        turns "the tail is light and stays light" into "the tail index is falling".
        """
        return self.moment

    @property
    def xi(self) -> float:
        """The order parameter, `xi = max(gamma, 0)`. Zero means no heavy tail."""
        return max(self.moment, 0.0)

    def row(self) -> dict[str, Any]:
        row = {k: v for k, v in self.__dict__.items() if k not in {"full", "key_frequencies"}}
        # Written out rather than derived by the reader, so a CSV cannot be misread the way the
        # JSON was: `gamma` is signed, `xi` is clipped, `hill` is neither.
        row["gamma"] = self.gamma
        row["xi"] = self.xi
        return row


def _device(name: str) -> str:
    import torch

    if name != "auto":
        return name
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _tail_fast(z: np.ndarray, k_frac: float = 0.05) -> tuple[float, float, float, int]:
    """Point estimates at a fixed tail fraction, for the per-checkpoint curve.

    A fixed fraction rather than a per-checkpoint double bootstrap: the quantity of interest is
    how `gamma_hat` *moves* across training, and re-selecting `k` at every checkpoint would mix
    genuine movement with movement of the threshold. The full protocol, with `k` selected
    properly and intervals attached, runs at a subset of checkpoints.
    """
    x = sorted_positive_desc(z)
    k = int(np.clip(round(k_frac * x.size), 20, x.size - 2))
    try:
        g = float(gpd_from_order_statistics(x, k).gamma)
    except (ValueError, FloatingPointError):  # pragma: no cover
        g = float("nan")
    return hill(x, k), moment(x, k), g, k


def train_grokking(
    cfg: GrokkingConfig,
    *,
    seed: int = 0,
    full_every: int = 20,
    tail_k_frac: float = 0.05,
    progress_top_k: int = 6,
) -> tuple[list[Checkpoint], dict[str, Any]]:
    """Train the modular-addition transformer and measure the tail at every checkpoint."""
    import torch

    from ..models.grokking import build_model, make_data

    seed_everything(seed)
    device = _device(cfg.device)
    data = make_data(
        p=cfg.p, train_frac=cfg.train_frac, seed=seed, shuffle_labels=cfg.shuffle_labels
    )
    model = build_model(
        p=cfg.p, d_model=cfg.d_model, n_heads=cfg.n_heads, d_mlp=cfg.d_mlp, seed=seed
    ).to(device)

    inputs = data.inputs.to(device)
    targets = data.targets.to(device)
    train_x = inputs[data.train_idx]
    train_y = targets[data.train_idx]

    opt = torch.optim.AdamW(
        model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay, betas=cfg.betas
    )
    tail_cfg = cfg.tail

    checkpoints: list[Checkpoint] = []
    t0 = time.time()
    for step in range(cfg.steps + 1):
        if step % cfg.checkpoint_every == 0:
            checkpoints.append(
                _measure(
                    model,
                    data,
                    inputs,
                    device,
                    step,
                    full_every=full_every,
                    index=len(checkpoints),
                    tail_cfg=tail_cfg,
                    tail_k_frac=tail_k_frac,
                    progress_top_k=progress_top_k,
                    seed=seed,
                )
            )
            c = checkpoints[-1]
            if len(checkpoints) % 10 == 1 or c.test_acc > 0.9:
                log.info(
                    "step %6d | train acc %.3f test acc %.3f | restricted %.3f excluded %.3f "
                    "| hill %.4f moment %+.4f | %.0fs",
                    step,
                    c.train_acc,
                    c.test_acc,
                    c.restricted_loss,
                    c.excluded_loss,
                    c.hill,
                    c.moment,
                    time.time() - t0,
                )
        if step == cfg.steps:
            break

        model.train()
        opt.zero_grad(set_to_none=True)
        loss = torch.nn.functional.cross_entropy(model(train_x), train_y)
        loss.backward()
        opt.step()

    meta = {
        "device": device,
        "n_train": len(data.train_idx),
        "n_test": len(data.test_idx),
        "n_params": int(sum(p.numel() for p in model.parameters())),
        "wall_time_s": round(time.time() - t0, 1),
        "full_every": full_every,
        "tail_k_frac": tail_k_frac,
        "progress_measure_protocol": "same-frequency Fourier terms; excluded loss on train; adaptive frequencies",
    }
    return checkpoints, meta


def _measure(
    model: Any,
    data: Any,
    inputs: Any,
    device: str,
    step: int,
    *,
    full_every: int,
    index: int,
    tail_cfg: TailEstimationConfig,
    tail_k_frac: float,
    progress_top_k: int,
    seed: int,
) -> Checkpoint:
    import torch

    from ..models.grokking import progress_measures

    model.eval()
    with torch.no_grad():
        increments = model.block_increment(inputs).float().cpu().numpy()
    z = np.linalg.norm(increments, axis=1)
    # Appendix B.1 normalises depth-wise deviations by the layer-wise median. With one block the
    # median is a single scale factor and the tail index is scale-invariant, so this changes no
    # reported index; it is applied for fidelity and to keep the scale comparable across steps.
    median = float(np.median(z))
    z_norm = z / median if median > 0 else z

    pm = progress_measures(model, data, top_k=progress_top_k, device=device)
    h, m, g, k = _tail_fast(z_norm, k_frac=tail_k_frac)

    full: dict[str, Any] | None = None
    if full_every > 0 and index % full_every == 0:
        # Each input contributes one deviation, so inputs are independent sampling units and the
        # bootstrap over them is the trace bootstrap of Section 4 with traces of length one.
        est = estimate_tail(
            z_norm,
            np.arange(z_norm.size),
            tail_cfg,
            seed=seed,
            with_hill_plot=False,
            meta={"step": step},
        )
        full = est.as_dict() | est.row()

    return Checkpoint(
        step=step,
        train_loss=pm.train_loss,
        test_loss=pm.test_loss,
        train_acc=pm.train_acc,
        test_acc=pm.test_acc,
        restricted_loss=pm.restricted_loss,
        excluded_loss=pm.excluded_loss,
        hill=h,
        moment=m,
        gpd=g,
        k=k,
        n=int(z_norm.size),
        median_deviation=median,
        key_frequencies=pm.key_frequencies,
        full=full,
    )


def grokking_step(checkpoints: list[Checkpoint], threshold: float = 0.9) -> int | None:
    """The first checkpoint at which test accuracy crosses `threshold`."""
    for c in checkpoints:
        if c.test_acc >= threshold:
            return c.step
    return None


def _turning_point(
    steps: np.ndarray,
    values: np.ndarray,
    *,
    rising: bool,
    after_step: float = -1.0,
    log_scale: bool = False,
) -> int | None:
    """The step at which a curve makes its sharpest move, by largest single-interval change.

    `after_step` exists because the largest *rise* in test accuracy is the memorisation jump in
    the first few hundred steps, not the grokking transition tens of thousands of steps later.
    Searching the whole curve returns the wrong one and makes the coincidence test meaningless.

    `log_scale` is needed for the progress-measure losses, which span six orders of magnitude. On
    a linear scale an early fall from 14 to 8 can outweigh the collapse at the transition, where
    the restricted loss drops from 1 to 1e-6; measured on one seed, the linear reading put the
    turn at step 1300 instead of 22800. A fractional change is the scale-appropriate one.
    """
    if steps.size < 3:
        return None
    if log_scale:
        values = np.log(np.maximum(values, 1e-12))
    delta = np.diff(values)
    mask = steps[1:] > after_step
    if not np.any(mask & np.isfinite(delta)):
        return None
    candidates = np.where(mask & np.isfinite(delta), delta, -np.inf if rising else np.inf)
    idx = int(np.argmax(candidates) if rising else np.argmin(candidates))
    return int(steps[idx + 1])


def _half_transition_step(
    steps: np.ndarray,
    values: np.ndarray,
    *,
    after_step: float = -1.0,
    log_scale: bool = False,
    tail_frac: float = 0.1,
) -> int | None:
    """The step at which a curve completes half of its transition.

    A crossing time, not a derivative. The progress measures make a *level shift* -- the
    restricted loss falls from about 10 to below 1e-6 -- and a derivative is the wrong instrument
    for one: on a linear scale an early fall from 14 to 8 outweighs the collapse, and on a log
    scale the post-collapse noise between 1e-6 and 1e-7 outweighs everything. Measured on two
    seeds, those two readings put the turn at step 1300 and at step 32400 respectively, when the
    transition is at 22800.

    The level before is the median over the window's first tenth, the level after its last
    `tail_frac`, and the answer is the first step that crosses the midpoint between them.
    """
    mask = steps > after_step
    if int(mask.sum()) < 5:
        return None
    s, v = steps[mask], values[mask]
    if log_scale:
        v = np.log(np.maximum(v, 1e-12))
    head = max(int(0.1 * v.size), 2)
    tail = max(int(tail_frac * v.size), 2)
    before, after = float(np.median(v[:head])), float(np.median(v[-tail:]))
    if not np.isfinite(before) or not np.isfinite(after) or before == after:
        return None
    mid = 0.5 * (before + after)
    crossed = v <= mid if after < before else v >= mid
    idx = np.flatnonzero(crossed)
    return int(s[idx[0]]) if idx.size else None


def analyse_p4(
    checkpoints: list[Checkpoint], *, window: int = 3, tol_steps: int = 300
) -> dict[str, Any]:
    """Locate the transition and say whether, and where, `gamma_hat` moves.

    The analysis plan requires the drop to be *located at* the transition, not merely to happen
    during training. But "the transition" has two readings, and P4 names both: the paper says the
    drop should coincide "with the mechanistic progress measures of Nanda et al. **and** the
    generalization jump". Those are not the same step, so coincidence is reported against each
    separately rather than collapsed into one boolean -- and the lag between them is itself a
    result, since a drop that leads generalization is evidence the order parameter tracks circuit
    formation rather than downstream accuracy.
    """
    steps = np.array([c.step for c in checkpoints], dtype=float)
    # `gamma` is the signed shape and `xi = max(gamma, 0)` is the order parameter. Hill is kept
    # only as a diagnostic: this analysis used to compute every field named `gamma_*` from Hill,
    # which is non-negative by construction, and so reported a falling "tail index" on runs whose
    # order parameter was identically zero throughout.
    hill = np.array([c.hill for c in checkpoints], dtype=float)
    gamma = np.array([c.gamma for c in checkpoints], dtype=float)
    xi = np.array([c.xi for c in checkpoints], dtype=float)
    train_acc = np.array([c.train_acc for c in checkpoints], dtype=float)
    grok = grokking_step(checkpoints)

    # Ignore the memorisation phase when looking for turns: it ends when train accuracy saturates.
    memorised = steps[train_acc >= 0.99]
    after = float(memorised[0]) if memorised.size else -1.0

    drop_step = _turning_point(steps, gamma, rising=False, after_step=after)
    # The reference curves make level shifts, so they are located by a crossing time. gamma_hat
    # does not: it rises to a transient peak and comes back to roughly where it started, so its
    # signature is the fall itself and it is located by the sharpest single-interval drop. Using
    # a crossing time for it would find nothing, and that difference is itself a result.
    restricted_turn = _half_transition_step(
        steps, np.array([c.restricted_loss for c in checkpoints]), after_step=after, log_scale=True
    )
    excluded_turn = _half_transition_step(
        steps, np.array([c.excluded_loss for c in checkpoints]), after_step=after, log_scale=True
    )
    acc_turn = _half_transition_step(
        steps, np.array([c.test_acc for c in checkpoints]), after_step=after
    )

    finite_xi = xi[np.isfinite(xi)]
    # Whether xi "moves" has to be judged against the estimator's own noise, not against zero.
    # The moment estimator on k upper order statistics has a standard error of order 1/sqrt(k),
    # so a gamma_hat within that of zero is indistinguishable from a light tail. Counting bare
    # sign changes instead would call a run with 1% of checkpoints at xi = 0.0006 "moving".
    k_arr = np.array([max(int(c.k), 1) for c in checkpoints], dtype=float)
    se = 1.0 / np.sqrt(k_arr)
    ok_xi = np.isfinite(xi)
    out: dict[str, Any] = {
        "grokking_step": grok,
        "memorisation_step": int(after) if after >= 0 else None,
        "gamma_first": float(gamma[0]),
        "gamma_last": float(gamma[-1]),
        "gamma_max": float(np.nanmax(gamma)),
        "gamma_argmax_step": int(steps[int(np.nanargmax(gamma))]),
        # The order parameter itself. `xi_positive_fraction` is the field to read first: if the
        # tail is light at almost every checkpoint then xi is pinned at zero, nothing about it can
        # move, and any curve that appears to move is a different statistic.
        "xi_mean": float(np.mean(finite_xi)) if finite_xi.size else float("nan"),
        "xi_max": float(np.nanmax(xi)),
        "xi_positive_fraction": float(np.mean(finite_xi > 0)) if finite_xi.size else float("nan"),
        "xi_exceeds_noise_fraction": float(np.mean(xi[ok_xi] > se[ok_xi])) if ok_xi.any() else 0.0,
        "xi_moves": bool(ok_xi.any() and float(np.mean(xi[ok_xi] > se[ok_xi])) >= 0.10),
        # Hill, labelled as Hill, so the diagnostic stays available without being mistaken for
        # the order parameter.
        "hill_first": float(hill[0]),
        "hill_last": float(hill[-1]),
        "hill_max": float(np.nanmax(hill)),
        "sharpest_drop_step": drop_step,
        "test_acc_turn_step": acc_turn,
        "restricted_turn_step": restricted_turn,
        "excluded_turn_step": excluded_turn,
    }

    def near(a: int | None, b: int | None) -> bool | None:
        return None if a is None or b is None else bool(abs(a - b) <= tol_steps)

    # Each reference separately. The two progress measures do not turn together: the excluded
    # loss shifts when the memorised solution is displaced, while the restricted loss collapses
    # over six orders of magnitude and its half-way point sits well down that collapse. Folding
    # them into one boolean would hide which of the two gamma_hat actually tracks.
    out["drop_coincides_with_excluded_loss"] = near(drop_step, excluded_turn)
    out["drop_coincides_with_restricted_loss"] = near(drop_step, restricted_turn)
    out["drop_coincides_with_progress_measures"] = bool(
        out["drop_coincides_with_excluded_loss"] or out["drop_coincides_with_restricted_loss"]
    )
    out["drop_coincides_with_generalization"] = near(drop_step, grok)
    if drop_step is not None and grok is not None:
        out["drop_leads_generalization_by"] = int(grok - drop_step)

    if grok is not None:
        i = int(np.argmin(np.abs(steps - grok)))
        lo = slice(max(i - window, 0), i)
        hi = slice(i + 1, min(i + 1 + window, gamma.size))
        before = float(np.nanmean(gamma[lo])) if gamma[lo].size else float("nan")
        after_g = float(np.nanmean(gamma[hi])) if gamma[hi].size else float("nan")
        out |= {
            "gamma_before_transition": before,
            "gamma_after_transition": after_g,
            "drop_at_transition": before - after_g,
            "drops_at_transition": bool(
                np.isfinite(before) and np.isfinite(after_g) and after_g < before
            ),
        }
    if drop_step is not None:
        j = int(np.argmin(np.abs(steps - drop_step)))
        pre = slice(max(j - window, 0), j)
        post = slice(j, min(j + window, gamma.size))
        out["gamma_peak_to_trough"] = (
            float(np.nanmax(gamma[pre])) - float(np.nanmin(gamma[post]))
            if gamma[pre].size and gamma[post].size
            else float("nan")
        )

    # The verdict, spelled out, because every number above can be computed on a run where the
    # order parameter never leaves zero -- and on this experiment it does not. A P4 result
    # requires xi itself to move; a moving Hill on a light tail is not evidence for the paper's
    # hypothesis, it is the absence of one.
    if not out["xi_moves"]:
        out["verdict"] = (
            f"xi exceeds the estimator's own noise at only "
            f"{out['xi_exceeds_noise_fraction']:.1%} of checkpoints (positive at all at "
            f"{out['xi_positive_fraction']:.1%}), so the order parameter is pinned at zero and P4 "
            "is untested on this run -- neither confirmed nor refuted. Any trend reported here is "
            "a trend in Hill, which is non-negative by construction and cannot represent a light "
            "tail. Read hill_* as a diagnostic only."
        )
    else:
        out["verdict"] = (
            f"xi exceeds the estimator's noise at {out['xi_exceeds_noise_fraction']:.1%} of "
            "checkpoints, so the location statistics above are interpretable."
        )
    return out


def run_p4(
    cfg: GrokkingConfig | None = None,
    *,
    out_dir: Path | str | None = None,
    seed: int = 0,
    full_every: int = 20,
    make_figure: bool = True,
    figure_dir: Path | str = "paper_outputs/figures",
    metrics_dir: Path | str = "paper_outputs/metrics",
    run_name: str | None = None,
) -> dict[str, Any]:
    """Train, measure, and write the P4 record and figure.

    `run_name` distinguishes runs that differ in something other than the seed -- a device, a
    control condition -- and it reaches the *published* filenames, not only the manifest. Keying
    `paper_outputs/` on the seed alone meant every P4 run overwrote every other one at the same
    seed: the shuffled-label null ended up occupying the published metrics and figures of the real
    experiment, under the real experiment's name.
    """
    cfg = cfg or GrokkingConfig()
    out = Path(out_dir or cfg.out_dir)
    # Default to the output directory's own name, which is what already distinguishes
    # results/full/grokking from grokking_cuda, grokking_cpu and grokking_null.
    tag = run_name or out.name
    stem = (
        f"p4_grokking_{tag}_seed{seed}"
        if tag not in {"", "grokking"}
        else (f"p4_grokking_seed{seed}")
    )

    with run_manifest(
        f"p4-grokking-{tag}-seed{seed}" if tag != "grokking" else f"p4-grokking-seed{seed}",
        "grokking",
        out,
        config=cfg.model_dump(mode="json"),
        seed=seed,
    ) as man:
        checkpoints, meta = train_grokking(cfg, seed=seed, full_every=full_every)
        grok_at = grokking_step(checkpoints)
        memorised_at = grokking_step(
            [Checkpoint(**{**c.__dict__, "test_acc": c.train_acc}) for c in checkpoints], 0.99
        )

        # The analysis has to be in the payload before it is written: the figure and the report
        # both read `analysis` out of the metrics file, and an earlier ordering left it absent
        # from the file while still recording it in the manifest.
        analysis = analyse_p4(checkpoints)
        payload = {
            "config": cfg.model_dump(mode="json"),
            "seed": seed,
            "meta": meta,
            "grokking_step": grok_at,
            "memorisation_step": memorised_at,
            "analysis": analysis,
            "checkpoints": [c.__dict__ for c in checkpoints],
        }
        man.add_output(write_json(out / f"{stem}.json", payload), "metrics")

        header = ",".join(checkpoints[0].row().keys())
        body = "\n".join(
            ",".join(f"{v:.6g}" if isinstance(v, float) else str(v) for v in c.row().values())
            for c in checkpoints
        )
        csv_path = out / f"{stem}.csv"
        csv_path.write_text(header + "\n" + body + "\n", encoding="utf-8")
        man.add_output(csv_path, "table")

        pm = Path(metrics_dir)
        pm.mkdir(parents=True, exist_ok=True)
        man.add_output(write_json(pm / f"{stem}.json", payload), "metrics")

        man.add_metric("grokking_step", grok_at)
        man.add_metric("memorisation_step", memorised_at)
        man.add_metric("final_test_acc", checkpoints[-1].test_acc)
        for key, value in analysis.items():
            man.add_metric(f"analysis_{key}", value)
        man.note(
            f"gamma_hat is a fixed-fraction point estimate (k = {meta['tail_k_frac']:.0%} of n) "
            f"at every checkpoint; the full Section 4 protocol with intervals runs every "
            f"{full_every} checkpoints."
        )

        if make_figure:
            from ..reporting.plots import figure_grokking

            for path in figure_grokking(payload, Path(figure_dir), seed=seed, stem=stem):
                man.add_output(path, "figure")

        log.info(
            "P4 done: grokking at step %s, hill %.4f -> %.4f, %.0fs",
            grok_at,
            checkpoints[0].hill,
            checkpoints[-1].hill,
            meta["wall_time_s"],
        )
        return payload
