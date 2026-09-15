"""P1: step deviations of refuted traces have a heavier tail than those of verified ones.

    gamma_hat_ref > gamma_hat_ver, and the excess is carried by the steps at and after t*.

Three subsets are estimated separately, and the paper is explicit about which one matters:
`refuted, t < t*` is **the diagnostic one**, "since a heavier pre-rejection tail than on verified
traces would indicate that the model was already off-manifold before the kernel noticed". The
stated expectation is `verified ~ pre-rejection < post-rejection`.

The comparison is made on trace-bootstrap intervals, not on point estimates: the pre-rejection
subset is small, and a difference in the third decimal of two Hill estimates computed on a few
hundred exceedances is not a finding.

**A selection effect to keep in view.** Wherever labels come from the coupling hypothesis rather
than from a verifier -- which is the case in the Kesten calibration, where `v_t = 1{Z_t <= tau}`
by construction -- a "verified" trace is *defined* as one whose maximum stayed below `tau`. Its
deviations are then truncated above by `tau`, so its tail is light for a reason that has nothing
to do with the mechanism, and P1 comes out true by selection. That is a property of the
calibration setup, not of the Lean experiments, where "verified" means the kernel accepted the
proof and no threshold is involved. The consequence is that the simulation can check the
*direction* of P1 and the machinery that computes it, but not the *magnitude* of the separation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from ..config import TailEstimationConfig
from ..logging import get_logger
from ..stats import estimate_tail
from .dataset import subset, validate_table

__all__ = ["P1Result", "run_p1", "tail_separation"]


def _as_int(value: Any) -> int:
    """Narrow a pandas groupby key to `int`; the stubs type these as bare `Hashable`."""
    return int(cast(int, value))


log = get_logger(__name__)

ORDER = ("verified", "refuted_pre", "refuted_post", "refuted_all")


@dataclass
class P1Result:
    """One cell of Table 1: a (model, layer, statistic) with its subsets."""

    model: str
    layer: int
    statistic: str
    estimates: dict[str, dict[str, Any]] = field(default_factory=dict)
    separation: dict[str, Any] = field(default_factory=dict)

    def rows(self) -> list[dict[str, Any]]:
        out = []
        for name in ORDER:
            est = self.estimates.get(name)
            if est is None:
                continue
            out.append(
                {
                    "model": self.model,
                    "layer": self.layer,
                    "statistic": self.statistic,
                    "subset": name,
                    **{
                        k: v
                        for k, v in est.items()
                        if k
                        in {
                            "m_traces",
                            "n_steps",
                            "k",
                            "hill",
                            "hill_lo",
                            "hill_hi",
                            "moment",
                            "moment_lo",
                            "moment_hi",
                            "gpd",
                            "gpd_lo",
                            "gpd_hi",
                            "xi",
                            "sigma2_cl",
                            "favours",
                            "identified",
                        }
                    },
                }
            )
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "layer": self.layer,
            "statistic": self.statistic,
            "estimates": self.estimates,
            "separation": self.separation,
        }


def tail_separation(estimates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compare the subsets the way the prediction is stated, on intervals rather than points.

    `separated` requires the refuted interval to sit strictly above the verified one, which is a
    conservative reading of `gamma_hat_ref > gamma_hat_ver`: overlapping intervals mean the data
    do not distinguish them, whatever the point estimates do.
    """

    def ci(name: str, estimator: str = "hill") -> tuple[Any, Any, Any] | None:
        est = estimates.get(name)
        if est is None:
            return None
        boot = est.get("bootstrap", {}).get(estimator, {})
        return est.get(estimator), boot.get("ci_low"), boot.get("ci_high")

    ver = ci("verified")
    ref = ci("refuted_all")
    pre = ci("refuted_pre")
    post = ci("refuted_post")

    def strictly_above(
        a: tuple[Any, Any, Any] | None, b: tuple[Any, Any, Any] | None
    ) -> bool | None:
        if a is None or b is None or a[1] is None or b[2] is None:
            return None
        if not np.isfinite(a[1]) or not np.isfinite(b[2]):
            return None
        return bool(a[1] > b[2])

    complete = all(
        c is not None and all(v is not None and np.isfinite(v) for v in c) for c in (ver, pre, post)
    )

    return {
        "gamma_verified": None if ver is None else ver[0],
        "gamma_refuted": None if ref is None else ref[0],
        "gamma_refuted_pre": None if pre is None else pre[0],
        "gamma_refuted_post": None if post is None else post[0],
        "delta_refuted_minus_verified": (None if (ver is None or ref is None) else ref[0] - ver[0]),
        "refuted_above_verified": strictly_above(ref, ver),
        "post_above_verified": strictly_above(post, ver),
        "pre_above_verified": strictly_above(pre, ver),
        "post_above_pre": strictly_above(post, pre),
        "expected_pattern_holds": (
            None
            if not complete
            else strictly_above(post, ver) is True and strictly_above(pre, ver) is False
        ),
    }


