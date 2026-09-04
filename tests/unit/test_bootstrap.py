"""Trace bootstrap and the cluster variance of Theorem 6(ii)."""

from __future__ import annotations

import numpy as np
import pytest

from onebigjump.stats import cluster_variance, effective_sample, group_bootstrap, hill

M, L = 1500, 40


@pytest.fixture(scope="module")
def independent() -> tuple[np.ndarray, np.ndarray]:
    """Traces whose steps are independent: Theorem 6 says sigma_cl^2 = 1 exactly."""
    rng = np.random.default_rng(11)
    z = (rng.pareto(2.0, (M, L)) + 1.0).ravel()
    return z, np.repeat(np.arange(M), L)


@pytest.fixture(scope="module")
def clustered() -> tuple[np.ndarray, np.ndarray]:
    """Each trace's largest step is followed by a geometric relaxation, as in Theorem 5."""
    rng = np.random.default_rng(11)
    z = rng.pareto(2.0, (M, L)) + 1.0
    for j in range(M):
        i = int(np.argmax(z[j]))
        for d in (1, 2):
            if i + d < L:
                z[j, i + d] = z[j, i] * 0.9**d
    return z.ravel(), np.repeat(np.arange(M), L)


class TestClusterVariance:
    def test_is_one_for_independent_steps(self, independent) -> None:
        z, g = independent
        assert cluster_variance(z, g, 3_000)["sigma2_cl"] == pytest.approx(1.0, abs=0.15)

    def test_exceeds_one_when_large_steps_cluster(self, clustered) -> None:
        z, g = clustered
        assert cluster_variance(z, g, 3_000)["sigma2_cl"] > 1.5

    def test_effective_sample_deflates_k(self) -> None:
        assert effective_sample(2.5, 1_000) == pytest.approx(400.0)
        assert np.isnan(effective_sample(float("nan"), 1_000))
        assert np.isnan(effective_sample(-1.0, 1_000))


class TestResamplingUnit:
    def test_step_resampling_understates_the_variance_by_sigma2_cl(self, clustered) -> None:
        """Section 4: resampling steps destroys the clusters and underestimates by sigma_cl^2."""
        z, g = clustered
        k = 3_000
        s2 = cluster_variance(z, g, k)["sigma2_cl"]
        by_trace = group_bootstrap(z, g, hill, k=k, resamples=300, seed=1, unit="trace")
        by_step = group_bootstrap(z, g, hill, k=k, resamples=300, seed=1, unit="step")
        assert by_trace.se > by_step.se
        assert (by_trace.se / by_step.se) ** 2 == pytest.approx(s2, rel=0.3)

    def test_the_two_units_agree_when_there_are_no_clusters(self, independent) -> None:
        z, g = independent
        k = 3_000
        by_trace = group_bootstrap(z, g, hill, k=k, resamples=300, seed=1, unit="trace")
        by_step = group_bootstrap(z, g, hill, k=k, resamples=300, seed=1, unit="step")
        assert (by_trace.se / by_step.se) ** 2 == pytest.approx(1.0, abs=0.35)


class TestIntervals:
    def test_the_interval_covers_the_truth(self, independent) -> None:
        z, g = independent
        b = group_bootstrap(z, g, hill, k=3_000, resamples=400, seed=2)
        assert b.ci_low < 0.5 < b.ci_high
        assert b.n_valid > 350

    def test_the_point_estimate_is_the_full_sample_one(self, independent) -> None:
        z, g = independent
        b = group_bootstrap(z, g, hill, k=3_000, resamples=50, seed=2)
        assert b.estimate == pytest.approx(hill(z, 3_000))

    def test_the_tail_fraction_is_held_fixed_not_k(self, independent) -> None:
        """A resample of a different size must use k' = round(k/n * n'), per Section 4."""
        z, g = independent
        b = group_bootstrap(z, g, hill, k=3_000, resamples=100, seed=3, m_out=400)
        assert b.n_valid > 90
        assert b.se > group_bootstrap(z, g, hill, k=3_000, resamples=100, seed=3).se

    def test_a_wider_level_gives_a_wider_interval(self, independent) -> None:
        z, g = independent
        narrow = group_bootstrap(z, g, hill, k=3_000, resamples=300, seed=4, level=0.80)
        wide = group_bootstrap(z, g, hill, k=3_000, resamples=300, seed=4, level=0.99)
        assert wide.ci_high - wide.ci_low > narrow.ci_high - narrow.ci_low


class TestInputHandling:
    def test_mismatched_groups_raise(self) -> None:
        with pytest.raises(ValueError, match="groups has length"):
            group_bootstrap(np.arange(1.0, 100.0), np.arange(5), hill, k=10)

    def test_too_few_observations_raise(self) -> None:
        with pytest.raises(ValueError, match="at least 10"):
            group_bootstrap(np.arange(1.0, 5.0), None, hill, k=2)
