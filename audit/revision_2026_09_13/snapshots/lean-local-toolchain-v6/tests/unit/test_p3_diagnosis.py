import numpy as np
from scipy import stats

from onebigjump.readiness.p3_diagnosis import diagnose, draw_sample


def test_generated_failures_have_prescribed_support_and_independent_calibration():
    cal, fail, cutoff = draw_sample(271, 0.25, 0.99)
    cal2, fail2, cutoff2 = draw_sample(271, 0.25, 0.98)
    assert cal.shape == (48, 48) and fail.shape == (48, 3)
    assert np.array_equal(cal, cal2)
    assert np.all(fail > cutoff) and np.all(fail2 > cutoff2)
    assert np.allclose(
        (fail - cutoff) / (1 + 0.25 * cutoff), (fail2 - cutoff2) / (1 + 0.25 * cutoff2)
    )
    assert np.isclose(cutoff, stats.genpareto.ppf(0.99, 0.25))


def test_oracle_bootstrap_resamples_whole_failure_tasks_and_basic_reflects_bounds(monkeypatch):
    from onebigjump.readiness import p3_diagnosis as module

    cal, fail, cutoff = draw_sample(912, 0.25, 0.98)
    seen = []

    def fit(values, threshold):
        assert values.shape == (48, 3)
        assert all(any(np.array_equal(row, original) for original in fail) for row in values)
        seen.append((values.copy(), threshold))
        return float(values.mean() / 100)

    monkeypatch.setattr(module, "shape_at", fit)
    config = {
        "q": 0.01,
        "statistics": {"bootstrap": 8, "min_tasks": 20, "valid_fraction": 0.9, "family_size": 9},
    }
    result = diagnose(cal, fail, cutoff, config, 919)
    assert len(seen) == 18
    for i in range(2, 18, 2):
        assert np.array_equal(seen[i][0], seen[i + 1][0])
        assert seen[i + 1][1] == cutoff
    for name in ("oracle", "estimated"):
        cell = result["methods"][name]
        bounds = cell["percentile"]["ci95"]
        if bounds is not None:
            assert np.allclose(
                cell["basic"]["ci95"],
                [2 * cell["point"] - bounds[1], 2 * cell["point"] - bounds[0]],
            )


def test_small_tail_population_cannot_produce_an_interval():
    cal, fail, cutoff = draw_sample(817, 0.25, 0.99, tasks=19)
    config = {
        "q": 0.01,
        "statistics": {"bootstrap": 2, "min_tasks": 20, "valid_fraction": 0.9, "family_size": 9},
    }
    result = diagnose(cal, fail, cutoff, config, 920)
    assert all(
        c["percentile"]["ci95"] is None and c["basic"]["ci95"] is None
        for c in result["methods"].values()
    )
