"""Hill and moment estimators against laws whose extreme value index is known exactly."""

from __future__ import annotations

import numpy as np
import pytest

from onebigjump.stats import hill, hill_curve, log_moments, moment, moment_curve, xi_from_gamma


@pytest.fixture(scope="module")
def rng() -> np.random.Generator:
    return np.random.default_rng(20270101)


class TestKnownIndices:
    """gamma = 1/alpha for a Pareto tail; gamma = 0 in the Gumbel domain."""

    @pytest.mark.parametrize("alpha", [1.0, 2.0, 4.0])
    def test_hill_recovers_pareto_index(self, rng: np.random.Generator, alpha: float) -> None:
        z = rng.pareto(alpha, 200_000) + 1.0
        assert hill(z, 10_000) == pytest.approx(1.0 / alpha, abs=0.03)

    @pytest.mark.parametrize("alpha", [1.0, 2.0, 4.0])
    def test_moment_recovers_pareto_index(self, rng: np.random.Generator, alpha: float) -> None:
        z = rng.pareto(alpha, 200_000) + 1.0
        assert moment(z, 10_000) == pytest.approx(1.0 / alpha, abs=0.05)

    def test_student_t_tail_index(self, rng: np.random.Generator) -> None:
        """|t_nu| is regularly varying with alpha = nu, so gamma = 1/nu."""
        z = np.abs(rng.standard_t(3, 400_000))
        assert hill(z, 4_000) == pytest.approx(1.0 / 3.0, abs=0.04)


class TestDichotomy:
    """The estimators must separate H_heur from H_alg the way Section 4 says they do."""

    def test_hill_is_biased_upward_on_light_tails(self, rng: np.random.Generator) -> None:
        """Hill is the Pareto MLE: it cannot return a nonpositive value (Section 4)."""
        z = rng.exponential(1.0, 200_000)
        g = hill(z, 5_000)
        assert g > 0.0
        assert g > 0.1  # visibly, not marginally, away from the truth gamma = 0

    def test_moment_returns_about_zero_on_light_tails(self, rng: np.random.Generator) -> None:
        """Unlike Hill, the moment estimator can and does return ~0 in the Gumbel domain.

        The half-normal is the harder case: convergence of the normal to its Gumbel limit is
        at rate 1/log n, so the moment estimator sits at a stable ~-0.1 at any k here. That is
        a finite-sample bias, not a heavy tail, and it lands on the correct side of 0 -- which
        is the property Section 4 relies on to make H_alg a rejectable hypothesis.
        """
        for z in (rng.exponential(1.0, 200_000), np.abs(rng.normal(0, 1, 200_000))):
            assert abs(moment(z, 5_000)) < 0.15

    def test_moment_is_far_below_hill_on_light_tails(self, rng: np.random.Generator) -> None:
        """The gap between the two estimators is what flags a light tail in Table 1."""
        for z in (rng.exponential(1.0, 200_000), np.abs(rng.normal(0, 1, 200_000))):
            assert hill(z, 5_000) - moment(z, 5_000) > 0.1

    def test_moment_goes_negative_on_bounded_support(self, rng: np.random.Generator) -> None:
        """gamma < 0 requires a finite right endpoint -- the Tracr-style positive control."""
        z = rng.uniform(0.0, 1.0, 200_000)  # gamma = -1
        assert moment(z, 5_000) < -0.5


class TestOrderParameter:
    def test_xi_is_the_positive_part_of_gamma(self) -> None:
        assert xi_from_gamma(0.4) == pytest.approx(0.4)
        assert xi_from_gamma(0.0) == 0.0
        assert xi_from_gamma(-0.3) == 0.0, "bounded support is still xi = 0: algorithmic"
        assert np.isnan(xi_from_gamma(float("nan")))


class TestLogMoments:
    def test_m1_equals_the_hill_curve(self, rng: np.random.Generator) -> None:
        z = rng.pareto(2.0, 5_000) + 1.0
        k, m1, _ = log_moments(z, k_max=500)
        k2, curve = hill_curve(z, k_max=500)
        assert np.array_equal(k, k2)
        np.testing.assert_allclose(m1, curve)

    def test_m2_matches_a_direct_computation(self, rng: np.random.Generator) -> None:
        z = rng.pareto(2.0, 2_000) + 1.0
        x = np.sort(z)[::-1]
        _, _, m2 = log_moments(z, k_max=50)
        for kk in (5, 17, 50):
            direct = np.mean(np.log(x[:kk] / x[kk]) ** 2)
            assert m2[kk - 1] == pytest.approx(direct, rel=1e-10)

    def test_m2_is_about_twice_m1_squared_for_pareto(self, rng: np.random.Generator) -> None:
        """E M2 -> 2 gamma^2 while E M1 -> gamma: the control variate of the double bootstrap."""
        z = rng.pareto(2.0, 200_000) + 1.0
        _, m1, m2 = log_moments(z, k_max=20_000)
        assert m2[-1] == pytest.approx(2.0 * m1[-1] ** 2, rel=0.05)

    def test_moment_curve_and_point_agree(self, rng: np.random.Generator) -> None:
        z = rng.pareto(3.0, 20_000) + 1.0
        _, curve = moment_curve(z, k_max=1_000)
        assert moment(z, 1_000) == pytest.approx(curve[-1])


class TestInputHandling:
    def test_non_positive_and_non_finite_values_are_dropped(self) -> None:
        z = np.array([3.0, 2.0, np.nan, -1.0, 0.0, np.inf, 1.5, 1.2, 1.1])
        k, m1, _ = log_moments(z, k_max=3)
        assert k.tolist() == [1, 2, 3]
        assert np.all(np.isfinite(m1))

    def test_empty_after_filtering_raises(self) -> None:
        with pytest.raises(ValueError, match="no strictly positive"):
            log_moments(np.array([0.0, -1.0, np.nan]))

    def test_k_beyond_the_sample_raises(self) -> None:
        with pytest.raises(ValueError):
            hill(np.array([3.0, 2.0, 1.0]), 5)
