"""Choice of k: the double bootstrap, the KS criterion and the plateau rule."""

from __future__ import annotations

import numpy as np
import pytest

from onebigjump.stats import (
    double_bootstrap_k,
    hill,
    ks_distance_k,
    plateau_k,
    select_k,
)


@pytest.fixture(scope="module")
def pareto() -> np.ndarray:
    return np.random.default_rng(5).pareto(2.0, 100_000) + 1.0


@pytest.fixture(scope="module")
def student() -> np.ndarray:
    """|t_3| has a genuine second-order bias, so the AMSE has an interior minimum."""
    return np.abs(np.random.default_rng(6).standard_t(3, 200_000))


class TestDoubleBootstrap:
    def test_returns_a_usable_k_on_a_biased_tail(self, student: np.ndarray) -> None:
        sel = double_bootstrap_k(student, resamples=100, seed=0)
        assert sel.method == "double_bootstrap"
        assert 20 < sel.k < student.size // 2
        assert sel.diagnostics["k2_star"] < sel.diagnostics["k1_star"]

    def test_the_selected_k_estimates_the_index(self, student: np.ndarray) -> None:
        sel = double_bootstrap_k(student, resamples=200, seed=0)
        assert hill(student, sel.k) == pytest.approx(1 / 3, abs=0.06)

    def test_stage_sizes_follow_the_paper(self, pareto: np.ndarray) -> None:
        sel = double_bootstrap_k(pareto, resamples=50, n1_exponent=0.9, seed=0)
        n = pareto.size
        assert sel.diagnostics["n1"] == pytest.approx(n**0.9, rel=1e-3)
        assert sel.diagnostics["n2"] == pytest.approx(sel.diagnostics["n1"] ** 2 / n, rel=1e-3)

    def test_small_samples_fall_back_instead_of_failing(self) -> None:
        z = np.random.default_rng(0).pareto(2.0, 40) + 1.0
        sel = double_bootstrap_k(z, resamples=10, seed=0)
        assert sel.method.endswith("fallback")
        assert sel.diagnostics["reason"]

    def test_it_is_reproducible(self, student: np.ndarray) -> None:
        a = double_bootstrap_k(student, resamples=50, seed=42)
        b = double_bootstrap_k(student, resamples=50, seed=42)
        assert a.k == b.k


class TestKS:
    def test_selected_k_estimates_the_index(self, pareto: np.ndarray) -> None:
        sel = ks_distance_k(pareto)
        assert hill(pareto, sel.k) == pytest.approx(0.5, abs=0.05)

    def test_distance_is_small_for_a_true_pareto(self, pareto: np.ndarray) -> None:
        assert ks_distance_k(pareto).objective < 0.02


class TestPlateau:
    def test_flags_a_pareto_as_stable(self, pareto: np.ndarray) -> None:
        sel = plateau_k(pareto)
        assert sel.diagnostics["stable"]
        assert hill(pareto, sel.k) == pytest.approx(0.5, abs=0.05)

    def test_flags_an_exponential_as_unstable(self) -> None:
        z = np.random.default_rng(8).exponential(1.0, 100_000)
        assert (
            plateau_k(z).objective
            > plateau_k(np.random.default_rng(8).pareto(2.0, 100_000) + 1).objective
        )


class TestSelectK:
    @pytest.mark.parametrize("method", ["double_bootstrap", "ks", "plateau", "fixed_frac"])
    def test_every_method_respects_the_bounds(self, pareto: np.ndarray, method: str) -> None:
        sel = select_k(pareto, method, k_min=50, k_max_frac=0.1, resamples=30)
        assert 50 <= sel.k <= 0.1 * pareto.size

    def test_clipping_is_recorded(self, pareto: np.ndarray) -> None:
        sel = select_k(pareto, "fixed_frac", fixed_frac=0.4, k_min=20, k_max_frac=0.05)
        assert sel.k == pytest.approx(0.05 * pareto.size, rel=0.01)
        assert "k_before_clip" in sel.diagnostics

    def test_unknown_method_raises(self, pareto: np.ndarray) -> None:
        with pytest.raises(ValueError, match="unknown k selector"):
            select_k(pareto, "nonsense")  # type: ignore[arg-type]

    def test_selection_is_serialisable(self, pareto: np.ndarray) -> None:
        import json

        d = select_k(pareto, "ks").as_dict()
        assert set(d) == {"k", "method", "n", "objective", "diagnostics"}
        json.loads(json.dumps(d))
