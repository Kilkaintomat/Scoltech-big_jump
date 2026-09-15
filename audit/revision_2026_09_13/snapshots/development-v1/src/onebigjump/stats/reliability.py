"""Split-half reliability of the order parameter.

A bootstrap confidence interval answers "how much would this estimate move if I resampled the
traces I have?". It cannot answer "would I have got the same number from a different half of the
data?", because every replicate is drawn from the same pooled sample and inherits whatever is
peculiar to it. The two come apart exactly where it matters: a `k` chosen to fit one half's
particular upper order statistics gives a narrow interval around a number the other half does not
reproduce.

So the traces are split in half at random, `xi` is estimated independently on each side --
including a fresh choice of `k`, since selecting it once on the pooled data and reusing it is the
leak this is meant to detect -- and the two are compared. Repeating over many random splits gives
the distribution of that disagreement.

Two numbers come out.

`delta`, the median absolute difference between halves, is in the units of `xi` itself and is
what to quote beside an effect: a separation between verified and refuted proofs smaller than the
disagreement between two halves of the same data is not a finding.

`reliability` is the Spearman correlation between the halves across splits, computed over cells
when there is more than one -- layers, statistics, subsets. It asks whether the *ordering* the
paper reads off survives resampling, which is the claim the ablation tables actually make. With a
single cell there is nothing to correlate and it is None rather than a fabricated 1.0.

The split is by **trace**, never by step. Steps within a trace are dependent by construction --
that is the whole premise of the paper -- so a step-level split puts neighbours on both sides and
reports a reliability that measures nothing but that dependence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..config import TailEstimationConfig
from .estimators import estimate_tail

__all__ = ["SplitHalfResult", "split_half_reliability", "split_half_table"]


@dataclass
class SplitHalfResult:
    """The disagreement between independent halves of the same sample."""

    n_splits: int
    n_usable: int
    n_traces: int
    xi_full: float
    delta_median: float
    delta_iqr: tuple[float, float]
    delta_p90: float
    xi_left: list[float] = field(default_factory=list)
    xi_right: list[float] = field(default_factory=list)
    reliability: float | None = None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_splits": self.n_splits,
            "n_usable": self.n_usable,
            "n_traces": self.n_traces,
            "xi_full": self.xi_full,
            "delta_median": self.delta_median,
            "delta_iqr": list(self.delta_iqr),
            "delta_p90": self.delta_p90,
            "xi_left": self.xi_left,
            "xi_right": self.xi_right,
            "reliability": self.reliability,
            "note": self.note,
        }

    def row(self) -> dict[str, Any]:
        """One line of the reliability table."""
        return {
            "n_traces": self.n_traces,
            "xi": self.xi_full,
            "delta_median": self.delta_median,
            "delta_p90": self.delta_p90,
            "reliability": self.reliability,
            "n_usable_splits": self.n_usable,
        }

    def resolves(self, effect: float) -> bool:
        """Is an effect of this size larger than the disagreement between halves?

        The comparison a reader makes anyway, made explicit. `delta_p90` rather than the median,
        because a separation that survives a typical split but not an unlucky one is not something
        to build a claim on.
        """
        return bool(np.isfinite(self.delta_p90) and abs(effect) > self.delta_p90)


def _xi_on(
    x: np.ndarray,
    g: np.ndarray,
    keep: np.ndarray,
    cfg: TailEstimationConfig,
    seed: int,
) -> float:
    """`xi` for one half, with `k` selected on that half alone.

    Selecting `k` on the pooled sample and reusing it on both halves would hide precisely the
    instability this is measuring, so `estimate_tail` is called afresh. A half too small to
    estimate at all returns NaN rather than raising: with few traces some splits are simply
    uninformative, and dropping those is honest as long as the count is reported.
    """
    try:
        return float(
            estimate_tail(
                x[keep],
                g[keep],
                cfg,
                seed=seed,
                with_hill_plot=False,
                with_k_stability=False,
            ).xi
        )
    except (ValueError, FloatingPointError):
        return float("nan")


def split_half_reliability(
    z: np.ndarray,
    groups: Sequence[Any] | np.ndarray,
    cfg: TailEstimationConfig | None = None,
    *,
    n_splits: int = 50,
    seed: int = 0,
) -> SplitHalfResult:
    """Estimate `xi` on independent random halves of the traces, `n_splits` times.

    `groups` is the trace id. It is required, not optional: a split that is not by trace measures
    the dependence between neighbouring steps rather than the stability of the estimate.
    """
    cfg = cfg or TailEstimationConfig()
    x: np.ndarray = np.asarray(z, dtype=np.float64).ravel()
    g: np.ndarray = np.asarray(groups).ravel()
    if g.size != x.size:
        raise ValueError(f"groups has length {g.size}, expected {x.size}")

    finite = np.isfinite(x) & (x > 0)
    x, g = x[finite], g[finite]

    uniq = np.unique(g)
    n_traces = int(uniq.size)
    if n_traces < 4:
        return SplitHalfResult(
            n_splits=0,
            n_usable=0,
            n_traces=n_traces,
            xi_full=float("nan"),
            delta_median=float("nan"),
            delta_iqr=(float("nan"), float("nan")),
            delta_p90=float("nan"),
            note=(
                f"{n_traces} traces cannot be split in half and estimated on both sides; "
                "reliability is not defined here"
            ),
        )

    try:
        xi_full = float(
            estimate_tail(x, g, cfg, seed=seed, with_hill_plot=False, with_k_stability=False).xi
        )
    except (ValueError, FloatingPointError):
        xi_full = float("nan")

    rng = np.random.default_rng(seed)
    left: list[float] = []
    right: list[float] = []
    for i in range(n_splits):
        order = rng.permutation(n_traces)
        cut = n_traces // 2
        in_left = np.isin(g, uniq[order[:cut]])
        a = _xi_on(x, g, in_left, cfg, seed + i)
        b = _xi_on(x, g, ~in_left, cfg, seed + n_splits + i)
        left.append(a)
        right.append(b)

    la, ra = np.asarray(left), np.asarray(right)
    ok = np.isfinite(la) & np.isfinite(ra)
    d = np.abs(la[ok] - ra[ok])
    if d.size == 0:
        return SplitHalfResult(
            n_splits=n_splits,
            n_usable=0,
            n_traces=n_traces,
            xi_full=xi_full,
            delta_median=float("nan"),
            delta_iqr=(float("nan"), float("nan")),
            delta_p90=float("nan"),
            xi_left=left,
            xi_right=right,
            note="no split produced an estimate on both halves; the sample is too small",
        )

    # Across splits, left and right are exchangeable by construction, so a correlation between
    # them is a statement about the halves rather than about any ordering the paper claims. That
    # is what `split_half_table` computes across cells; here it stays None.
    return SplitHalfResult(
        n_splits=n_splits,
        n_usable=int(d.size),
        n_traces=n_traces,
        xi_full=xi_full,
        delta_median=float(np.median(d)),
        delta_iqr=(float(np.percentile(d, 25)), float(np.percentile(d, 75))),
        delta_p90=float(np.percentile(d, 90)),
        xi_left=left,
        xi_right=right,
        note=""
        if d.size == n_splits
        else f"{n_splits - d.size} of {n_splits} splits were unusable",
    )


def split_half_table(
    cells: dict[str, tuple[np.ndarray, Sequence[Any] | np.ndarray]],
    cfg: TailEstimationConfig | None = None,
    *,
    n_splits: int = 50,
    seed: int = 0,
) -> dict[str, Any]:
    """Reliability for several cells, plus whether their *ordering* survives a split.

    The ablation tables do not claim each cell's value; they claim the ranking across cells -- this
    layer is heavier-tailed than that one, refuted heavier than verified. So the number that
    matters is whether the ranking computed on one half reproduces on the other. That is a Spearman
    correlation across cells, averaged over splits, and it needs at least three cells to mean
    anything.
    """
    from scipy.stats import spearmanr

    per_cell = {
        name: split_half_reliability(z, g, cfg, n_splits=n_splits, seed=seed)
        for name, (z, g) in cells.items()
    }

    names = list(per_cell)
    rhos: list[float] = []
    if len(names) >= 3:
        for s in range(n_splits):
            a = np.array([per_cell[n].xi_left[s] for n in names if s < len(per_cell[n].xi_left)])
            b = np.array([per_cell[n].xi_right[s] for n in names if s < len(per_cell[n].xi_right)])
            if a.size != len(names) or b.size != len(names):
                continue
            ok = np.isfinite(a) & np.isfinite(b)
            # A constant vector makes the correlation undefined, and scipy returns NaN with a
            # warning rather than raising; skip those splits rather than average NaN in.
            if ok.sum() >= 3 and np.ptp(a[ok]) > 0 and np.ptp(b[ok]) > 0:
                rho = float(spearmanr(a[ok], b[ok]).statistic)
                if np.isfinite(rho):
                    rhos.append(rho)

    reliability = float(np.median(rhos)) if rhos else None
    for r in per_cell.values():
        r.reliability = reliability

    return {
        "cells": {name: r.as_dict() for name, r in per_cell.items()},
        "rows": {name: r.row() for name, r in per_cell.items()},
        "ordering_reliability": reliability,
        "n_ordering_splits": len(rhos),
        "note": (
            ""
            if reliability is not None
            else f"ordering reliability needs at least 3 cells; got {len(names)}"
        ),
    }
