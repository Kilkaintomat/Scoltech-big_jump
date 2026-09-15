"""Extremal index: theta = 1 without clustering, theta < 1 with it."""

from __future__ import annotations

import numpy as np
import pytest

from onebigjump.stats import extremal_index, traces_from_groups

METHODS = ["intervals", "blocks", "runs"]


@pytest.fixture(scope="module")
def iid_traces() -> list[np.ndarray]:
    rng = np.random.default_rng(2)
    return [rng.pareto(2.0, 200) + 1.0 for _ in range(600)]


@pytest.fixture(scope="module")
def moving_max_traces() -> list[np.ndarray]:
    """X_t = max(Y_t, Y_{t-1}) with iid heavy Y has extremal index exactly 1/2."""
    rng = np.random.default_rng(2)
    out = []
    for _ in range(600):
        y = rng.pareto(2.0, 201) + 1.0
        out.append(np.maximum(y[1:], y[:-1]))
    return out


@pytest.mark.parametrize("method", METHODS)
def test_iid_gives_theta_one(iid_traces: list[np.ndarray], method: str) -> None:
    est = extremal_index(iid_traces, quantile=0.98, method=method)
    assert est.theta == pytest.approx(1.0, abs=0.15)


@pytest.mark.parametrize("method", METHODS)
def test_moving_maximum_gives_theta_one_half(
    moving_max_traces: list[np.ndarray], method: str
) -> None:
    est = extremal_index(moving_max_traces, quantile=0.98, method=method)
    assert est.theta == pytest.approx(0.5, abs=0.12)


def test_clustering_lowers_theta(iid_traces, moving_max_traces) -> None:
    a = extremal_index(iid_traces, quantile=0.98).theta
    b = extremal_index(moving_max_traces, quantile=0.98).theta
    assert b < a


def test_theta_never_exceeds_one(moving_max_traces: list[np.ndarray]) -> None:
    for m in METHODS:
        assert extremal_index(moving_max_traces, quantile=0.9, method=m).theta <= 1.0


def test_explicit_threshold_overrides_the_quantile(iid_traces: list[np.ndarray]) -> None:
    est = extremal_index(iid_traces, threshold=5.0)
    assert est.threshold == 5.0
    assert est.n_exceedances == sum(int(np.sum(t > 5.0)) for t in iid_traces)


def test_traces_from_groups_restores_step_order() -> None:
    z = np.array([1.0, 2.0, 3.0, 10.0, 20.0])
    g = np.array(["a", "a", "a", "b", "b"])
    order = np.array([2, 0, 1, 1, 0])
    got = traces_from_groups(z, g, order)
    np.testing.assert_allclose(got[0], [2.0, 3.0, 1.0])
    np.testing.assert_allclose(got[1], [20.0, 10.0])


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        traces_from_groups(np.arange(5.0), np.arange(3))


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError, match="no non-empty traces"):
        extremal_index([])
