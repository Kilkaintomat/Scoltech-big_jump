"""Teacher-forced extraction of residual-stream trajectories, and the three deviation statistics.

Section 2 and Appendix B.1. The pipeline for one trace is:

1. re-run the sampled proof through the model with teacher forcing, in a single forward pass,
   which reproduces the states that produced the sample (the model is causal);
2. read the block output at the last prompt token (`X_0`) and at the last token of each step;
3. collect the token log-probabilities in the same pass, for the P2 surprisal baseline;
4. form the increments `xi_t = X_t - X_{t-1}` and reduce them to the three statistics of
   equation 1.

The whitening and innovation parameters are **fitted on verified traces of a disjoint problem
split** and then applied unchanged. Fitting them on the traces they are applied to would leak the
label into the statistic: the whitening would learn the covariance of the refuted traces too, and
the tail separation of P1 would be partly an artefact of the fit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..logging import get_logger
from ..reproducibility import write_json
from .hooks import layer_indices, record_residuals
from .token_alignment import TokenAlignment

__all__ = [
    "Calibration",
    "Trajectory",
    "deviations",
    "extract_trajectory",
    "fit_calibration",
    "ledoit_wolf_intensity",
    "shrinkage_target",
]

log = get_logger(__name__)

STATISTICS = ("raw", "whitened", "innovation")


@dataclass
class Trajectory:
    """One trace's residual-stream trajectory at one layer, plus its per-step surprisal."""

    trace_id: str
    layer: int
    states: np.ndarray  # (L+1, d): X_0 .. X_L
    surprisal: np.ndarray  # (L,): mean negative token log-probability of each step
    n_steps: int
    d_model: int
    meta: dict[str, Any] = field(default_factory=dict)

    def increments(self) -> np.ndarray:
        """`xi_t = X_t - X_{t-1}`, one row per step."""
        return np.diff(self.states, axis=0)


@dataclass
class Calibration:
    """Whitening and innovation parameters, fitted once on a disjoint verified split."""

    layer: int
    mean: np.ndarray  # mu
    whitener: np.ndarray  # Sigma^{-1/2}
    ridge_a: np.ndarray  # A_hat
    ridge_c: np.ndarray  # c_hat
    n_increments: int
    shrinkage: float
    ridge_alpha: float
    source: str = ""
    target: str = "diagonal"

    def whiten(self, increments: np.ndarray) -> np.ndarray:
        return (increments - self.mean) @ self.whitener.T

    def innovate(self, states: np.ndarray) -> np.ndarray:
        """`X_t - A_hat X_{t-1} - c_hat` for every step."""
        return states[1:] - states[:-1] @ self.ridge_a.T - self.ridge_c

    def save(self, path: Path | str) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            p,
            layer=self.layer,
            mean=self.mean,
            whitener=self.whitener,
            ridge_a=self.ridge_a,
            ridge_c=self.ridge_c,
            n_increments=self.n_increments,
            shrinkage=self.shrinkage,
            ridge_alpha=self.ridge_alpha,
            source=self.source,
            target=self.target,
        )
        return p

    @classmethod
    def load(cls, path: Path | str) -> Calibration:
        z = np.load(Path(path), allow_pickle=False)
        return cls(
            layer=int(z["layer"]),
            mean=z["mean"],
            whitener=z["whitener"],
            ridge_a=z["ridge_a"],
            ridge_c=z["ridge_c"],
            n_increments=int(z["n_increments"]),
            shrinkage=float(z["shrinkage"]),
            ridge_alpha=float(z["ridge_alpha"]),
            source=str(z["source"]),
            target=str(z["target"]) if "target" in z else "diagonal",
        )

    @property
    def increments_per_dim(self) -> float:
        """How well determined the whitening is. Below ~2 the whitened norms lose their spread."""
        return float(self.n_increments) / float(self.mean.size)

    def summary(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "d_model": int(self.mean.size),
            "n_increments": self.n_increments,
            "increments_per_dim": self.increments_per_dim,
            "shrinkage": self.shrinkage,
            "shrinkage_target": self.target,
            "ridge_alpha": self.ridge_alpha,
            "source": self.source,
            "mean_norm": float(np.linalg.norm(self.mean)),
            "whitener_logdet": _safe_logdet(self.whitener),
        }


def _safe_logdet(matrix: np.ndarray) -> float | None:
    """`log|M|`, or None when it under/overflows -- a diagnostic must not crash a run."""
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        value = float(np.linalg.slogdet(matrix)[1])
    return value if np.isfinite(value) else None


def _inverse_sqrt(cov: np.ndarray) -> np.ndarray:
    """`Sigma^{-1/2}` by symmetric eigendecomposition, with a floor on the eigenvalues.

    Residual-stream increment covariances are near-singular: a few massive-activation directions
    carry most of the variance and the rest is numerically flat. Inverting without a floor turns
    that flat subspace into enormous whitened norms, which is precisely the artefact whitening is
    supposed to remove.
    """
    vals, vecs = np.linalg.eigh((cov + cov.T) / 2.0)
    floor = max(float(vals.max()) * 1e-10, 1e-12)
    vals = np.maximum(vals, floor)
    return (vecs / np.sqrt(vals)) @ vecs.T


