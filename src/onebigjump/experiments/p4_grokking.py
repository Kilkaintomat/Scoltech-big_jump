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

__all__ = ["Checkpoint", "run_p4", "train_grokking"]

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

    def row(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k not in {"full", "key_frequencies"}}


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
    data = make_data(p=cfg.p, train_frac=cfg.train_frac, seed=seed)
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


def run_p4(
    cfg: GrokkingConfig | None = None,
    *,
    out_dir: Path | str | None = None,
    seed: int = 0,
    full_every: int = 20,
    make_figure: bool = True,
    figure_dir: Path | str = "paper_outputs/figures",
    metrics_dir: Path | str = "paper_outputs/metrics",
) -> dict[str, Any]:
    """Train, measure, and write the P4 record and figure."""
    cfg = cfg or GrokkingConfig()
    out = Path(out_dir or cfg.out_dir)

    with run_manifest(
        f"p4-grokking-seed{seed}",
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

        payload = {
            "config": cfg.model_dump(mode="json"),
            "seed": seed,
            "meta": meta,
            "grokking_step": grok_at,
            "memorisation_step": memorised_at,
            "checkpoints": [c.__dict__ for c in checkpoints],
        }
        man.add_output(write_json(out / f"p4_grokking_seed{seed}.json", payload), "metrics")

        header = ",".join(checkpoints[0].row().keys())
        body = "\n".join(
            ",".join(f"{v:.6g}" if isinstance(v, float) else str(v) for v in c.row().values())
            for c in checkpoints
        )
        csv_path = out / f"p4_grokking_seed{seed}.csv"
        csv_path.write_text(header + "\n" + body + "\n", encoding="utf-8")
        man.add_output(csv_path, "table")

        pm = Path(metrics_dir)
        pm.mkdir(parents=True, exist_ok=True)
        man.add_output(write_json(pm / f"p4_grokking_seed{seed}.json", payload), "metrics")

        man.add_metric("grokking_step", grok_at)
        man.add_metric("memorisation_step", memorised_at)
        man.add_metric("final_test_acc", checkpoints[-1].test_acc)
        man.add_metric("hill_first", checkpoints[0].hill)
        man.add_metric("hill_last", checkpoints[-1].hill)
        man.note(
            f"gamma_hat is a fixed-fraction point estimate (k = {meta['tail_k_frac']:.0%} of n) "
            f"at every checkpoint; the full Section 4 protocol with intervals runs every "
            f"{full_every} checkpoints."
        )

        if make_figure:
            from ..reporting.plots import figure_grokking

            for path in figure_grokking(payload, Path(figure_dir), seed=seed):
                man.add_output(path, "figure")

        log.info(
            "P4 done: grokking at step %s, hill %.4f -> %.4f, %.0fs",
            grok_at,
            checkpoints[0].hill,
            checkpoints[-1].hill,
            meta["wall_time_s"],
        )
        return payload
