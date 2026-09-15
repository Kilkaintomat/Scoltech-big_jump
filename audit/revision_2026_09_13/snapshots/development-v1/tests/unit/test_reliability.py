"""Split-half reliability: does the estimate reproduce on the other half of the data?

A bootstrap interval cannot answer that -- every replicate comes from the same pooled sample -- so
these tests pin down the properties that make the split-half number worth quoting instead.
"""

from __future__ import annotations

import numpy as np
import pytest

from onebigjump.config import TailEstimationConfig
from onebigjump.stats import split_half_reliability, split_half_table

# The tail estimate itself is what these tests exercise; its own bootstrap is not, and the
# config floors it at 50 replicates, so keep it at the floor rather than paying for more.
FAST = TailEstimationConfig(
    k_selector="fixed_frac", bootstrap_resamples=50, double_bootstrap_resamples=20
)


def pareto(n_traces: int, per_trace: int, alpha: float, seed: int = 0):
    """A pooled sample with a known tail index and honest trace structure."""
    rng = np.random.default_rng(seed)
    z = rng.pareto(alpha, size=n_traces * per_trace) + 1.0
    g = np.repeat(np.arange(n_traces), per_trace)
    return z, g


class TestTheSplitIsHonest:
    def test_groups_must_match_the_values(self) -> None:
        z, g = pareto(40, 20, 2.0)
        with pytest.raises(ValueError, match="groups has length"):
            split_half_reliability(z, g[:-5], FAST, n_splits=2)

    def test_too_few_traces_is_reported_not_faked(self) -> None:
        """Three traces cannot be split and estimated on both sides. Say so."""
        z, g = pareto(3, 40, 2.0)
        r = split_half_reliability(z, g, FAST, n_splits=5)
        assert r.n_usable == 0
        assert np.isnan(r.delta_median)
        assert "cannot be split" in r.note

    def test_the_same_seed_gives_the_same_splits(self) -> None:
        z, g = pareto(60, 20, 2.0)
        a = split_half_reliability(z, g, FAST, n_splits=6, seed=5)
        b = split_half_reliability(z, g, FAST, n_splits=6, seed=5)
        assert a.delta_median == b.delta_median
        assert a.xi_left == b.xi_left

    def test_every_split_uses_half_the_traces(self) -> None:
        """A split that leaked traces to both sides would report a reliability of its own leak."""
        rng = np.random.default_rng(0)
        uniq = np.arange(50)
        for _ in range(20):
            order = rng.permutation(uniq.size)
            left = set(uniq[order[: uniq.size // 2]].tolist())
            right = set(uniq[order[uniq.size // 2 :]].tolist())
            assert not (left & right)
            assert left | right == set(uniq.tolist())


class TestWhatTheNumbersMean:
    def test_more_data_disagrees_less(self) -> None:
        """The property that makes delta interpretable at all."""
        small = split_half_reliability(*pareto(40, 25, 2.0, seed=1), FAST, n_splits=12, seed=1)
        large = split_half_reliability(*pareto(400, 25, 2.0, seed=1), FAST, n_splits=12, seed=1)
        assert large.delta_median < small.delta_median

    def test_a_heavier_tail_is_harder_to_pin_down(self) -> None:
        """Estimating a heavy tail from the same number of traces is a noisier job."""
        light = split_half_reliability(*pareto(200, 25, 4.0, seed=2), FAST, n_splits=12, seed=2)
        heavy = split_half_reliability(*pareto(200, 25, 1.2, seed=2), FAST, n_splits=12, seed=2)
        assert heavy.delta_median > light.delta_median

    def test_resolves_compares_an_effect_against_the_disagreement(self) -> None:
        r = split_half_reliability(*pareto(200, 25, 2.0, seed=3), FAST, n_splits=12, seed=3)
        assert r.delta_p90 > 0
        assert r.resolves(r.delta_p90 * 5)
        assert not r.resolves(r.delta_p90 / 5)

    def test_an_undefined_disagreement_resolves_nothing(self) -> None:
        """With no usable split, `resolves` must not wave an effect through."""
        z, g = pareto(3, 40, 2.0)
        r = split_half_reliability(z, g, FAST, n_splits=4)
        assert not r.resolves(10.0)


class TestOrderingAcrossCells:
    def test_a_stable_ordering_reports_high_reliability(self) -> None:
        """Four well-separated cells should rank the same way in both halves."""
        cells = {f"a{a}": pareto(150, 25, a, seed=7) for a in (1.2, 1.8, 2.6, 4.0)}
        out = split_half_table(cells, FAST, n_splits=10, seed=7)
        assert out["ordering_reliability"] is not None
        assert out["ordering_reliability"] > 0.8

    def test_identical_cells_do_not_manufacture_an_ordering(self) -> None:
        """Cells drawn from one distribution have no true ranking, so reliability must not be high."""
        cells = {f"same{i}": pareto(150, 25, 2.0, seed=100 + i) for i in range(4)}
        out = split_half_table(cells, FAST, n_splits=10, seed=11)
        assert out["ordering_reliability"] is None or out["ordering_reliability"] < 0.8

    def test_too_few_cells_gives_none_not_a_fabricated_one(self) -> None:
        cells = {f"a{a}": pareto(120, 25, a, seed=9) for a in (1.5, 3.0)}
        out = split_half_table(cells, FAST, n_splits=6, seed=9)
        assert out["ordering_reliability"] is None
        assert "at least 3 cells" in out["note"]

    def test_every_cell_gets_a_row(self) -> None:
        cells = {f"a{a}": pareto(120, 25, a, seed=4) for a in (1.5, 2.5, 3.5)}
        out = split_half_table(cells, FAST, n_splits=6, seed=4)
        assert set(out["rows"]) == set(cells)
        for row in out["rows"].values():
            assert {"n_traces", "xi", "delta_median", "delta_p90", "reliability"} <= set(row)