def shrinkage_target(cov: np.ndarray, target: str) -> np.ndarray:
    """The matrix the sample covariance is shrunk towards.

    `identity` is the classical Ledoit-Wolf target `tr(S)/d * I`. `diagonal` keeps each
    coordinate's own variance and shrinks only the correlations.

    The default is `diagonal`, because of what a residual stream looks like. A few
    massive-activation coordinates (Sun et al., 2024) carry variance thousands of times larger
    than the rest, so `tr(S)/d` sits far above the variance of every ordinary coordinate and even
    a tiny intensity inflates them. Measured on increments with a 2500:1 anisotropy, an intensity
    of 0.0011 towards the identity left the whitened covariance at 0.81 instead of 1. Whitening
    is here precisely to remove those directions, so the target must not reintroduce them.
    """
    d = cov.shape[0]
    if target == "identity":
        return float(np.trace(cov) / d) * np.eye(d)
    if target == "diagonal":
        return np.diag(np.diag(cov))
    raise ValueError(f"unknown shrinkage target: {target!r}")


def ledoit_wolf_intensity(centred: np.ndarray, cov: np.ndarray, target: str = "diagonal") -> float:
    """Ledoit-Wolf optimal shrinkage intensity towards `target`.

    "Shrinkage covariance" in the paper is left unspecified; this is the estimator the phrase
    normally names, and unlike a hand-picked intensity it adapts to how badly the sample is
    under-determined -- exactly the regime a residual stream puts us in.
    """
    n, _ = centred.shape
    t = shrinkage_target(cov, target)
    delta = float(np.sum((cov - t) ** 2))
    if delta <= 0:
        return 1.0
    # Sum over entries of the per-observation variance of the sample covariance.
    sq = centred**2
    beta_bar = (float(np.sum(sq.T @ sq)) / n - float(np.sum(cov**2))) / n
    return float(np.clip(max(beta_bar, 0.0) / delta, 0.0, 1.0))


def fit_calibration(
    trajectories: list[Trajectory],
    *,
    shrinkage: float | None = None,
    ridge_alpha: float = 1.0,
    source: str = "",
    min_increments_per_dim: float = 2.0,
    allow_underdetermined: bool = False,
    target: str = "diagonal",
) -> Calibration:
    """Fit `(mu, Sigma)` and `(A_hat, c_hat)` on the increments of verified traces.

    `Sigma` is shrunk towards `target` (see `shrinkage_target`), `(1-s) S + s T`. With
    `shrinkage=None` the intensity is the Ledoit-Wolf optimum; a float pins it instead.

    **The guard is not incidental.** With fewer increments than dimensions the sample covariance
    is singular, the shrinkage term dominates, and `Sigma^{-1/2}` becomes a near-multiple of the
    identity divided by a constant -- so every whitened norm comes out nearly equal. Measured on
    GPT-2 with 12 increments in 768 dimensions, the whitened deviations were 3.249, 3.249, 3.267,
    3.269, ... : a statistic with no variance left to have a tail. That silently flattens P1
    rather than failing, so an under-determined fit raises unless explicitly allowed. A residual
    stream of width `d` needs on the order of `2d` increments, which at ~10 steps per trace means
    hundreds of traces in the calibration split.
    """
    if not trajectories:
        raise ValueError("no trajectories to calibrate on")
    layer = trajectories[0].layer
    if any(t.layer != layer for t in trajectories):
        raise ValueError("all trajectories must come from the same layer")

    increments = np.concatenate([t.increments() for t in trajectories], axis=0)
    prev = np.concatenate([t.states[:-1] for t in trajectories], axis=0)
    nxt = np.concatenate([t.states[1:] for t in trajectories], axis=0)
    n, d = increments.shape
    if n < 2:
        raise ValueError(f"need at least 2 increments to calibrate, got {n}")
    if n < min_increments_per_dim * d and not allow_underdetermined:
        raise ValueError(
            f"under-determined whitening: {n} increments in {d} dimensions "
            f"({n / d:.2f} per dimension, want >= {min_increments_per_dim}). "
            "The shrinkage term would dominate and every whitened norm would come out nearly "
            "equal, flattening the tail P1 is about. Use a larger calibration split, or pass "
            "allow_underdetermined=True if you are deliberately testing that regime."
        )

    mu = increments.mean(axis=0)
    centred = increments - mu
    cov = centred.T @ centred / max(n - 1, 1)
    s = (
        ledoit_wolf_intensity(centred, cov, target)
        if shrinkage is None
        else float(np.clip(shrinkage, 0.0, 1.0))
    )
    cov = (1.0 - s) * cov + s * shrinkage_target(cov, target)
    whitener = _inverse_sqrt(cov)

    # Ridge regression of X_t on X_{t-1} with an intercept, fitted in one solve.
    x_mean = prev.mean(axis=0)
    y_mean = nxt.mean(axis=0)
    xc = prev - x_mean
    yc = nxt - y_mean
    gram = xc.T @ xc + float(ridge_alpha) * np.eye(d)
    a_hat = np.linalg.solve(gram, xc.T @ yc).T
    c_hat = y_mean - a_hat @ x_mean

    return Calibration(
        layer=layer,
        mean=mu,
        whitener=whitener,
        ridge_a=a_hat,
        ridge_c=c_hat,
        n_increments=int(n),
        shrinkage=s,
        ridge_alpha=float(ridge_alpha),
        source=source,
        target=target,
    )


