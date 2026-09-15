"""The modular-addition transformer, its progress measures, and the P4 machinery."""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.ml

P = 17  # a small prime keeps these tests fast; the paper's setting is p = 113


@pytest.fixture(scope="module")
def data():
    from onebigjump.models.grokking import make_data

    return make_data(p=P, train_frac=0.3, seed=0)


@pytest.fixture(scope="module")
def model():
    from onebigjump.models.grokking import build_model

    return build_model(p=P, d_model=32, n_heads=4, d_mlp=64, seed=0)


class TestData:
    def test_every_pair_appears_exactly_once(self, data) -> None:
        assert data.n == P * P
        pairs = {(int(a), int(b)) for a, b, _ in data.inputs}
        assert len(pairs) == P * P

    def test_the_equals_token_closes_every_input(self, data) -> None:
        assert (data.inputs[:, 2] == P).all()

    def test_targets_are_the_modular_sum(self, data) -> None:
        a, b = data.inputs[:, 0], data.inputs[:, 1]
        assert ((a + b) % P == data.targets).all()

    def test_the_split_is_a_partition(self, data) -> None:
        idx = set(data.train_idx.tolist()) | set(data.test_idx.tolist())
        assert idx == set(range(P * P))
        assert not set(data.train_idx.tolist()) & set(data.test_idx.tolist())

    def test_the_split_is_reproducible(self) -> None:
        from onebigjump.models.grokking import make_data

        a = make_data(p=P, seed=3)
        b = make_data(p=P, seed=3)
        assert (a.train_idx == b.train_idx).all()


class TestModel:
    def test_logits_have_one_entry_per_residue(self, model, data) -> None:
        assert model(data.inputs).shape == (P * P, P)

    def test_no_layer_normalisation(self, model) -> None:
        """B.5 follows Nanda et al.: no LN. It would rescale the very norm P4 measures."""
        import torch

        assert not any(isinstance(m, torch.nn.LayerNorm) for m in model.modules())

    def test_the_block_increment_is_the_residual_difference(self, model, data) -> None:
        import torch

        with torch.no_grad():
            h0 = model.residual_in(data.inputs[:8])
            h1 = model.block(h0)
            got = model.block_increment(data.inputs[:8])
        torch.testing.assert_close(got, (h1 - h0)[:, -1])

    def test_the_increment_is_one_vector_per_input(self, model, data) -> None:
        assert model.block_increment(data.inputs[:20]).shape == (20, model.d_model)

    def test_it_is_causal(self, model, data) -> None:
        """Changing the last token must not change what earlier positions computed."""
        import torch

        x = data.inputs[:4].clone()
        with torch.no_grad():
            a = model.block(model.residual_in(x))[:, 0]
            x[:, 2] = (x[:, 2] + 1) % (P + 1)
            b = model.block(model.residual_in(x))[:, 0]
        torch.testing.assert_close(a, b)