def run_p1(
    df: pd.DataFrame,
    cfg: TailEstimationConfig | None = None,
    *,
    seed: int = 0,
    min_steps: int = 200,
    min_bootstrap_groups: int = 20,
    with_hill_plot: bool = True,
) -> list[P1Result]:
    """Estimate the tail on every subset, for every (model, layer, statistic) cell."""
    validate_table(df)
    cfg = cfg or TailEstimationConfig()
    results: list[P1Result] = []

    for (model, layer, statistic), cell in df.groupby(["model", "layer", "statistic"], sort=True):
        res = P1Result(model=str(model), layer=_as_int(layer), statistic=str(statistic))
        for name in ORDER:
            part = subset(cell, name)
            if len(part) < min_steps:
                log.info(
                    "skipping %s/%s/%s subset %s: only %d steps (need %d)",
                    model,
                    layer,
                    statistic,
                    name,
                    len(part),
                    min_steps,
                )
                continue
            groups, unit = _bootstrap_unit(part, min_groups=min_bootstrap_groups)
            est = estimate_tail(
                part["z"].to_numpy(),
                groups.to_numpy(),
                cfg.model_copy(update={"bootstrap_unit": unit}),
                seed=seed,
                with_hill_plot=with_hill_plot,
                meta={
                    "model": model,
                    "layer": _as_int(layer),
                    "statistic": statistic,
                    "subset": name,
                    "bootstrap_unit": unit,
                },
            )
            res.estimates[name] = est.as_dict() | est.row()
            res.estimates[name]["m_traces"] = int(part["trace_id"].nunique())
        if not res.estimates:
            continue
        res.separation = tail_separation(res.estimates)
        results.append(res)
        log.info(
            "P1 %s/L%s/%s: verified=%s refuted=%s separated=%s",
            model,
            layer,
            statistic,
            _fmt(res.separation["gamma_verified"]),
            _fmt(res.separation["gamma_refuted"]),
            res.separation["refuted_above_verified"],
        )
    return results


def _bootstrap_unit(
    part: pd.DataFrame, min_groups: int = 20
) -> tuple[pd.Series, Literal["trace", "prompt"]]:
    """Pick the resampling unit, and say which one was picked.

    Section 4 resamples prompts when several traces share a prompt, because such traces are not
    independent. But that rule only helps while there are enough distinct prompts to resample:
    with one prompt every resample is the same sample and the interval collapses to a point,
    which reads as an impossibly precise estimate rather than as a failure. Below `min_groups`
    prompts the unit falls back to traces, and the choice is recorded in the estimate's metadata.
    """
    n_prompts = int(part["prompt_id"].nunique())
    n_traces = int(part["trace_id"].nunique())
    if min_groups <= n_prompts < n_traces:
        return part["prompt_id"], "prompt"
    if n_traces < min_groups:
        log.warning("only %d traces in this subset; the trace bootstrap will be coarse", n_traces)
    return part["trace_id"], "trace"


def _fmt(x: float | None) -> str:
    return "-" if x is None else f"{x:.4f}"
