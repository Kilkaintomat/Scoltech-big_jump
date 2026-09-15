"""Survival, mean-excess, QQ and the paper's identifiability criterion."""

from __future__ import annotations

import numpy as np
import pytest

from onebigjump.stats import hill_plot, identified_tail, mean_excess, pareto_qq, survival


@pytest.fixture(scope="module")
def pareto() -> np.ndarray:
    return np.random.default_rng(9).pareto(2.0, 100_000) + 1.0


@pytest.fixture(scope="module")
def light() -> np.ndarray:
    return np.random.default_rng(9).exponential(1.0, 100_000)


class TestSurvival:
    def test_is_decreasing_and_reaches_one_over_n(self, pareto: np.ndarray) -> None:
        x, s = survival(pareto)
        assert np.all(np.diff(x) <= 0)
        assert s[0] == pytest.approx(1.0 / pareto.size)
        assert s[-1] == pytest.approx(1.0)

    def test_log_log_slope_is_minus_alpha(self, pareto: np.ndarray) -> None:
        x, s = survival(pareto)
        m = x > 5.0
        slope = np.polyfit(np.log(x[m]), np.log(s[m]), 1)[0]
        assert slope == pytest.approx(-2.0, abs=0.1)

    def test_thinning_keeps_the_extreme_tail(self, pareto: np.ndarray) -> None:
        x, _ = survival(pareto, n_points=300)
        assert x.size <= 300
        assert x.max() == pytest.approx(pareto.max())


class TestMeanExcess:
    def test_slope_matches_gamma_over_one_minus_gamma(self, pareto: np.ndarray) -> None:
        """For a GPD tail, E[Z-u | Z>u] is linear in u with slope gamma/(1-gamma) = 1 here."""
        u, me = mean_excess(pareto)
        m = (u > 20) & (u < 500)
        assert np.polyfit(u[m], me[m], 1)[0] == pytest.approx(1.0, abs=0.25)

    def test_is_flat_for_an_exponential(self, light: np.ndarray) -> None:
        u, me = mean_excess(light)
        m = (u > 1) & (u < 6)
        assert abs(np.polyfit(u[m], me[m], 1)[0]) < 0.1


class TestParetoQQ:
    def test_slope_is_gamma(self, pareto: np.ndarray) -> None:
        theo, emp = pareto_qq(pareto, 5_000)
        assert np.polyfit(theo, emp, 1)[0] == pytest.approx(0.5, abs=0.05)

    def test_light_tails_bend_away_from_the_line(self, light: np.ndarray) -> None:
        theo, emp = pareto_qq(light, 5_000)
        lo = emp[: emp.size // 2]
        hi = emp[emp.size // 2 :]
        s_lo = np.polyfit(theo[: theo.size // 2], lo, 1)[0]
        s_hi = np.polyfit(theo[theo.size // 2 :], hi, 1)[0]
        assert s_hi < s_lo, "an exponential tail flattens in a Pareto QQ plot"


class TestHillPlot:
    def test_returns_both_curves_over_the_requested_range(self, pareto: np.ndarray) -> None:
        hp = hill_plot(pareto, k_min=50, k_max_frac=0.3, n_points=25)
        assert len(hp["k"]) == len(hp["hill"]) == len(hp["moment"]) <= 25
        assert hp["k"][0] >= 50
        assert hp["k"][-1] <= 0.3 * pareto.size
        assert "ci_low" not in hp

    def test_bands_bracket_the_curve(self, pareto: np.ndarray) -> None:
        groups = np.repeat(np.arange(2_000), 50)
        hp = hill_plot(pareto, groups, k_min=200, k_max_frac=0.2, n_points=6, resamples=60)
        for lo, g, hi in zip(hp["ci_low"], hp["hill"], hp["ci_high"], strict=True):
            assert lo <= g <= hi


class TestIdentifiedTail:
    def test_a_pareto_is_identified(self, pareto: np.ndarray) -> None:
        it = identified_tail(pareto, {"hill": 0.50, "moment": 0.51, "gpd": 0.49})
        assert it.identified
        assert it.plateau and it.agreement
        assert it.decades >= 1.0
        assert it.plateau_k_range is not None

    def test_an_exponential_is_not_identified(self, light: np.ndarray) -> None:
        it = identified_tail(light, {"hill": 0.22, "moment": 0.03, "gpd": 0.01})
        assert not it.identified

    def test_disagreeing_estimators_break_identification(self, pareto: np.ndarray) -> None:
        it = identified_tail(pareto, {"hill": 0.50, "moment": 0.10, "gpd": 0.90})
        assert it.plateau, "the Hill plot is still flat"
        assert not it.agreement
        assert not it.identified

    def test_near_zero_estimates_use_an_absolute_criterion(self, pareto: np.ndarray) -> None:
        """A relative tolerance is meaningless at gamma ~ 0, which is exactly the H_alg regime."""
        it = identified_tail(pareto, {"hill": 0.02, "moment": -0.01, "gpd": 0.0})
        assert it.agreement

    def test_is_serialisable(self, pareto: np.ndarray) -> None:
        import json

        json.loads(json.dumps(identified_tail(pareto, {"hill": 0.5, "moment": 0.5}).as_dict()))
