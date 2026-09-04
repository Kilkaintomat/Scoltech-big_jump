"""Teacher-forced extraction against a real transformer (GPT-2), end to end."""

from __future__ import annotations

import numpy as np
import pytest

from onebigjump.lean import segment_proof, split_header_and_proof
from onebigjump.models.activations import deviations, extract_trajectory, fit_calibration
from onebigjump.models.hooks import block_modules, layer_indices, record_residuals
from onebigjump.models.token_alignment import align_steps, step_char_spans

pytestmark = [pytest.mark.ml, pytest.mark.slow]

MODEL = "gpt2"
PROMPT = "Prove the following in Lean 4.\n\n"
PROOFS = [
    "theorem a (x y : Nat) : x + y = y + x := by\n  rw [Nat.add_comm]\n  simp\n  ring\n  done",
    "theorem b (x : Nat) : x + 0 = x := by\n  simp\n  rfl\n  omega\n  trivial",
    "theorem c (n : Nat) : 0 + n = n := by\n  induction n\n  simp\n  omega\n  done",
]


@pytest.fixture(scope="module")
def model_and_tokenizer():
    transformers = pytest.importorskip("transformers")
    try:
        model = transformers.AutoModelForCausalLM.from_pretrained(MODEL)
        tok = transformers.AutoTokenizer.from_pretrained(MODEL)
    except Exception as exc:  # pragma: no cover - offline or no cached weights
        pytest.skip(f"{MODEL} is not available: {exc}")
    model.eval()
    return model, tok


def _prepare(tok, proof: str):
    header, body = split_header_and_proof(proof)
    segs = segment_proof(body)
    prompt = PROMPT + header + "\n"
    full = prompt + body
    spans = step_char_spans(body, segs, base_offset=len(prompt))
    enc = tok(full, return_offsets_mapping=True, add_special_tokens=True)
    al = align_steps(enc["offset_mapping"], spans, prompt_char_end=len(prompt))
    return full, segs, al, enc


class TestHooks:
    def test_blocks_are_found_and_counted(self, model_and_tokenizer) -> None:
        model, _ = model_and_tokenizer
        blocks = block_modules(model)
        assert len(blocks) == model.config.n_layer == 12

    def test_only_the_requested_positions_are_captured(self, model_and_tokenizer) -> None:
        import torch

        model, tok = model_and_tokenizer
        ids = tok("hello world, this is a test", return_tensors="pt")["input_ids"]
        layers = layer_indices(12, (0.25, 0.5, 0.75))
        with torch.no_grad(), record_residuals(model, layers, [0, 2, 4]) as rec:
            model(input_ids=ids)
        caps = rec.result()
        assert set(caps) == set(layers)
        for cap in caps.values():
            assert cap.n_positions == 3
            assert cap.d_model == model.config.n_embd
            assert cap.states.dtype == torch.float32

    def test_hooks_are_removed_after_the_context(self, model_and_tokenizer) -> None:
        import torch

        model, tok = model_and_tokenizer
        ids = tok("abc def", return_tensors="pt")["input_ids"]
        with torch.no_grad(), record_residuals(model, [0], [0]) as rec:
            model(input_ids=ids)
        before = dict(rec.captures)
        with torch.no_grad():
            model(input_ids=ids)
        assert rec.captures.keys() == before.keys()
        assert torch.equal(rec.captures[0], before[0]), "a leaked hook would overwrite this"


class TestExtraction:
    @pytest.fixture(scope="class")
    def extracted(self, model_and_tokenizer):
        model, tok = model_and_tokenizer
        out = []
        for i, proof in enumerate(PROOFS):
            full, segs, al, _ = _prepare(tok, proof)
            trajs = extract_trajectory(
                model, tok, full, al, trace_id=f"t{i}", layer_fractions=(0.25, 0.5, 0.75)
            )
            out.append((segs, al, trajs))
        return out

    def test_every_step_aligns(self, extracted) -> None:
        for _, al, _ in extracted:
            assert al.complete, al.unaligned

    def test_one_state_per_step_plus_the_prompt(self, extracted) -> None:
        for segs, _, trajs in extracted:
            for traj in trajs.values():
                assert traj.states.shape[0] == len(segs) + 1
                assert traj.n_steps == len(segs)

    def test_the_requested_layers_come_back(self, extracted) -> None:
        _, _, trajs = extracted[0]
        assert sorted(trajs) == layer_indices(12, (0.25, 0.5, 0.75))

    def test_states_are_finite_and_not_all_equal(self, extracted) -> None:
        for _, _, trajs in extracted:
            for traj in trajs.values():
                assert np.all(np.isfinite(traj.states))
                assert np.linalg.norm(np.diff(traj.states, axis=0), axis=1).min() > 0

    def test_deeper_layers_have_larger_residual_norms(self, extracted) -> None:
        """The residual stream grows with depth; this is why depth-wise readouts are normalised."""
        _, _, trajs = extracted[0]
        norms = [np.linalg.norm(trajs[layer].states).item() for layer in sorted(trajs)]
        assert norms == sorted(norms)

    def test_surprisal_is_a_positive_number_per_step(self, extracted) -> None:
        for segs, _, trajs in extracted:
            traj = next(iter(trajs.values()))
            assert traj.surprisal.shape == (len(segs),)
            assert np.all(np.isfinite(traj.surprisal))
            assert np.all(traj.surprisal > 0), "negative log-probabilities are positive"

    def test_extraction_is_deterministic(self, model_and_tokenizer) -> None:
        model, tok = model_and_tokenizer
        full, _, al, _ = _prepare(tok, PROOFS[0])
        a = extract_trajectory(model, tok, full, al, trace_id="a", layer_fractions=(0.5,))
        b = extract_trajectory(model, tok, full, al, trace_id="b", layer_fractions=(0.5,))
        layer = next(iter(a))
        np.testing.assert_allclose(a[layer].states, b[layer].states)

    def test_a_stale_alignment_is_refused(self, model_and_tokenizer) -> None:
        model, tok = model_and_tokenizer
        full, _, al, _ = _prepare(tok, PROOFS[0])
        al.n_tokens += 5
        with pytest.raises(ValueError, match="tokenisation changed"):
            extract_trajectory(model, tok, full, al, trace_id="x", layer_fractions=(0.5,))


class TestDeviationsOnRealActivations:
    def test_raw_deviations_are_computable_without_a_calibration(self, model_and_tokenizer) -> None:
        model, tok = model_and_tokenizer
        full, segs, al, _ = _prepare(tok, PROOFS[0])
        traj = extract_trajectory(model, tok, full, al, trace_id="t", layer_fractions=(0.5,))
        z = deviations(next(iter(traj.values())))["raw"]
        assert z.shape == (len(segs),)
        assert np.all(z > 0)

    def test_a_calibration_on_three_traces_is_refused(self, model_and_tokenizer) -> None:
        """768 dimensions from 12 increments is exactly the regime the guard exists for."""
        model, tok = model_and_tokenizer
        trajs = []
        for i, proof in enumerate(PROOFS):
            full, _, al, _ = _prepare(tok, proof)
            trajs.append(
                next(
                    iter(
                        extract_trajectory(
                            model, tok, full, al, trace_id=f"t{i}", layer_fractions=(0.5,)
                        ).values()
                    )
                )
            )
        with pytest.raises(ValueError, match="under-determined whitening"):
            fit_calibration(trajs)
