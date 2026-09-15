"""The single call that fills one cell of Table 1."""

from __future__ import annotations

import json

import numpy as np
import pytest

from onebigjump.config import TailEstimationConfig
from onebigjump.stats import estimate_tail

FAST = TailEstimationConfig(bootstrap_resamples=80, double_bootstrap_resamples=50)


def _traces(law: str, m: int = 800, L: int = 40, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    if law == "pareto":
        z = rng.pareto(2.5, (m, L)) + 1.0  # gamma = 0.4
    elif law == "exponential":
        z = rng.exponential(1.0, (m, L))  # gamma = 0
    else:  # pragma: no cover
        raise ValueError(law)
    return z.ravel(), np.repeat(np.arange(m), L)


class TestHeavyTail:
    @pytest.fixture(scope="class")
    def est(self):
        z, g = _traces("pareto")
        return estimate_tail(z, g, FAST, seed=0, with_hill_plot=True)

    def test_all_three_estimators_recover_gamma(self, est) -> None:
        for value in (est.hill, est.moment, est.gpd):
            assert value == pytest.approx(0.4, abs=0.06)

    def test_intervals_cover_the_truth(self, est) -> None:
        for name in ("hill", "moment", "gpd"):
            b = est.boot[name]
            assert b["ci_low"] < 0.4 < b["ci_high"], name

    def test_the_tail_is_reported_as_identified_and_heavy(self, est) -> None:
        assert est.identification["identified"]
        assert est.comparison["favours"].startswith("heavy")

    def test_cluster_variance_is_about_one_for_independent_steps(self, est) -> None:
        assert est.cluster["sigma2_cl"] == pytest.approx(1.0, abs=0.25)
        assert est.cluster["effective_k"] == pytest.approx(est.k, rel=0.3)

    def test_the_order_parameter_is_positive(self, est) -> None:
        assert est.xi > 0.3

    def test_counts_are_right(self, est) -> None:
        assert est.n == 800 * 40
        assert est.n_traces == 800
        assert 20 <= est.k <= 0.25 * est.n


class TestLightTail:
    @pytest.fixture(scope="class")
    def est(self):
        z, g = _traces("exponential")
        return estimate_tail(z, g, FAST, seed=0, with_hill_plot=False)

    def test_the_order_parameter_is_about_zero(self, est) -> None:
        assert est.xi < 0.1, "an exponential must not be read as a heavy tail"

    def test_hill_alone_would_have_been_misleading(self, est) -> None:
        assert est.hill > est.moment + 0.1

    def test_non_rejection_of_exponential_is_inconclusive(self, est) -> None:
        assert est.comparison["favours"] == "inconclusive"

    def test_it_is_not_identified_as_a_tail(self, est) -> None:
        assert not est.identification["identified"]


class TestPlumbing:
    def test_the_row_has_the_columns_table_one_needs(self) -> None:
        z, g = _traces("pareto", m=300, L=20)
        row = estimate_tail(z, g, FAST, meta={"model": "toy"}, with_hill_plot=False).row()
        for col in (
            "m_traces",
            "n_steps",
            "k",
            "hill",
            "hill_lo",
            "hill_hi",
            "moment",
            "gpd",
            "xi",
            "sigma2_cl",
            "favours",
            "identified",
        ):
            assert col in row
        assert row["meta_model"] == "toy"

    def test_the_result_is_json_serialisable(self) -> None:
        z, g = _traces("pareto", m=300, L=20)
        est = estimate_tail(z, g, FAST, with_hill_plot=True)
        json.loads(json.dumps(est.as_dict()))

    def test_it_is_reproducible(self) -> None:
        z, g = _traces("pareto", m=300, L=20)
        a = estimate_tail(z, g, FAST, seed=7, with_hill_plot=False)
        b = estimate_tail(z, g, FAST, seed=7, with_hill_plot=False)
        assert (a.k, a.hill, a.boot["hill"]["se"]) == (b.k, b.hill, b.boot["hill"]["se"])

    def test_restricting_the_estimator_list_is_honoured(self) -> None:
        z, g = _traces("pareto", m=300, L=20)
        cfg = TailEstimationConfig(
            estimators=["hill"], bootstrap_resamples=50, double_bootstrap_resamples=50
        )
        est = estimate_tail(z, g, cfg, with_hill_plot=False)
        assert set(est.boot) == {"hill"}

    def test_non_positive_values_are_dropped_not_fatal(self) -> None:
        z, g = _traces("pareto", m=300, L=20)
        z = z.copy()
        z[::50] = 0.0
        est = estimate_tail(z, g, FAST, with_hill_plot=False)
        assert est.n == 300 * 20 - z[::50].size

    def test_mismatched_groups_raise(self) -> None:
        z, _ = _traces("pareto", m=100, L=10)
        with pytest.raises(ValueError, match="groups has length"):
            estimate_tail(z, np.arange(5), FAST)

    def test_a_tiny_sample_raises_rather_than_inventing_a_tail(self) -> None:
        with pytest.raises(ValueError, match="too few positive deviations"):
            estimate_tail(np.random.default_rng(0).pareto(2.0, 30) + 1.0, None, FAST)
