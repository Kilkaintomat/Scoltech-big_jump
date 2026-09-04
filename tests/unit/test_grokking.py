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
