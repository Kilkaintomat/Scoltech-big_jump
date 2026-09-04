"""Extremal index `theta` of the step-deviation process.

`theta` is the parameter of Corollary 3, `P(M_L <= u) ~ exp(-theta L Fbar(u))`, and hence of
prediction P5. It is `1` when large steps do not cluster and `< 1` when they do; Theorem 5
predicts clustering, because a jump is followed by a geometric relaxation.

Traces are independent, so every estimator here works *within* a trace and pools across traces.
Three estimators are provided because they fail in different ways at short trace lengths:

* `intervals` -- Ferro & Segers (2003), the default: threshold-based, no block length to choose;
* `blocks`    -- the ratio of blocks containing an exceedance to the number of exceedances;
* `runs`      -- the fraction of exceedances not followed by another within `run_length` steps.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

__all__ = ["ExtremalIndexEstimate", "extremal_index", "traces_from_groups"]

Method = Literal["intervals", "blocks", "runs"]


@dataclass
class ExtremalIndexEstimate:
    theta: float
    method: str
    threshold: float
    n_exceedances: int
    n_traces: int
    detail: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "theta": self.theta,
            "method": self.method,
            "threshold": self.threshold,
            "n_exceedances": self.n_exceedances,
            "n_traces": self.n_traces,
            "detail": self.detail,
        }


def traces_from_groups(
    z: np.ndarray,
    groups: Sequence[Any] | np.ndarray,
    order: Sequence[int] | np.ndarray | None = None,
) -> list[np.ndarray]:
    """Split a pooled deviation column back into per-trace series, preserving step order."""
    z = np.asarray(z, dtype=np.float64).ravel()
    g = np.asarray(groups).ravel()
    if g.size != z.size:
        raise ValueError("z and groups must have the same length")
    o = np.arange(z.size) if order is None else np.asarray(order).ravel()
    if o.size != z.size:
        raise ValueError("order must have the same length as z")
    uniq, inverse = np.unique(g, return_inverse=True)
    out: list[np.ndarray] = []
    for i in range(uniq.size):
        m = inverse == i
        seg = z[m]
        out.append(seg[np.argsort(o[m], kind="stable")])
    return out


def _intervals_estimator(traces: Iterable[np.ndarray], u: float) -> tuple[float, dict[str, Any]]:
    """Ferro & Segers (2003), pooling interexceedance times over independent traces."""
    gaps: list[np.ndarray] = []
    n_exc = 0
    for tr in traces:
        idx = np.flatnonzero(tr > u)
        n_exc += idx.size
        if idx.size >= 2:
            gaps.append(np.diff(idx).astype(np.float64))
    if not gaps:
        return float("nan"), {"n_gaps": 0}
    s = np.concatenate(gaps)
    n_gaps = s.size
    if s.max() <= 2.0:
        num = 2.0 * s.sum() ** 2
        den = n_gaps * np.sum(s * s)
        form = "s_max<=2"
    else:
        num = 2.0 * np.sum(s - 1.0) ** 2
        den = n_gaps * np.sum((s - 1.0) * (s - 2.0))
        form = "s_max>2"
    theta = float("nan") if den <= 0 else float(min(1.0, num / den))
    return theta, {"n_gaps": int(n_gaps), "formula": form, "mean_gap": float(s.mean())}


def _blocks_estimator(
    traces: Iterable[np.ndarray], u: float, block: int
) -> tuple[float, dict[str, Any]]:
    n_blocks_exc = 0
    n_exc = 0
    n_blocks = 0
    for tr in traces:
        exc = tr > u
        n_exc += int(exc.sum())
        for start in range(0, tr.size, block):
            chunk = exc[start : start + block]
            if chunk.size == 0:
                continue
            n_blocks += 1
            n_blocks_exc += int(chunk.any())
    if n_exc == 0:
        return float("nan"), {"n_blocks": n_blocks}
    return float(min(1.0, n_blocks_exc / n_exc)), {
        "n_blocks": int(n_blocks),
        "n_blocks_with_exceedance": int(n_blocks_exc),
        "block": int(block),
    }


def _runs_estimator(
    traces: Iterable[np.ndarray], u: float, run_length: int
) -> tuple[float, dict[str, Any]]:
    n_exc = 0
    n_isolated = 0
    for tr in traces:
        idx = np.flatnonzero(tr > u)
        n_exc += idx.size
        for i, t in enumerate(idx):
            nxt = idx[i + 1] if i + 1 < idx.size else None
            if nxt is None or nxt - t > run_length:
                n_isolated += 1
    if n_exc == 0:
        return float("nan"), {}
    return float(min(1.0, n_isolated / n_exc)), {
        "run_length": int(run_length),
        "n_isolated": int(n_isolated),
    }


def extremal_index(
    traces: Sequence[np.ndarray],
    *,
    threshold: float | None = None,
    quantile: float = 0.99,
    method: Method = "intervals",
    block: int | None = None,
    run_length: int = 3,
) -> ExtremalIndexEstimate:
    """Estimate `theta` at a threshold given directly or as a pooled quantile.

    `run_length` defaults to 3, the relaxation window Theorem 4's discussion derives for
    `rho = 0.7`, `kappa = 2.5`.
    """
    series = [np.asarray(t, dtype=np.float64).ravel() for t in traces if np.size(t) > 0]
    if not series:
        raise ValueError("no non-empty traces")
    pooled = np.concatenate(series)
    u = float(np.quantile(pooled, quantile)) if threshold is None else float(threshold)
    n_exc = int(np.sum(pooled > u))

    if method == "intervals":
        theta, detail = _intervals_estimator(series, u)
    elif method == "blocks":
        b = (
            int(block)
            if block
            else max(2, round(float(np.sqrt(np.mean([t.size for t in series])))))
        )
        theta, detail = _blocks_estimator(series, u, b)
    elif method == "runs":
        theta, detail = _runs_estimator(series, u, int(run_length))
    else:  # pragma: no cover
        raise ValueError(f"unknown method: {method}")

    detail["quantile"] = float(quantile)
    return ExtremalIndexEstimate(
        theta=theta,
        method=method,
        threshold=u,
        n_exceedances=n_exc,
        n_traces=len(series),
        detail=detail,
    )
