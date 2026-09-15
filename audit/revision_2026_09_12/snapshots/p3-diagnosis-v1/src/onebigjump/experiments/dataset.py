"""The one table every P1-P5 test reads.

Whatever produced a trace -- the Lean kernel over a prover's output, a symbolic checker over a
chain of thought, or the Kesten surrogate of Theorem 5 -- it reduces to the same long table, one
row per (trace, step):

    trace_id  prompt_id  model  layer  statistic  t  L  z  valid  t_star  outcome  surprisal

Having one schema is what lets the same P1-P5 code be validated against the simulation, where the
answer is known in closed form, and then run unchanged on real traces. A test that only ever sees
real data has nothing to be checked against.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:  # pragma: no cover
    from ..lean.schemas import ProofTrace
    from ..models.activations import Calibration, Trajectory
    from ..simulation.kesten import KestenTraces

__all__ = [
    "COLUMNS",
    "SUBSETS",
    "from_kesten",
    "from_traces",
    "subset",
    "validate_table",
]

COLUMNS = (
    "trace_id",
    "prompt_id",
    "model",
    "layer",
    "statistic",
    "t",
    "L",
    "z",
    "valid",
    "t_star",
    "outcome",
    "surprisal",
)

#: The three rows of Table 1, and what each selects.
SUBSETS = {
    "verified": "every step of a verified trace",
    "refuted_pre": "steps strictly before t* in a refuted trace -- the diagnostic subset",
    "refuted_post": "steps at and after t* in a refuted trace",
    "refuted_all": "every step of a refuted trace",
}


def validate_table(df: pd.DataFrame) -> pd.DataFrame:
    """Check the invariants the P1-P5 code relies on, and fail loudly if they do not hold."""
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"deviations table is missing columns: {missing}")
    if df.empty:
        raise ValueError("deviations table is empty")
    if not np.isfinite(df["z"].to_numpy(dtype=float)).all() or (df["z"] < 0).any():
        raise ValueError("step deviations must be finite and nonnegative")
    if not df["valid"].isin([True, False]).all():
        raise ValueError("valid labels must be boolean or binary")
    if df[["trace_id", "prompt_id", "model", "layer", "statistic", "outcome"]].isna().any().any():
        raise ValueError("missing trace metadata")
    for col in ("t", "L", "layer"):
        values = df[col].to_numpy(dtype=float)
        if not np.isfinite(values).all() or np.any(values != np.floor(values)):
            raise ValueError(f"{col} must contain finite integer values")
    if df["t"].lt(0).any() or df["L"].lt(1).any():
        raise ValueError("step indices must be nonnegative and lengths positive")

    key = ["model", "trace_id", "layer", "statistic"]
    for keys, group in df.groupby(key, sort=False):
        steps = group["t"].to_numpy()
        if len(np.unique(steps)) != len(steps):
            raise ValueError(f"duplicate step indices in {dict(zip(key, keys, strict=True))}")
        # Absorption: v_t may fall from 1 to 0, never rise back (Section 2).
        v = group.sort_values("t")["valid"].to_numpy()
        if np.any(np.diff(v.astype(int)) > 0):
            raise ValueError(f"non-absorbing labels in {dict(zip(key, keys, strict=True))}")
        for col in ("prompt_id", "L", "outcome", "t_star"):
            if group[col].nunique(dropna=False) != 1:
                raise ValueError(f"inconsistent {col} within trace {keys}")
        length = int(group["L"].iloc[0])
        if len(steps) != length or not np.array_equal(np.sort(steps), np.arange(length)):
            raise ValueError(f"steps must cover 0..L-1 without gaps in trace {keys}")
        star = group["t_star"].iloc[0]
        outcome = group["outcome"].iloc[0]
        if outcome == "verified":
            if not pd.isna(star) or not np.all(v):
                raise ValueError(f"verified trace has a failure or t_star: {keys}")
        elif outcome == "refuted":
            if pd.isna(star) or star != int(star) or not 0 <= star < length:
                raise ValueError(f"refuted trace has invalid t_star: {keys}")
            if not np.array_equal(v.astype(bool), np.arange(length) < star):
                raise ValueError(f"t_star disagrees with labels in trace {keys}")
        else:
            raise ValueError(f"unlabelled outcome {outcome!r} in deviations table")
        if "status" in group:
            statuses = group.sort_values("t")["status"].to_numpy()
            expected_ok = statuses == "ok"
            if not np.array_equal(expected_ok, v.astype(bool)):
                raise ValueError(f"step status disagrees with valid labels in trace {keys}")
            if outcome == "refuted" and (
                statuses[int(star)] not in {"error", "timeout", "sorry", "unsolved_goals"}
                or np.any(statuses[int(star) + 1 :] != "unreached")
            ):
                raise ValueError(f"steps after t_star must be unreached in trace {keys}")
    return df


def from_traces(
    traces: Iterable[ProofTrace],
    trajectories: dict[str, dict[int, Trajectory]],
    calibrations: dict[int, Calibration] | None = None,
    *,
    statistics: Sequence[str] = ("raw", "whitened", "innovation"),
    model: str = "",
) -> pd.DataFrame:
    """Build the table from labelled Lean traces and their extracted trajectories.

    Traces without step structure (a discarded parse error) contribute nothing: they have no
    labels, and inventing rows for them would put unlabelled steps into a labelled analysis.
    """
    from ..models.activations import deviations

    rows: list[dict[str, Any]] = []
    for trace in traces:
        if not trace.labelled:
            continue
        per_layer = trajectories.get(trace.trace_id)
        if not per_layer:
            continue
        for layer, traj in per_layer.items():
            cal = (calibrations or {}).get(layer)
            devs = deviations(traj, cal)
            if trace.n_steps != traj.n_steps:
                raise ValueError(f"trajectory/label length mismatch for {trace.trace_id}")
            n = trace.n_steps
            for name, values in devs.items():
                if name not in statistics:
                    continue
                for t in range(n):
                    step = trace.steps[t]
                    rows.append(
                        {
                            "trace_id": trace.trace_id,
                            "prompt_id": trace.problem_id,
                            "model": model or trace.model_id,
                            "layer": int(layer),
                            "statistic": name,
                            "t": t,
                            "L": n,
                            "z": float(values[t]),
                            "valid": bool(step.valid),
                            "t_star": trace.t_star,
                            "outcome": trace.outcome.value,
                            "status": step.status.value,
                            "surprisal": float(traj.surprisal[t])
                            if t < traj.surprisal.size
                            else np.nan,
                        }
                    )
    if not rows:
        raise ValueError("no labelled traces with trajectories")
    return validate_table(pd.DataFrame(rows, columns=[*COLUMNS, "status"]))


def from_kesten(
    traces: KestenTraces, tolerance_quantile: float = 0.999, *, model: str = "kesten"
) -> pd.DataFrame:
    """Build the table from the surrogate of Theorem 5, using Hypothesis 1 as the labeller.

    Under Hypothesis 1, `v_t = 1{Z_t <= tau}` up to and including the first rejected step, so the
    coupling that the real experiments *test* is here imposed by construction. That is exactly
    what makes this the calibration case: P1-P3 must come out right when the coupling holds.
    """
    tau = traces.tolerance(tolerance_quantile)
    t_star = traces.first_exceedance(tau)
    m, ell = traces.z.shape
    idx = np.arange(ell)

    trace_ids = np.repeat([f"kesten-{i:06d}" for i in range(m)], ell)
    ts = np.tile(idx, m)
    z = traces.z.ravel()
    star_col = np.repeat(t_star, ell)
    valid = (star_col < 0) | (ts < star_col)

    df = pd.DataFrame(
        {
            "trace_id": trace_ids,
            "prompt_id": np.repeat([f"p{traces.p:.4f}"], m * ell),
            "model": model,
            "layer": 0,
            "statistic": "raw",
            "t": ts,
            "L": ell,
            "z": z,
            "valid": valid,
            "t_star": np.where(star_col < 0, np.nan, star_col),
            "outcome": np.where(star_col < 0, "verified", "refuted"),
            "surprisal": np.nan,
        },
        columns=list(COLUMNS),
    )
    df.attrs["tau"] = float(tau)
    df.attrs["p"] = float(traces.p)
    df.attrs["alpha_theory"] = traces.alpha_theory
    df.attrs["xi_theory"] = traces.xi_theory
    return validate_table(df)


def subset(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """One of the row groups of Table 1."""
    if name not in SUBSETS:
        raise ValueError(f"unknown subset {name!r}; expected one of {sorted(SUBSETS)}")
    if name == "verified":
        return df[df["outcome"] == "verified"]
    refuted = df[df["outcome"] == "refuted"]
    if name == "refuted_all":
        return refuted
    star = refuted["t_star"].to_numpy()
    t = refuted["t"].to_numpy()
    keep = t < star if name == "refuted_pre" else t >= star
    return refuted[keep]
