"""Inferential edge cases and dependence/weighting invariants."""

import numpy as np
import pandas as pd
import pytest

from onebigjump.readiness.finite_sample import (
    bounded_mean,
    localization_effects,
    sign_screen,
    threshold_rates,
)


def test_small_sample_is_uncertain_not_missing_or_degenerate():
    result = bounded_mean([1.0], -1, 1)
    assert result["interval"] == [-1, 1]
    assert sign_screen([1.0] * 5)["p_two_sided"] == 0.0625
    assert sign_screen([0.0] * 4)["p_two_sided"] is None


def test_invalid_values_do_not_silently_disappear():
    with pytest.raises(ValueError):
        bounded_mean([np.nan], 0, 1)
    with pytest.raises(ValueError):
        bounded_mean([2.0], 0, 1)
    assert bounded_mean([], 0, 1)["interval"] is None


def fixture():
    return pd.DataFrame(
        [
            {
                "trace_id": f"{task}:{a}",
                "prompt_id": task,
                "outcome": "refuted",
                "t": t,
                "t_star": 1,
                "z": z,
                "surprisal": s,
            }
            for task, attempts, zz, ss in [("a", 10, [0, 2], [2, 0]), ("b", 1, [2, 0], [0, 2])]
            for a in range(attempts)
            for t, (z, s) in enumerate(zip(zz, ss, strict=True))
        ]
    )


def test_tasks_are_not_reweighted_by_attempt_counts():
    data = fixture()
    result = localization_effects(data)
    assert result["traces"] == 11
    assert result["tasks"] == 2
    assert result["estimates"]["gain"]["mean"] == 0
    assert result["sign_screen"]["wins"] == result["sign_screen"]["losses"] == 1
    # No resampling below 20 tasks; the bound remains wide.
    assert result["estimates"]["gain"]["interval"] == [-1, 1]


def test_shared_pair_eligibility_and_original_step_positions():
    data = fixture()
    data.loc[(data.trace_id == "a:0") & (data.t == 0), "surprisal"] = np.nan
    result = localization_effects(data)
    assert result["traces"] == 10
    assert result["omitted"]["nonfinite_pair"] == 1
    dropped = localization_effects(data, drop_first=True)
    assert dropped["traces"] == 11
    assert dropped["estimates"]["gain"]["mean"] == 0


def test_ties_and_absorbing_post_failure_are_handled():
    data = fixture()
    data["z"] = data["surprisal"] = 1.0
    assert localization_effects(data)["estimates"]["jump"]["mean"] == 0
    extra = data[data.t == 1].copy()
    extra["t"] = 2
    extra["z"] = 1000
    result = threshold_rates(pd.concat([data, extra]), 0.5)
    assert result["groups"]["accepted"]["steps"] == 11
    assert result["groups"]["first_failure"]["steps"] == 11
    assert result["paired_discrimination"]["estimate"]["mean"] == 0


def test_interval_respects_confidence_level_and_task_count():
    small = bounded_mean([0.5] * 10, 0, 1)["radius_before_clipping"]
    big = bounded_mean([0.5] * 40, 0, 1)["radius_before_clipping"]
    assert big == pytest.approx(small / 2)
    assert bounded_mean([0.5] * 40, 0, 1, 0.01)["radius_before_clipping"] > big
