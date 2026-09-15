"""Theorem 5: the closed form, and a simulation that has to satisfy it."""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from onebigjump.config import KestenConfig
from onebigjump.simulation.kesten import (
    alpha_two_heuristics,
    lyapunov_exponent,
    p_critical,
    simulate,
    stationary_step_scale,
    xi_two_heuristics,
)
from onebigjump.stats import hill, moment

RHO, KAPPA = 0.7, 2.5

# The three indices stated in the caption of Figure 1.
PAPER_ALPHAS = {0.02: 3.97, 0.05: 2.80, 0.10: 1.82}


class TestClosedForm:
    @pytest.mark.parametrize("p,expected", PAPER_ALPHAS.items())
    def test_reproduces_the_indices_printed_in_figure_one(self, p: float, expected: float) -> None:
        assert alpha_two_heuristics(p, RHO, KAPPA) == pytest.approx(expected, abs=0.005)

    def test_the_root_actually_solves_the_moment_equation(self) -> None:
        for p in (0.01, 0.05, 0.1, 0.2, 0.27):
            a = alpha_two_heuristics(p, RHO, KAPPA)
            assert (1 - p) * RHO**a + p * KAPPA**a == pytest.approx(1.0, abs=1e-9)

    def test_no_root_at_p_zero(self) -> None:
        """A uniformly contractive map has an empty tail: Theorem 5(iii), not a failure."""
        assert alpha_two_heuristics(0.0, RHO, KAPPA) == float("inf")
        assert xi_two_heuristics(0.0, RHO, KAPPA) == 0.0

    def test_p_critical_is_where_the_lyapunov_exponent_vanishes(self) -> None:
        pc = p_critical(RHO, KAPPA)
        assert pc == pytest.approx(0.2802, abs=1e-4)
        assert lyapunov_exponent(pc, RHO, KAPPA) == pytest.approx(0.0, abs=1e-12)
        assert lyapunov_exponent(pc - 0.01, RHO, KAPPA) < 0
        assert lyapunov_exponent(pc + 0.01, RHO, KAPPA) > 0

    def test_alpha_vanishes_at_and_beyond_p_critical(self) -> None:
        pc = p_critical(RHO, KAPPA)
        assert alpha_two_heuristics(pc, RHO, KAPPA) == 0.0
        assert xi_two_heuristics(pc, RHO, KAPPA) == float("inf")

    def test_alpha_is_strictly_decreasing_and_xi_strictly_increasing(self) -> None:
        ps = np.linspace(0.005, 0.27, 40)
        alphas = [alpha_two_heuristics(float(p), RHO, KAPPA) for p in ps]
        xis = [xi_two_heuristics(float(p), RHO, KAPPA) for p in ps]
        assert all(b < a for a, b in pairwise(alphas))
        assert all(b > a for a, b in pairwise(xis))

    def test_small_p_asymptotic(self) -> None:
        """Theorem 5(v): alpha(p) ~ log(1/p)/log(kappa) as p -> 0."""
        for p in (1e-6, 1e-8, 1e-10):
            ratio = alpha_two_heuristics(p, RHO, KAPPA) / (np.log(1 / p) / np.log(KAPPA))
            assert ratio == pytest.approx(1.0, abs=0.12)

    def test_xi_vanishes_only_logarithmically(self) -> None:
        """The discussion's point: an 'almost algorithmic' model still has a measurable tail."""
        assert xi_two_heuristics(1e-4, RHO, KAPPA) > 0.09

    @pytest.mark.parametrize("bad", [(-0.1, 2.5), (1.0, 2.5), (0.7, 0.9), (0.7, 1.0)])
    def test_invalid_parameters_raise(self, bad: tuple[float, float]) -> None:
        with pytest.raises(ValueError):
            p_critical(*bad)

    def test_p_outside_the_unit_interval_raises(self) -> None:
        with pytest.raises(ValueError, match=r"p must lie in \[0, 1\]"):
            alpha_two_heuristics(1.5, RHO, KAPPA)