def deviations(
    trajectory: Trajectory, calibration: Calibration | None = None
) -> dict[str, np.ndarray]:
    """The three statistics of equation 1 for one trajectory.

    `raw` is always available. `whitened` and `innovation` need a calibration fitted elsewhere;
    without one they are omitted rather than silently computed from the trace itself.
    """
    xi = trajectory.increments()
    out = {"raw": np.linalg.norm(xi, axis=1)}
    if calibration is not None:
        if calibration.layer != trajectory.layer:
            raise ValueError(
                f"calibration is for layer {calibration.layer}, trajectory for {trajectory.layer}"
            )
        out["whitened"] = np.linalg.norm(calibration.whiten(xi), axis=1)
        out["innovation"] = np.linalg.norm(calibration.innovate(trajectory.states), axis=1)
    return out


def extract_trajectory(
    model: Any,
    tokenizer: Any,
    text: str,
    alignment: TokenAlignment,
    *,
    trace_id: str,
    layers: list[int] | None = None,
    layer_fractions: tuple[float, ...] = (0.25, 0.5, 0.75),
    device: str | None = None,
) -> dict[int, Trajectory]:
    """Teacher-force `text` through `model` and read the trajectory at each requested layer.

    One forward pass produces every layer's states and the token log-probabilities together, as
    Appendix B.1 specifies; running separate passes would double the cost and, with sampling
    disabled but dropout defaults unverified, risk two different sets of activations.
    """
    import torch

    n_layers = len(list(_blocks(model)))
    chosen = layers if layers is not None else layer_indices(n_layers, layer_fractions)
    positions = alignment.readout_positions

    enc = tokenizer(text, return_tensors="pt", add_special_tokens=True)
    input_ids = enc["input_ids"]
    if input_ids.shape[1] != alignment.n_tokens:
        raise ValueError(
            f"tokenisation changed between alignment ({alignment.n_tokens} tokens) and "
            f"extraction ({input_ids.shape[1]} tokens)"
        )
    dev = device or str(next(model.parameters()).device)
    input_ids = input_ids.to(dev)

    with torch.no_grad(), record_residuals(model, chosen, positions) as rec:
        out = model(input_ids=input_ids)
        logits = out.logits[0].to(torch.float32)

    # Token log-probability of each *realised* token, shifted by one as usual.
    log_probs = torch.log_softmax(logits[:-1], dim=-1)
    realised = input_ids[0, 1:]
    token_lp = log_probs.gather(1, realised.unsqueeze(1)).squeeze(1).cpu().numpy()

    surprisal = _step_surprisal(token_lp, alignment)
    captures = rec.result()
    trajectories: dict[int, Trajectory] = {}
    for layer, cap in captures.items():
        states = cap.states.numpy().astype(np.float64)
        trajectories[layer] = Trajectory(
            trace_id=trace_id,
            layer=layer,
            states=states,
            surprisal=surprisal,
            n_steps=states.shape[0] - 1,
            d_model=states.shape[1],
            meta={"n_tokens": alignment.n_tokens, "unaligned_steps": alignment.unaligned},
        )
    return trajectories


def _step_surprisal(token_lp: np.ndarray, alignment: TokenAlignment) -> np.ndarray:
    """Mean negative log-probability of the tokens of each step (the P2 baseline scorer)."""
    out = np.full(len(alignment.step_token_spans), np.nan)
    for i, (lo, hi) in enumerate(alignment.step_token_spans):
        # token_lp[j-1] is the log-probability of token j, so shift the span by one.
        a, b = max(lo - 1, 0), min(hi, token_lp.size)
        if b > a:
            out[i] = -float(np.mean(token_lp[a:b]))
    return out


def _blocks(model: Any) -> Any:
    from .hooks import block_modules

    return block_modules(model)


def save_calibrations(calibrations: dict[int, Calibration], out_dir: Path | str) -> list[Path]:
    """Persist one calibration per layer, plus a human-readable summary."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = [c.save(out / f"calibration_layer{layer:03d}.npz") for layer, c in calibrations.items()]
    paths.append(
        write_json(
            out / "calibration_summary.json", {str(k): v.summary() for k, v in calibrations.items()}
        )
    )
    return paths
