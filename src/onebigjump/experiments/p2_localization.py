"""P2: among refuted traces, the first rejected step is the largest jump.

Theorem 4(ii) predicts `P(T^max = t* | V_L = 0) -> 1` under extremal independence; Theorem 4(i)
says clustering lowers it to `pi_L(Theta)`. The test compares the realised rate against three
things, and all three are required before a hit rate means anything:

* **chance**, `E[1/L]` over the refuted traces (Theorem 4(iii)). Reporting a raw hit rate without
  it is meaningless, because a trace with four steps has a chance level of 0.25;
* **a permutation null**, shuffling step positions *within* each trace, which preserves both the
  distribution of deviations and the distribution of `L`;
* **the token-surprisal baseline**, the least likely step by mean token log-probability. This is
  the natural competitor: if surprisal localises the error just as well, the residual-stream jump
  is telling us nothing that the output distribution did not already say.

The jump statistic is also scored as a per-step detector (ROC), which is what makes it comparable
to the supervised hidden-state probes of the hallucination-detection literature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd

from ..logging import get_logger
from .dataset import validate_table

__all__ = ["P2Result", "localization_rates", "run_p2"]


def _as_int(value: Any) -> int:
    """Narrow a pandas groupby key to `int`; the stubs type these as bare `Hashable`."""
    return int(cast(int, value))


log = get_logger(__name__)


@dataclass
class P2Result:
    """One row of Table 2."""

    model: str
    layer: int
    statistic: str
    n_refuted: int
    top1: float
    top3: float
    chance: float
    mean_rank: float
    surprisal_top1: float | None
    surprisal_top3: float | None
    permutation: dict[str, Any] = field(default_factory=dict)
    roc: dict[str, Any] = field(default_factory=dict)
    by_length: list[dict[str, Any]] = field(default_factory=list)

    @property
    def lift(self) -> float:
        """How many times chance the top-1 rate is."""
        return float(self.top1 / self.chance) if self.chance > 0 else float("nan")

    def row(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "layer": self.layer,
            "statistic": self.statistic,
            "n_refuted": self.n_refuted,
            "top1": self.top1,
            "top3": self.top3,
            "chance": self.chance,
            "lift": self.lift,
            "surprisal_top1": self.surprisal_top1,
            "perm_mean": self.permutation.get("mean"),
            "perm_sd": self.permutation.get("sd"),
            "perm_p": self.permutation.get("p_value"),
            "auc": self.roc.get("auc"),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.row(),
            "mean_rank": self.mean_rank,
            "surprisal_top3": self.surprisal_top3,
            "permutation": self.permutation,
            "roc": self.roc,
            "by_length": self.by_length,
        }


def _per_trace(cell: pd.DataFrame) -> list[dict[str, Any]]:
    """One record per refuted trace: its deviations in step order, `t*`, and its surprisals."""
    refuted = cell[cell["outcome"] == "refuted"]
    out: list[dict[str, Any]] = []
    for trace_id, group in refuted.groupby("trace_id", sort=False):
        g = group.sort_values("t")
        t_star = g["t_star"].iloc[0]
        if pd.isna(t_star):
            continue
        z = g["z"].to_numpy(dtype=float)
        if z.size == 0 or not np.all(np.isfinite(z)):
            continue
        out.append(
            {
                "trace_id": trace_id,
                "z": z,
                "t_star": int(t_star),
                "L": int(z.size),
                "surprisal": g["surprisal"].to_numpy(dtype=float),
            }
        )
    return out


def _rank_of(values: np.ndarray, index: int) -> int:
    """Rank of `values[index]` among `values`, 1 = largest. Ties count against the target."""
    return int(1 + np.sum(values > values[index]))


def localization_rates(traces: list[dict[str, Any]], key: str = "z") -> dict[str, float]:
    """Top-1, top-3 and mean rank of `t*` under a given per-step score."""
    ranks = []
    for tr in traces:
        values = tr[key]
        if values.size <= tr["t_star"] or not np.all(np.isfinite(values)):
            continue
        ranks.append(_rank_of(values, tr["t_star"]))
    if not ranks:
        return {"top1": float("nan"), "top3": float("nan"), "mean_rank": float("nan"), "n": 0}
    arr = np.asarray(ranks)
    return {
        "top1": float(np.mean(arr == 1)),
        "top3": float(np.mean(arr <= 3)),
        "mean_rank": float(arr.mean()),
        "n": int(arr.size),
    }


def _permutation_null(traces: list[dict[str, Any]], resamples: int, seed: int) -> dict[str, Any]:
    """Shuffle step positions within each trace; recompute the top-1 rate each time.

    This preserves the deviations and the trace lengths and destroys only the alignment between
    the jump and `t*`, which is the thing being tested.
    """
    rng = np.random.default_rng(seed)
    observed = localization_rates(traces)["top1"]
    stats = np.empty(resamples)
    for r in range(resamples):
        hits = 0
        for tr in traces:
            shuffled = rng.permutation(tr["z"])
            hits += int(_rank_of(shuffled, tr["t_star"]) == 1)
        stats[r] = hits / len(traces)
    # One-sided: the prediction is that localisation beats chance.
    p = float((1 + np.sum(stats >= observed)) / (resamples + 1))
    return {
        "mean": float(stats.mean()),
        "sd": float(stats.std(ddof=1)) if resamples > 1 else 0.0,
        "p_value": p,
        "resamples": int(resamples),
        "observed": float(observed),
    }


def _roc(traces: list[dict[str, Any]], key: str = "z") -> dict[str, Any]:
    """Jump size as a per-step detector of the first rejection.

    Every step of every refuted trace is one observation; the positive class is `t = t*`. The AUC
    is computed by the rank identity, which handles ties correctly and needs no threshold sweep.
    """
    scores: list[float] = []
    labels: list[int] = []
    for tr in traces:
        z = tr[key]
        if z.size <= tr["t_star"] or not np.all(np.isfinite(z)):
            continue
        scores.extend(z.tolist())
        labels.extend([1 if i == tr["t_star"] else 0 for i in range(z.size)])
    if not scores or not any(labels) or all(labels):
        return {"auc": float("nan"), "n_positive": int(sum(labels)), "n": len(labels)}

    s = np.asarray(scores)
    y = np.asarray(labels)
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, s.size + 1)
    # Average ranks over ties so that a constant score gives exactly 0.5.
    _, inv, counts = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.zeros(counts.size)
    np.add.at(sums, inv, ranks)
    ranks = (sums / counts)[inv]

    n_pos = int(y.sum())
    n_neg = int(y.size - n_pos)
    auc = (ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return {"auc": float(auc), "n_positive": n_pos, "n_negative": n_neg, "n": int(y.size)}


def _by_length(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Top-1 against chance at each trace length, since chance depends on `L`."""
    out = []
    lengths = sorted({tr["L"] for tr in traces})
    for length in lengths:
        part = [tr for tr in traces if tr["L"] == length]
        rates = localization_rates(part)
        out.append(
            {
                "L": length,
                "n_traces": len(part),
                "top1": rates["top1"],
                "top3": rates["top3"],
                "chance": 1.0 / length,
            }
        )
    return out


