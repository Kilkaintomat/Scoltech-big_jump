"""Calibration and the three deviation statistics of equation 1."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from onebigjump.models.activations import (
    Calibration,
    Trajectory,
    deviations,
    fit_calibration,
    ledoit_wolf_intensity,
    shrinkage_target,
)
from onebigjump.models.hooks import layer_indices

D = 16


def _trajectories(
    n_traces: int, n_steps: int = 10, *, d: int = D, seed: int = 0, cov: np.ndarray | None = None
) -> list[Trajectory]:
    rng = np.random.default_rng(seed)
    chol = np.linalg.cholesky(cov) if cov is not None else np.eye(d)
    out = []
    for i in range(n_traces):
        inc = rng.normal(size=(n_steps, d)) @ chol.T
        states = np.vstack([np.zeros(d), np.cumsum(inc, axis=0)])
        out.append(Trajectory(f"t{i}", 0, states, np.zeros(n_steps), n_steps, d))
    return out


def _correlated(d: int = D, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(d, d))
    return a @ a.T / d + np.eye(d) * 0.1


class TestLayerIndices:
    def test_the_paper_reads_out_at_quarter_half_and_three_quarters(self) -> None:
        assert layer_indices(32, (0.25, 0.5, 0.75)) == [8, 16, 24]
        assert layer_indices(12, (0.25, 0.5, 0.75)) == [3, 6, 9]

    def test_floor_is_used_and_the_range_is_clamped(self) -> None:
        assert layer_indices(10, (0.25, 0.5, 0.75)) == [2, 5, 7]
        assert layer_indices(4, (0.0, 1.0, 2.0)) == [0, 3]

    def test_duplicates_collapse(self) -> None:
        assert layer_indices(2, (0.25, 0.4, 0.49)) == [0]


class TestShrinkageTarget:
    def test_identity_target_is_a_scaled_identity(self) -> None:
        cov = np.diag([1.0, 4.0, 7.0])
        t = shrinkage_target(cov, "identity")
        assert np.allclose(t, np.eye(3) * 4.0)

    def test_diagonal_target_keeps_each_variance(self) -> None:
        cov = np.array([[2.0, 0.5], [0.5, 8.0]])
        assert np.allclose(shrinkage_target(cov, "diagonal"), np.diag([2.0, 8.0]))

    def test_unknown_target_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown shrinkage target"):
            shrinkage_target(np.eye(2), "eyeball")


class TestShrinkageIntensity:
    def test_near_full_shrinkage_when_the_target_is_the_truth(self) -> None:
        """Uncorrelated increments make the diagonal target exact, so the optimum sits near 1."""
        assert fit_calibration(_trajectories(600)).shrinkage > 0.8

    def test_less_shrinkage_when_the_data_are_correlated(self) -> None:
        trs = _trajectories(600, cov=_correlated())
        assert fit_calibration(trs).shrinkage < 0.2

    def test_shrinkage_falls_as_the_sample_grows(self) -> None:
        cov = _correlated()
        small = fit_calibration(_trajectories(50, cov=cov)).shrinkage
        large = fit_calibration(_trajectories(1000, cov=cov)).shrinkage
        assert large < small

    def test_a_pinned_intensity_is_honoured(self) -> None:
        assert fit_calibration(_trajectories(200), shrinkage=0.3).shrinkage == pytest.approx(0.3)

    def test_the_intensity_is_a_probability(self) -> None:
        trs = _trajectories(200, cov=_correlated())
        inc = np.concatenate([t.increments() for t in trs])
        centred = inc - inc.mean(axis=0)
        cov = np.cov(centred.T)
        for target in ("diagonal", "identity"):
            assert 0.0 <= ledoit_wolf_intensity(centred, cov, target) <= 1.0


class TestWhitening:
    def test_whitened_increments_have_identity_covariance(self) -> None:
        trs = _trajectories(1000, cov=_correlated())
        cal = fit_calibration(trs)
        w = np.concatenate([cal.whiten(t.increments()) for t in trs])
        c = np.cov(w.T)
        assert np.mean(np.diag(c)) == pytest.approx(1.0, abs=0.05)
        assert np.max(np.abs(c - np.diag(np.diag(c)))) < 0.15

    def test_the_identity_target_distorts_an_anisotropic_covariance(self) -> None:
        """Why `diagonal` is the default: massive activations break the scaled-identity target."""
        scale = np.ones(D)
        scale[:2] = 50.0
        trs = _trajectories(1000, cov=np.diag(scale**2))
        diag_cal = fit_calibration(trs, target="diagonal")
        id_cal = fit_calibration(trs, target="identity")
        diag_var = np.mean(
            np.diag(np.cov(np.concatenate([diag_cal.whiten(t.increments()) for t in trs]).T))
        )
        id_var = np.mean(
            np.diag(np.cov(np.concatenate([id_cal.whiten(t.increments()) for t in trs]).T))
        )
        assert diag_var == pytest.approx(1.0, abs=0.05)
        assert id_var < 0.95

    def test_whitening_removes_anisotropy_without_removing_spread(self) -> None:
        scale = np.ones(D)
        scale[:2] = 50.0
        trs = _trajectories(600, cov=np.diag(scale**2))
        cal = fit_calibration(trs)
        raw = np.concatenate([deviations(t, cal)["raw"] for t in trs])
        wht = np.concatenate([deviations(t, cal)["whitened"] for t in trs])
        assert raw.std() / raw.mean() > wht.std() / wht.mean()
        assert wht.std() > 0


class TestUnderdeterminedGuard:
    def test_too_few_increments_is_refused(self) -> None:
        """Measured on GPT-2: 12 increments in 768 dims gave near-constant whitened norms."""
        with pytest.raises(ValueError, match="under-determined whitening"):
            fit_calibration(_trajectories(2, n_steps=4))

    def test_it_can_be_overridden_deliberately(self) -> None:
        cal = fit_calibration(_trajectories(2, n_steps=4), allow_underdetermined=True)
        assert cal.increments_per_dim < 1.0

    def test_the_ratio_is_reported(self) -> None:
        cal = fit_calibration(_trajectories(100, n_steps=10))
        assert cal.increments_per_dim == pytest.approx(1000 / D)
        assert cal.summary()["increments_per_dim"] == cal.increments_per_dim


class TestDeviations:
    @pytest.fixture(scope="class")
    def calibrated(self):
        trs = _trajectories(400, cov=_correlated())
        return trs, fit_calibration(trs, source="unit-test")

    def test_all_three_statistics_are_produced(self, calibrated) -> None:
        trs, cal = calibrated
        d = deviations(trs[0], cal)
        assert set(d) == {"raw", "whitened", "innovation"}
        assert all(v.shape == (trs[0].n_steps,) for v in d.values())
        assert all(np.all(v >= 0) for v in d.values())

    def test_without_a_calibration_only_raw_is_returned(self, calibrated) -> None:
        trs, _ = calibrated
        assert set(deviations(trs[0])) == {"raw"}

    def test_raw_is_the_increment_norm(self, calibrated) -> None:
        trs, _ = calibrated
        np.testing.assert_allclose(
            deviations(trs[0])["raw"], np.linalg.norm(trs[0].increments(), axis=1)
        )

    def test_a_layer_mismatch_is_refused(self, calibrated) -> None:
        trs, cal = calibrated
        other = Trajectory("x", 7, trs[0].states, trs[0].surprisal, trs[0].n_steps, D)
        with pytest.raises(ValueError, match="calibration is for layer"):
            deviations(other, cal)

    def test_innovation_is_small_for_a_predictable_trajectory(self) -> None:
        """A pure random walk has X_t = X_{t-1} + noise, so the ridge fit leaves only the noise."""
        trs = _trajectories(400)
        cal = fit_calibration(trs)
        inn = np.concatenate([deviations(t, cal)["innovation"] for t in trs])
        raw = np.concatenate([deviations(t, cal)["raw"] for t in trs])
        assert inn.mean() == pytest.approx(raw.mean(), rel=0.15)


class TestPersistence:
    def test_round_trip(self, tmp_path: Path) -> None:
        cal = fit_calibration(_trajectories(300, cov=_correlated()), source="unit-test")
        back = Calibration.load(cal.save(tmp_path / "c.npz"))
        for attr in ("layer", "n_increments", "shrinkage", "ridge_alpha", "source", "target"):
            assert getattr(back, attr) == getattr(cal, attr)
        for attr in ("mean", "whitener", "ridge_a", "ridge_c"):
            np.testing.assert_allclose(getattr(back, attr), getattr(cal, attr))

    def test_the_summary_is_json_safe(self) -> None:
        import json

        json.loads(json.dumps(fit_calibration(_trajectories(300)).summary()))


class TestValidation:
    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="no trajectories"):
            fit_calibration([])

    def test_mixed_layers_raise(self) -> None:
        trs = _trajectories(300)
        trs[5].layer = 3
        with pytest.raises(ValueError, match="same layer"):
            fit_calibration(trs)
