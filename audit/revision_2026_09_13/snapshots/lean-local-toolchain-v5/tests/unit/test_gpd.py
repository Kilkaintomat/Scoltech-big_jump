"""GPD maximum likelihood and the likelihood-ratio comparisons behind `H_alg` as a finding."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from onebigjump.stats import (
    compare_tail_models,
    exponential_fit,
    gpd_fit,
    gpd_from_order_statistics,
    weibull_fit,
)
from onebigjump.stats.gpd import gpd_nll


@pytest.fixture(scope="module")
def rng() -> np.random.Generator:
    return np.random.default_rng(31337)


class TestShapeRecovery:
    @pytest.mark.parametrize("gamma", [-0.3, -0.1, 0.0, 0.2, 0.5, 0.9])
    def test_mle_recovers_the_shape(self, rng: np.random.Generator, gamma: float) -> None:
        y = stats.genpareto.rvs(gamma, scale=1.0, size=40_000, random_state=rng)
        y = y[y > 0]
        fit = gpd_fit(y)
        assert fit.converged
        assert fit.gamma == pytest.approx(gamma, abs=0.03)
        assert fit.sigma == pytest.approx(1.0, rel=0.08)

    def test_alpha_is_the_reciprocal_shape(self, rng: np.random.Generator) -> None:
        y = stats.genpareto.rvs(0.25, scale=1.0, size=20_000, random_state=rng)
        assert gpd_fit(y[y > 0]).alpha == pytest.approx(4.0, rel=0.15)

    def test_alpha_is_infinite_when_the_tail_is_light(self, rng: np.random.Generator) -> None:
        y = stats.genpareto.rvs(-0.2, scale=1.0, size=20_000, random_state=rng)
        assert gpd_fit(y[y > 0]).alpha == float("inf")

    def test_order_statistic_form_matches_the_paper(self, rng: np.random.Generator) -> None:
        """Equation 3 fits the k excesses over Z_(k+1)."""
        z = rng.pareto(2.0, 100_000) + 1.0
        fit = gpd_from_order_statistics(z, 5_000)
        assert fit.gamma == pytest.approx(0.5, abs=0.05)
        assert fit.n_excesses == 5_000
        assert fit.threshold == pytest.approx(float(np.sort(z)[::-1][5_000]))


class TestLikelihood:
    def test_the_fit_beats_neighbouring_parameters(self, rng: np.random.Generator) -> None:
        y = stats.genpareto.rvs(0.4, scale=2.0, size=5_000, random_state=rng)
        y = y[y > 0]
        fit = gpd_fit(y)
        best = gpd_nll(fit.gamma, fit.sigma, y)
        for dg, ds in [(0.05, 0.0), (-0.05, 0.0), (0.0, 0.1), (0.0, -0.1), (0.03, 0.05)]:
            assert gpd_nll(fit.gamma + dg, fit.sigma + ds, y) >= best

    def test_zero_shape_reduces_to_the_exponential(self, rng: np.random.Generator) -> None:
        y = rng.exponential(2.0, 10_000)
        exp = exponential_fit(y)
        assert -gpd_nll(0.0, exp["scale"], y) == pytest.approx(exp["loglik"], rel=1e-12)

    def test_support_violations_are_infinite(self) -> None:
        y = np.array([1.0, 2.0, 10.0])
        assert gpd_nll(-1.0, 1.0, y) == float("inf")  # 1 + gamma*y/sigma <= 0 at y = 10
        assert gpd_nll(0.5, -1.0, y) == float("inf")


class TestModelComparison:
    """`H_alg` must be a positive finding: a light-tailed fit that beats the Pareto fit."""

    @pytest.mark.parametrize("gamma", [0.4, 0.6])
    def test_heavy_excesses_are_called_heavy(self, rng: np.random.Generator, gamma: float) -> None:
        y = stats.genpareto.rvs(gamma, scale=1.0, size=8_000, random_state=rng)
        cmp_ = compare_tail_models(y[y > 0])
        assert cmp_.favours.startswith("heavy")
        assert cmp_.p_gpd_vs_exponential < 0.01
        assert cmp_.vuong_gpd_vs_weibull > 0

    @pytest.mark.parametrize("shape", [0.6, 1.5, 2.0])
    def test_weibull_excesses_are_called_light(
        self, rng: np.random.Generator, shape: float
    ) -> None:
        y = stats.weibull_min.rvs(shape, scale=1.0, size=8_000, random_state=rng)
        cmp_ = compare_tail_models(y[y > 0])
        assert cmp_.favours == "light"
        assert cmp_.vuong_gpd_vs_weibull < 0

    def test_exponential_excesses_do_not_beat_the_exponential(
        self, rng: np.random.Generator
    ) -> None:
        y = rng.exponential(1.0, 8_000)
        cmp_ = compare_tail_models(y)
        assert cmp_.favours == "inconclusive"  # non-rejection is not positive evidence
        assert cmp_.p_gpd_vs_exponential > 0.01
        assert abs(cmp_.gpd.gamma) < 0.05

    def test_aic_ranks_the_generating_family_first(self, rng: np.random.Generator) -> None:
        y = stats.genpareto.rvs(0.5, scale=1.0, size=8_000, random_state=rng)
        aic = compare_tail_models(y[y > 0]).aic
        assert aic["gpd"] < aic["exponential"]
        assert aic["gpd"] < aic["weibull"]

    def test_weibull_fit_recovers_its_shape(self, rng: np.random.Generator) -> None:
        y = stats.weibull_min.rvs(0.7, scale=2.0, size=20_000, random_state=rng)
        fit = weibull_fit(y)
        assert fit["shape"] == pytest.approx(0.7, rel=0.05)
        assert fit["scale"] == pytest.approx(2.0, rel=0.08)


class TestInputHandling:
    def test_too_few_excesses_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 5"):
            gpd_fit(np.array([1.0, 2.0]))

    def test_k_out_of_range_raises(self) -> None:
        z = np.arange(1.0, 20.0)
        with pytest.raises(ValueError, match="k must be in"):
            gpd_from_order_statistics(z, 100)


class TestEndpointFailure:
    @pytest.mark.parametrize("size", [6, 20, 60])
    def test_narrow_excesses_preserve_failure_diagnostics_but_not_an_estimate(self, size):
        fit = gpd_fit(np.linspace(10.0, 11.0, size))
        assert fit.gamma < -1
        assert not fit.converged
        assert "nonregular" in fit.message
        assert np.isnan(fit.shape_estimate)
        assert np.isnan(fit.alpha)
        assert fit.as_dict()["gamma"] == fit.gamma

    def test_endpoint_singularity_cannot_be_evidence_for_algorithmicity(self):
        comparison = compare_tail_models(np.linspace(10.0, 11.0, 20))
        assert not comparison.gpd.converged
        assert comparison.favours == "inconclusive"
        assert np.isnan(comparison.p_gpd_vs_exponential)
        assert np.isnan(comparison.p_gpd_vs_weibull)