class TestProgressMeasures:
    def test_an_untrained_model_sits_at_chance(self, model, data) -> None:
        from onebigjump.models.grokking import progress_measures

        pm = progress_measures(model, data, top_k=3)
        assert pm.train_acc == pytest.approx(1 / P, abs=0.05)
        assert pm.train_loss == pytest.approx(np.log(P), abs=0.5)

    def test_the_key_frequencies_are_in_range_and_exclude_the_constant(self, model) -> None:
        from onebigjump.models.grokking import key_frequencies

        freqs = key_frequencies(model, top_k=4)
        assert len(freqs) == 4
        assert all(1 <= f <= P // 2 for f in freqs)
        assert freqs == sorted(freqs)

    def test_the_measures_are_serialisable(self, model, data) -> None:
        import json

        from onebigjump.models.grokking import progress_measures

        json.loads(json.dumps(progress_measures(model, data, top_k=3).as_dict()))

    def test_restricted_and_excluded_are_both_finite(self, model, data) -> None:
        from onebigjump.models.grokking import progress_measures

        pm = progress_measures(model, data, top_k=3)
        assert np.isfinite(pm.restricted_loss)
        assert np.isfinite(pm.excluded_loss)


class TestTraining:
    def test_a_short_run_memorises_the_training_split(self) -> None:
        """The memorisation phase is fast and must be visible before any grokking claim."""
        from onebigjump.config import GrokkingConfig, TailEstimationConfig
        from onebigjump.experiments.p4_grokking import train_grokking

        cfg = GrokkingConfig(
            p=P,
            d_model=32,
            n_heads=4,
            d_mlp=64,
            steps=600,
            checkpoint_every=200,
            device="cpu",
            tail=TailEstimationConfig(bootstrap_resamples=50, double_bootstrap_resamples=50),
        )
        cps, meta = train_grokking(cfg, seed=0, full_every=0)
        assert len(cps) == 4
        assert cps[-1].train_acc > cps[0].train_acc
        assert meta["device"] == "cpu"
        assert all(c.n == P * P for c in cps)

    def test_every_checkpoint_carries_a_tail_estimate(self) -> None:
        from onebigjump.config import GrokkingConfig
        from onebigjump.experiments.p4_grokking import train_grokking

        cfg = GrokkingConfig(
            p=P, d_model=32, n_heads=4, d_mlp=64, steps=200, checkpoint_every=100, device="cpu"
        )
        cps, _ = train_grokking(cfg, seed=0, full_every=0)
        for c in cps:
            assert np.isfinite(c.hill)
            assert c.k >= 20
            assert c.median_deviation > 0

    def test_the_full_protocol_runs_at_the_requested_cadence(self) -> None:
        from onebigjump.config import GrokkingConfig, TailEstimationConfig
        from onebigjump.experiments.p4_grokking import train_grokking

        cfg = GrokkingConfig(
            p=P,
            d_model=32,
            n_heads=4,
            d_mlp=64,
            steps=300,
            checkpoint_every=100,
            device="cpu",
            tail=TailEstimationConfig(bootstrap_resamples=50, double_bootstrap_resamples=50),
        )
        cps, _ = train_grokking(cfg, seed=0, full_every=2)
        with_full = [c for c in cps if c.full is not None]
        assert len(with_full) == 2  # checkpoints 0 and 2
        assert "bootstrap" in with_full[0].full

    def test_grokking_step_finds_the_first_crossing(self) -> None:
        from onebigjump.experiments.p4_grokking import Checkpoint, grokking_step

        def cp(step: int, acc: float) -> Checkpoint:
            return Checkpoint(step, 0, 0, 0, acc, 0, 0, 0, 0, 0, 10, 10, 1.0)

        cps = [cp(0, 0.1), cp(100, 0.5), cp(200, 0.95), cp(300, 0.99)]
        assert grokking_step(cps) == 200
        assert grokking_step(cps, threshold=0.999) is None


class TestAnalysis:
    """The analysis plan asks whether the drop is *located at* the transition."""

    @staticmethod
    def _cp(
        step: int,
        gamma: float,
        test_acc: float,
        restricted: float = 1.0,
        excluded: float = 1.0,
        train_acc: float = 1.0,
    ):
        """`gamma` is the signed shape, which is what the analysis reads.

        It used to be passed as `hill`, and the analysis used to read Hill -- which is how a
        module whose whole subject is a tail index came to report a statistic that cannot be
        negative. The fixture now puts the signal where the analysis actually looks.
        """
        from onebigjump.experiments.p4_grokking import Checkpoint

        return Checkpoint(
            step=step,
            train_loss=0.0,
            test_loss=0.0,
            train_acc=train_acc,
            test_acc=test_acc,
            restricted_loss=restricted,
            excluded_loss=excluded,
            # Hill carries the same shape here only so the diagnostic fields stay populated;
            # nothing in the analysis reads it any more.
            hill=abs(gamma),
            moment=gamma,
            gpd=gamma,
            k=100,
            n=1000,
            median_deviation=1.0,
        )

    def _series(self):
        # Memorisation, a plateau, the circuit forming, then the generalization jump.
        return [
            self._cp(0, 0.03, 0.01, 10.0, 10.0, train_acc=0.01),
            self._cp(100, 0.04, 0.24, 9.0, 14.0),
            self._cp(200, 0.04, 0.24, 8.0, 14.0),
            self._cp(300, 0.17, 0.30, 7.0, 14.0),
            self._cp(400, 0.05, 0.37, 1.0, 8.0),  # progress measures turn here
            self._cp(500, 0.04, 0.95, 0.1, 7.0),  # generalization follows
            self._cp(600, 0.03, 1.00, 0.0, 6.5),
            self._cp(700, 0.03, 1.00, 0.0, 6.5),
        ]

    def test_the_transition_is_located(self) -> None:
        from onebigjump.experiments.p4_grokking import analyse_p4

        out = analyse_p4(self._series(), window=2)
        assert out["grokking_step"] == 500
        assert out["memorisation_step"] == 100

    def test_the_memorisation_jump_is_not_mistaken_for_grokking(self) -> None:
        """The largest rise in test accuracy over the whole curve is memorisation, not grokking."""
        from onebigjump.experiments.p4_grokking import analyse_p4

        out = analyse_p4(self._series(), window=2)
        assert out["test_acc_turn_step"] is not None
        assert out["test_acc_turn_step"] >= 400

    def test_a_level_shift_is_located_by_its_crossing_not_its_derivative(self) -> None:
        """A loss spanning decades defeats both a linear and a log derivative; a crossing does not."""
        from onebigjump.experiments.p4_grokking import _half_transition_step

        steps = np.array([0, 100, 200, 300, 400, 500, 600, 700], dtype=float)
        # A big early fall, then the real collapse over orders of magnitude, then noise.
        loss = np.array([20.0, 12.0, 11.0, 10.0, 1e-3, 1e-6, 1e-7, 1e-6])
        assert _half_transition_step(steps, loss, log_scale=True) == 400

    def test_the_drop_is_measured_across_the_transition(self) -> None:
        from onebigjump.experiments.p4_grokking import analyse_p4

        out = analyse_p4(self._series(), window=2)
        assert out["gamma_before_transition"] > out["gamma_after_transition"]
        assert out["drops_at_transition"]
        assert out["gamma_peak_to_trough"] > 0

    def test_coincidence_is_reported_against_both_references(self) -> None:
        """P4 names two: the progress measures and the generalization jump. They differ."""
        from onebigjump.experiments.p4_grokking import analyse_p4

        out = analyse_p4(self._series(), window=2, tol_steps=50)
        assert out["sharpest_drop_step"] == 400
        assert out["excluded_turn_step"] == 400
        assert out["drop_coincides_with_progress_measures"] is True
        assert out["drop_coincides_with_generalization"] is False
        assert out["drop_leads_generalization_by"] == 100

    def test_a_drop_far_from_everything_is_not_credited(self) -> None:
        from onebigjump.experiments.p4_grokking import analyse_p4

        cps = [
            self._cp(0, 0.30, 0.01, train_acc=0.01),
            self._cp(100, 0.30, 0.02),
            self._cp(200, 0.03, 0.02),  # the drop happens here, long before anything else
            self._cp(300, 0.03, 0.02),
            self._cp(400, 0.03, 0.02),
            self._cp(500, 0.03, 0.02),
            self._cp(600, 0.03, 0.98, 0.1, 7.0),  # ... and grokking happens here
        ]
        out = analyse_p4(cps, window=2, tol_steps=50)
        assert out["grokking_step"] == 600
        assert out["sharpest_drop_step"] == 200
        assert out["drop_coincides_with_generalization"] is False
        assert out["drop_coincides_with_progress_measures"] is False
        assert out["drop_coincides_with_excluded_loss"] is False

    def test_a_run_that_never_grokked_reports_no_transition(self) -> None:
        from onebigjump.experiments.p4_grokking import analyse_p4

        out = analyse_p4([self._cp(s, 0.03, 0.2) for s in (0, 100, 200, 300)])
        assert out["grokking_step"] is None
        assert "drops_at_transition" not in out
        assert out["drop_coincides_with_generalization"] is None

    def test_the_analysis_is_serialisable(self) -> None:
        import json

        from onebigjump.experiments.p4_grokking import analyse_p4

        json.loads(json.dumps(analyse_p4(self._series())))


class TestShuffledLabelNull:
    """The control that decides whether P4's surviving claim means anything.

    P4 now claims only that the tail index declines monotonically through training, and reads that
    as the network acquiring algorithmic structure. The competing explanation is that it declines
    in *any* long optimisation run -- weights grow, the loss falls, activations settle -- and has
    nothing to do with a circuit being found. Training on a random permutation of the labels
    separates the two: memorisation is still possible, generalisation is not.

    For that comparison to be honest the null must differ from the real task in exactly one way.
    """

    @pytest.fixture(scope="class")
    def pair(self):
        from onebigjump.models.grokking import make_data

        return (
            make_data(p=P, train_frac=0.3, seed=0),
            make_data(p=P, train_frac=0.3, seed=0, shuffle_labels=True),
        )

    def test_inputs_and_split_are_untouched(self, pair) -> None:
        import torch

        real, null = pair
        assert torch.equal(real.inputs, null.inputs)
        assert torch.equal(real.train_idx, null.train_idx)
        assert torch.equal(real.test_idx, null.test_idx)

    def test_the_label_histogram_is_preserved(self, pair) -> None:
        """A permutation, not fresh draws, so the entropy being fitted is the task's own."""
        import torch

        real, null = pair
        assert torch.equal(real.targets.bincount(minlength=P), null.targets.bincount(minlength=P))

    def test_the_arithmetic_relation_is_destroyed(self, pair) -> None:
        real, null = pair
        a, b = real.inputs[:, 0], real.inputs[:, 1]
        assert (real.targets == (a + b) % P).float().mean().item() == 1.0
        agreement = (null.targets == (a + b) % P).float().mean().item()
        assert agreement < 4.0 / P, "shuffled labels still predict a + b; this is not a null"

    def test_the_null_is_reproducible_from_the_seed(self) -> None:
        import torch

        from onebigjump.models.grokking import make_data

        one = make_data(p=P, train_frac=0.3, seed=3, shuffle_labels=True)
        two = make_data(p=P, train_frac=0.3, seed=3, shuffle_labels=True)
        assert torch.equal(one.targets, two.targets)

    def test_different_seeds_give_different_nulls(self) -> None:
        import torch

        from onebigjump.models.grokking import make_data

        one = make_data(p=P, train_frac=0.3, seed=3, shuffle_labels=True)
        two = make_data(p=P, train_frac=0.3, seed=4, shuffle_labels=True)
        assert not torch.equal(one.targets, two.targets)

    def test_the_config_carries_it_through_to_the_trainer(self) -> None:
        """A flag the runner silently drops would produce a null identical to the real run."""
        import inspect

        from onebigjump.config import GrokkingConfig
        from onebigjump.experiments import p4_grokking

        assert GrokkingConfig().shuffle_labels is False
        source = inspect.getsource(p4_grokking.train_grokking)
        assert "shuffle_labels=cfg.shuffle_labels" in source


class TestTheOrderParameterIsNotHill:
    """P4 reported a falling tail index on runs whose order parameter never left zero.

    `analyse_p4` computed every field named `gamma_*` from Hill. Hill is a mean of log-ratios of
    upper order statistics and is non-negative by construction, so it cannot represent a light
    tail; the paper's order parameter is `xi = max(gamma, 0)` with `gamma` the signed shape. On
    the real grokking runs `gamma` is negative at 99% of checkpoints, so `xi` is pinned at zero
    and nothing about it can move -- while Hill fell steadily, and was reported as the result.
    """

    @staticmethod
    def _cp(step: int, hill: float, moment: float, k: int = 640):
        from onebigjump.experiments.p4_grokking import Checkpoint

        return Checkpoint(
            step=step,
            train_loss=0.0,
            test_loss=0.0,
            train_acc=1.0,
            test_acc=1.0,
            restricted_loss=1.0,
            excluded_loss=1.0,
            hill=hill,
            moment=moment,
            gpd=moment,
            k=k,
            n=12769,
            median_deviation=3.0,
        )

    def test_gamma_is_signed_and_xi_is_clipped(self) -> None:
        c = self._cp(0, hill=0.05, moment=-0.12)
        assert c.gamma == -0.12, "gamma must be the signed shape, not Hill"
        assert c.xi == 0.0, "xi must clip a light tail to zero"

    def test_the_row_writes_both_out(self) -> None:
        """A CSV reader must not have to know which column means what."""
        row = self._cp(0, hill=0.05, moment=-0.12).row()
        assert row["hill"] == 0.05
        assert row["gamma"] == -0.12
        assert row["xi"] == 0.0

    def test_a_light_tail_throughout_is_reported_as_untested(self) -> None:
        """Hill falling steeply while gamma stays negative is exactly the observed failure."""
        from onebigjump.experiments.p4_grokking import analyse_p4

        series = [
            self._cp(s, hill=0.06 - 3e-6 * s, moment=-0.05 - 1e-6 * s) for s in range(0, 8000, 100)
        ]
        out = analyse_p4(series)
        assert out["xi_positive_fraction"] == 0.0
        assert out["xi_moves"] is False
        assert "untested" in out["verdict"]
        assert "Hill" in out["verdict"]

    def test_a_genuinely_heavy_tail_is_reported_as_interpretable(self) -> None:
        from onebigjump.experiments.p4_grokking import analyse_p4

        series = [self._cp(s, hill=0.5, moment=0.4) for s in range(0, 8000, 100)]
        out = analyse_p4(series)
        assert out["xi_positive_fraction"] == 1.0
        assert out["xi_moves"] is True
        assert "interpretable" in out["verdict"]

    def test_xi_barely_crossing_zero_does_not_count_as_movement(self) -> None:
        """1% of checkpoints at xi = 0.0006 is noise crossing zero, not an order parameter."""
        import numpy as np

        from onebigjump.experiments.p4_grokking import analyse_p4

        rng = np.random.default_rng(0)
        series = [
            self._cp(s, hill=0.04, moment=float(rng.normal(-0.05, 0.02)))
            for s in range(0, 8000, 100)
        ]
        out = analyse_p4(series)
        assert out["xi_positive_fraction"] < 0.10
        assert out["xi_moves"] is False