class TestSimulationAgainstTheory:
    def test_contractive_case_matches_the_exact_step_scale(self) -> None:
        """Theorem 5(iii) with a = rho fixed: the increment is Gaussian with a known variance."""
        tr = simulate(0.0, n_traces=4000, n_steps=64, d=8, sigma=1.0, seed=1)
        rng = np.random.default_rng(0)
        expected = stationary_step_scale(RHO) * np.mean(
            np.linalg.norm(rng.normal(size=(200_000, 8)), axis=1)
        )
        assert tr.z.mean() == pytest.approx(expected, rel=0.02)

    def test_contractive_case_has_no_measurable_tail(self) -> None:
        tr = simulate(0.0, n_traces=3000, n_steps=64, seed=1)
        z, _ = tr.pooled()
        k = 4_000
        assert moment(z, k) < 0.05, "the moment estimator must not see a tail at p = 0"
        assert hill(z, k) < 0.15, "Hill is biased upward but must stay small"

    @pytest.mark.parametrize("p", [0.02, 0.05, 0.10])
    def test_hill_recovers_the_closed_form_index(self, p: float) -> None:
        cfg = KestenConfig(n_traces=3000, n_steps=64)
        tr = simulate(p, cfg)
        z, _ = tr.pooled()
        from onebigjump.stats import select_k

        k = select_k(z, "double_bootstrap", k_min=20, k_max_frac=0.25, resamples=60).k
        assert hill(z, k) == pytest.approx(tr.xi_theory, abs=0.05)

    def test_the_tail_gets_heavier_with_p(self) -> None:
        gammas = []
        for p in (0.0, 0.02, 0.05, 0.10):
            z, _ = simulate(p, n_traces=1500, n_steps=64, seed=3).pooled()
            gammas.append(hill(z, 3_000))
        assert all(b > a for a, b in pairwise(gammas))


class TestTraceBookkeeping:
    @pytest.fixture(scope="class")
    def traces(self):
        return simulate(0.05, KestenConfig(n_traces=2000, n_steps=64))

    def test_shapes_and_pooling(self, traces) -> None:
        assert traces.z.shape == (2000, 64)
        z, g = traces.pooled()
        assert z.size == 2000 * 64
        assert np.unique(g).size == 2000
        np.testing.assert_allclose(z[:64], traces.z[0])

    def test_first_exceedance_is_the_first_one(self, traces) -> None:
        tau = traces.tolerance(0.999)
        t_star = traces.first_exceedance(tau)
        for i in np.flatnonzero(t_star >= 0)[:50]:
            t = t_star[i]
            assert traces.z[i, t] > tau
            assert np.all(traces.z[i, :t] <= tau)

    def test_verified_traces_are_marked_minus_one(self, traces) -> None:
        tau = traces.tolerance(0.999)
        t_star = traces.first_exceedance(tau)
        for i in np.flatnonzero(t_star < 0)[:50]:
            assert traces.z[i].max() <= tau

    def test_localization_is_far_above_chance(self, traces) -> None:
        """P2 on the model where the answer is known: T^max = t* at a rate near the theory's 0.85."""
        tau = traces.tolerance(0.999)
        t_star = traces.first_exceedance(tau)
        refuted = t_star >= 0
        top1 = float(np.mean(traces.argmax_step()[refuted] == t_star[refuted]))
        assert top1 > 0.7
        assert top1 > 20 * (1.0 / traces.n_steps)

    def test_multipliers_are_the_two_heuristics_at_the_right_rate(self, traces) -> None:
        assert set(np.unique(traces.a)) == {RHO, KAPPA}
        assert float(np.mean(traces.a == KAPPA)) == pytest.approx(0.05, abs=0.01)

    def test_reproducible_given_the_seed(self) -> None:
        a = simulate(0.05, n_traces=100, n_steps=16, seed=99)
        b = simulate(0.05, n_traces=100, n_steps=16, seed=99)
        np.testing.assert_array_equal(a.z, b.z)

    def test_different_rates_are_independent_streams(self) -> None:
        a = simulate(0.05, n_traces=100, n_steps=16, seed=99)
        b = simulate(0.10, n_traces=100, n_steps=16, seed=99)
        assert not np.allclose(a.z, b.z)