def run_p2(
    df: pd.DataFrame,
    *,
    permutation_resamples: int = 2000,
    seed: int = 0,
    min_traces: int = 20,
) -> list[P2Result]:
    """Run the localisation test for every (model, layer, statistic) cell."""
    validate_table(df)
    results: list[P2Result] = []

    for (model, layer, statistic), cell in df.groupby(["model", "layer", "statistic"], sort=True):
        traces = _per_trace(cell)
        if len(traces) < min_traces:
            log.info(
                "skipping P2 for %s/L%s/%s: %d refuted traces (need %d)",
                model,
                layer,
                statistic,
                len(traces),
                min_traces,
            )
            continue

        rates = localization_rates(traces)
        chance = float(np.mean([1.0 / tr["L"] for tr in traces]))  # E[1/L], Theorem 4(iii)

        has_surprisal = any(np.all(np.isfinite(tr["surprisal"])) for tr in traces)
        surprisal_rates = None
        if has_surprisal:
            usable = [tr for tr in traces if np.all(np.isfinite(tr["surprisal"]))]
            surprisal_rates = localization_rates(usable, key="surprisal")

        res = P2Result(
            model=str(model),
            layer=_as_int(layer),
            statistic=str(statistic),
            n_refuted=len(traces),
            top1=rates["top1"],
            top3=rates["top3"],
            chance=chance,
            mean_rank=rates["mean_rank"],
            surprisal_top1=None if surprisal_rates is None else surprisal_rates["top1"],
            surprisal_top3=None if surprisal_rates is None else surprisal_rates["top3"],
            permutation=_permutation_null(traces, permutation_resamples, seed),
            roc=_roc(traces),
            by_length=_by_length(traces),
        )
        results.append(res)
        log.info(
            "P2 %s/L%s/%s: top-1=%.3f top-3=%.3f chance=%.3f (lift %.1fx) perm p=%.4f auc=%.3f",
            model,
            layer,
            statistic,
            res.top1,
            res.top3,
            res.chance,
            res.lift,
            res.permutation["p_value"],
            res.roc["auc"],
        )
    return results
