"""Controls catch position-index errors, calibration leakage and pseudoreplication."""

import numpy as np
import pandas as pd
import pytest

from onebigjump.readiness import controls, diagnostics

CONFIG = {
    "statistics": {
        "min_tasks": 20,
        "bootstrap": 50,
        "permutations": 19,
        "min_steps": 200,
        "min_k": 20,
        "inner_bootstrap": 20,
    }
}


def frame(tasks=4, attempts=2):
    return pd.DataFrame(
        [
            {
                "trace_id": f"p{p}:a{a}",
                "prompt_id": f"p{p}",
                "task_family": "f",
                "role": "evaluation",
                "outcome": "refuted",
                "t": t,
                "t_star": 2,
                "z": [100, 1, 10][t],
                "surprisal": [1, 2, 10][t],
            }
            for p in range(tasks)
            for a in range(attempts)
            for t in range(3)
        ]
    )


def test_excluding_first_keeps_step_coordinates_and_pairs():
    data = frame()
    data.loc[data["trace_id"] == "p0:a0", "surprisal"] = np.nan
    result = diagnostics.paired_views(data, CONFIG)
    assert result["all"]["jump_top1"] == 0
    assert result["all"]["surprisal_top1"] == 1
    later = result["failure_after_first_drop_first"]
    assert later["jump_top1"] == later["surprisal_top1"] == 1
    assert later["n_traces"] == 7 and later["n_tasks"] == 4
    assert later["omitted_traces"]["nonfinite_pair"] == 1
    assert later["paired_ci95"] is None
    assert set(later["paired_trace_ids"]) == set(result["all"]["paired_trace_ids"])


def test_many_attempts_do_not_create_independent_tasks():
    result = diagnostics.paired_views(frame(tasks=2, attempts=30), CONFIG)
    assert result["all"]["n_traces"] == 60
    assert result["all"]["paired_ci95"] is None


def test_first_failures_are_explicitly_excluded():
    data = frame()
    data.loc[data["prompt_id"] == "p0", "t_star"] = 0
    result = diagnostics.paired_views(data, CONFIG)
    assert result["all"]["n_traces"] == 8
    assert result["failure_after_first_drop_first"]["n_traces"] == 6
    assert result["failure_after_first_drop_first"]["omitted_traces"]["first_failure"] == 2


def test_null_with_nonzero_first_index_keeps_same_position_confound():
    data = frame(tasks=25, attempts=1)
    data = data[data["t"] > 0]
    result = controls.positional_null(data, 19)
    assert result["jump_top1"] == result["null_jump_mean"] == result["p_jump"] == 1


def calibration_data():
    rng = np.random.default_rng(91)
    table = []
    states = {}
    for role, n in (("calibration", 8), ("evaluation", 3)):
        for task in range(n):
            rid = f"{role}:{task}"
            increments = rng.normal(size=(4, 3))
            increments[0] *= 100
            states[rid] = np.vstack([np.zeros(3), np.cumsum(increments, axis=0)])
            for t in range(4):
                table.append(
                    {
                        "trace_id": rid,
                        "prompt_id": rid,
                        "role": role,
                        "task_family": "f",
                        "outcome": "verified",
                        "t": t,
                        "t_star": np.nan,
                        "z": 1.0,
                        "surprisal": 1.0,
                    }
                )
    return pd.DataFrame(table), states


def test_disjoint_threshold_and_first_increment_refit_are_actual():
    table, states = calibration_data()
    spec = {"drop_first": True, "disjoint": True, "shrinkage": 0.1}
    result = diagnostics.fit_specification(table, states, spec, CONFIG)
    assert result["status"] == "complete"
    assert not set(result["fit_task_ids"]) & set(result["threshold_task_ids"])
    assert result["fit_increments"] == 4 * 3
    assert result["threshold"]["calibration"]["steps"] == 4 * 3
    assert result["threshold"]["evaluation"]["accepted_first"]["steps"] == 0
    changed = {
        key: value * (1000 if key.startswith("evaluation:") else 1) for key, value in states.items()
    }
    again = diagnostics.fit_specification(table, changed, spec, CONFIG)
    assert again["threshold"]["tau"] == result["threshold"]["tau"]


def test_role_overlap_refused():
    table, states = calibration_data()
    table.loc[table["role"] == "evaluation", "prompt_id"] = "calibration:0"
    with pytest.raises(ValueError, match="overlap"):
        diagnostics.fit_specification(table, states, diagnostics.variants()[0], CONFIG)
