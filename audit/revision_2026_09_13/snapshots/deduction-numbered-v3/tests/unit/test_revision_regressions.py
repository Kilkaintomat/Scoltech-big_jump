"""Scientific failure cases reproduced during the September code revision."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from onebigjump.experiments.dataset import from_traces, validate_table
from onebigjump.experiments.p1_tail_separation import tail_separation
from onebigjump.experiments.p2_localization import _roc, localization_rates
from onebigjump.lean.schemas import (
    ProofTrace,
    StepLabel,
    StepStatus,
    TraceOutcome,
    VerificationSummary,
)
from onebigjump.models.extraction import read_traces, stratified_calibration_split, trace_alignment
from onebigjump.reproducibility import _git_from_environment, git_info
from onebigjump.stats.thresholds import select_k


def trace(trace_id="t", problem_id="p", *, inline=False):
    header = "theorem demo : True := by"
    body = "trivial" if inline else "  trivial"
    return ProofTrace(
        trace_id=trace_id,
        problem_id=problem_id,
        model_id="handwritten",
        header=header,
        proof_text=header + (" " if inline else "\n") + body,
        outcome=TraceOutcome.VERIFIED,
        steps=[
            StepLabel(
                index=0,
                tactic="trivial",
                status=StepStatus.OK,
                valid=True,
                line_start=0,
                line_end=0,
                n_lines=1,
            )
        ],
    )


class CharTokenizer:
    """Lossless tokenizer; makes context and positional errors observable without downloads."""

    def __call__(self, text, **kwargs):
        ids = list(map(ord, text))
        if kwargs.get("return_tensors"):
            import torch

            return {"input_ids": torch.tensor([ids])}
        return {"input_ids": ids, "offset_mapping": [(i, i + 1) for i in range(len(text))]}

    def decode(self, ids, **kwargs):
        return "".join(map(chr, ids))


def sampled_trace():
    tr = trace()
    tr.model_id = "prover"
    prompt = "Solve this problem.\n"
    completion = "Informal reasoning first.\n```lean\n" + tr.proof_text + "\n```"
    tr.meta["generation"] = {
        "prompt": prompt,
        "completion": completion,
        "proof": tr.proof_text,
        "prompt_token_ids": list(map(ord, prompt)),
        "completion_token_ids": list(map(ord, completion)),
    }
    return tr


def table():
    return pd.DataFrame(
        {
            "trace_id": ["t"] * 3,
            "prompt_id": ["p"] * 3,
            "model": ["m"] * 3,
            "layer": [0] * 3,
            "statistic": ["raw"] * 3,
            "t": [0, 1, 2],
            "L": [3] * 3,
            "z": [1.0, 3.0, 2.0],
            "valid": [True, False, False],
            "t_star": [1] * 3,
            "outcome": ["refuted"] * 3,
            "surprisal": [1.0, 2.0, 3.0],
            "status": ["ok", "error", "unreached"],
        }
    )


@pytest.mark.parametrize("value", [np.nan, np.inf, -1.0])
def test_nonfinite_or_negative_deviations_are_rejected(value):
    df = table()
    df.loc[0, "z"] = value
    with pytest.raises(ValueError, match="finite and nonnegative"):
        validate_table(df)


@pytest.mark.parametrize("mutation", ["gap", "star", "outcome", "unreached", "length", "binary"])
def test_corrupt_labels_and_step_structure_are_rejected(mutation):
    df = table()
    if mutation == "gap":
        df = df.drop(index=0)
    elif mutation == "star":
        df["t_star"] = 2
    elif mutation == "outcome":
        df["outcome"] = "verified"
    elif mutation == "unreached":
        df.loc[2, "status"] = "error"
    elif mutation == "length":
        df.loc[0, "L"] = 4
    else:
        df["valid"] = df["valid"].astype(object)
        df.loc[0, "valid"] = "false"
    with pytest.raises(ValueError):
        validate_table(df)


def test_earliest_maximum_defines_top_one_and_top_three():
    traces = [{"z": np.ones(5), "t_star": t} for t in range(5)]
    rates = localization_rates(traces)
    assert rates["top1"] == pytest.approx(1 / 5)
    assert rates["top3"] == pytest.approx(3 / 5)


def test_tied_roc_curve_agrees_with_auc():
    result = _roc([{"z": np.ones(5), "t_star": 3}])
    assert result["auc"] == 0.5
    assert result["curve"] == {"fpr": [0.0, 1.0], "tpr": [0.0, 1.0]}


@pytest.mark.parametrize("n", [50, 100, 200])
def test_default_k_selection_handles_small_bootstrap_subsamples(n):
    values = np.random.default_rng(7).pareto(2, size=n) + 1
    result = select_k(values, resamples=20)
    assert 2 <= result.k < n


def test_missing_pre_rejection_subset_cannot_confirm_expected_pattern():
    estimates = {
        "verified": {"hill": 0.1, "bootstrap": {"hill": {"ci_low": 0.05, "ci_high": 0.15}}},
        "refuted_post": {"hill": 0.5, "bootstrap": {"hill": {"ci_low": 0.4, "ci_high": 0.6}}},
    }
    assert tail_separation(estimates)["expected_pattern_holds"] is None


def test_generation_context_and_exact_tokens_survive_alignment():
    tr = sampled_trace()
    prepared = trace_alignment(tr, CharTokenizer())
    assert prepared is not None
    text, alignment = prepared
    generation = tr.meta["generation"]
    assert text == generation["prompt"] + generation["completion"]
    assert (
        alignment.input_ids == generation["prompt_token_ids"] + generation["completion_token_ids"]
    )
    assert alignment.prompt_end_token == len(generation["prompt_token_ids"]) - 1
    assert text[alignment.step_end_tokens[0]] == "l"
    assert "Informal reasoning" in text[: alignment.step_end_tokens[0]]


def test_inline_tactic_is_not_lost():
    prepared = trace_alignment(trace(inline=True), CharTokenizer())
    assert prepared is not None
    assert len(prepared[1].step_end_tokens) == 1


def test_model_trace_without_generation_context_is_refused():
    tr = trace()
    tr.model_id = "prover"
    assert trace_alignment(tr, CharTokenizer()) is None


def test_retokenized_ids_must_match_exactly():
    class WrongTokenizer(CharTokenizer):
        def __call__(self, text, **kwargs):
            result = super().__call__(text, **kwargs)
            result["input_ids"][0] += 1
            return result

    assert trace_alignment(sampled_trace(), WrongTokenizer()) is None


def test_incomplete_alignment_is_refused():
    class MissingTokenizer(CharTokenizer):
        def __call__(self, text, **kwargs):
            result = super().__call__(text, **kwargs)
            result["offset_mapping"] = [(0, 1)] + [(0, 0)] * (len(text) - 1)
            return result

    assert trace_alignment(trace(), MissingTokenizer()) is None


def test_trajectory_cannot_silently_truncate_labels():
    from onebigjump.models.activations import Trajectory

    tr = trace()
    traj = Trajectory("t", 0, np.ones((1, 2)), np.array([]), 0, 2)
    with pytest.raises(ValueError, match="length mismatch"):
        from_traces([tr], {"t": {0: traj}}, statistics=["raw"])


def test_calibration_membership_does_not_depend_on_success_labels():
    traces = [trace(str(i), str(i)) for i in range(10)]
    before = stratified_calibration_split(traces, seed=9)
    for tr in traces[:5]:
        tr.outcome = TraceOutcome.REFUTED
    assert stratified_calibration_split(traces, seed=9) == before


def test_read_shards_and_reject_duplicate_ids(tmp_path):
    for i in range(2):
        (tmp_path / f"traces.shard{i:02d}.jsonl").write_text(trace(str(i)).model_dump_json() + "\n")
    assert len(read_traces(tmp_path / "traces.jsonl")) == 2
    (tmp_path / "traces.shard02.jsonl").write_text(trace("0").model_dump_json() + "\n")
    with pytest.raises(ValueError, match="duplicate trace_id"):
        read_traces(tmp_path)


def test_unknown_git_status_is_not_a_clean_checkout(monkeypatch, tmp_path):
    from onebigjump import reproducibility

    monkeypatch.setattr(reproducibility, "_run", lambda cmd: "a" * 40 if "HEAD" in cmd else None)
    assert git_info(tmp_path)["dirty"] is None
    monkeypatch.setenv("ONEBIGJUMP_GIT_COMMIT", "a" * 40)
    monkeypatch.delenv("ONEBIGJUMP_GIT_STATUS", raising=False)
    assert _git_from_environment()["dirty"] is None


def test_launcher_provenance_is_scoped_to_its_repository(monkeypatch, tmp_path):
    from onebigjump import reproducibility

    monkeypatch.setattr(reproducibility, "_run", lambda cmd: None)
    monkeypatch.setenv("ONEBIGJUMP_GIT_COMMIT", "a" * 40)
    monkeypatch.setenv("ONEBIGJUMP_GIT_STATUS", "")
    monkeypatch.delenv("ONEBIGJUMP_GIT_ROOT", raising=False)
    assert git_info(tmp_path)["commit"] is None
    monkeypatch.setenv("ONEBIGJUMP_GIT_ROOT", str(tmp_path))
    assert git_info(tmp_path)["source"] == "environment"
    assert git_info(tmp_path / "unrelated")["commit"] is None


def test_step_timeout_count_is_separate_from_statement_timeout():
    tr = trace()
    tr.outcome = TraceOutcome.REFUTED
    tr.t_star = 0
    tr.steps[0].valid = False
    tr.steps[0].status = StepStatus.TIMEOUT
    summary = VerificationSummary.from_traces([tr])
    assert summary.refuted == 1
    assert summary.step_timeout == 1
    assert summary.timeout == 0


def test_fourier_circuit_excludes_mixed_frequencies_and_retains_dc():
    from onebigjump.models.grokking import fourier_circuit_logits

    p = 11
    a, b = np.meshgrid(np.arange(p), np.arange(p), indexing="ij")
    circuit = np.cos(2 * np.pi * (a + b) / p)
    mixed = np.cos(2 * np.pi * (a + 2 * b) / p)
    grid = (3 + circuit + mixed)[:, :, None]
    restricted, excluded = fourier_circuit_logits(grid, [1])
    np.testing.assert_allclose(restricted[:, :, 0], 3 + circuit, atol=1e-12)
    np.testing.assert_allclose(excluded[:, :, 0], 3 + mixed, atol=1e-12)


def test_batch_keeps_sampling_metadata_and_shard_artifacts(monkeypatch, tmp_path):
    from onebigjump.lean import batch

    class Repl:
        restarts = recoveries = 0

        def __init__(self, env):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        batch, "discover", lambda _: SimpleNamespace(as_dict=lambda: {}, require=lambda: None)
    )
    monkeypatch.setattr(batch, "LeanREPL", Repl)
    monkeypatch.setattr(batch, "verify_trace", lambda _, source, **kw: trace(kw["trace_id"]))
    req = {
        "trace_id": "t",
        "problem_id": "p",
        "proof": trace().proof_text,
        "prompt": "request",
        "completion": "proof",
        "prompt_token_ids": [1, 2],
        "completion_token_ids": [3, 4],
    }
    for shard in range(2):
        batch.verify_batch([req], tmp_path, n_shards=2, shard=shard, resume=False)
    assert len(list(tmp_path.glob("manifest-*.json"))) == 2
    assert len(list(tmp_path.glob("summary.shard*.json"))) == 2
    saved = read_traces(tmp_path)[0].meta["generation"]
    assert saved["prompt_token_ids"] == [1, 2]
    assert saved["completion"] == "proof"
    # A valid proof of True must not count as a proof of the requested False.
    req["theorem_statement"] = "theorem demo : False := by"
    monkeypatch.setattr(
        batch, "verify_trace", lambda *a, **kw: pytest.fail("changed goal reached kernel")
    )
    traces, summary = batch.verify_batch([req], tmp_path / "changed-goal", resume=False)
    assert traces[0].outcome == TraceOutcome.STATEMENT_MISMATCH
    assert not traces[0].labelled
    assert summary.statement_mismatch == 1


@pytest.mark.ml
def test_exact_context_states_match_direct_transformer_forward():
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    from onebigjump.models.activations import extract_trajectory
    from onebigjump.models.hooks import record_residuals

    model = transformers.GPT2LMHeadModel(
        transformers.GPT2Config(
            vocab_size=256,
            n_positions=256,
            n_layer=2,
            n_head=2,
            n_embd=16,
        )
    ).eval()
    text, alignment = trace_alignment(sampled_trace(), CharTokenizer())
    actual = extract_trajectory(model, CharTokenizer(), text, alignment, trace_id="t", layers=[0])
    with torch.no_grad(), record_residuals(model, [0], alignment.readout_positions) as rec:
        model(input_ids=torch.tensor([alignment.input_ids]), use_cache=False)
    np.testing.assert_array_equal(actual[0].states, rec.result()[0].states.numpy())
    with pytest.raises(ValueError, match="incomplete"):
        extract_trajectory(
            model,
            CharTokenizer(),
            text,
            replace(alignment, unaligned=[0]),
            trace_id="t",
            layers=[0],
        )


def test_generation_seed_and_revision_reach_backend(monkeypatch, tmp_path):
    from onebigjump.experiments.pipeline import run_generation
    from onebigjump.models import generation

    calls = []

    class Backend:
        model_id = "fake"

        def sample(self, prompts, **kwargs):
            return [[f"trivial -- {np.random.random()}"] for _ in prompts]  # noqa: NPY002

    def backend(*args, **kwargs):
        calls.append(kwargs)
        return Backend()

    monkeypatch.setattr(generation, "make_backend", backend)
    problems = tmp_path / "problems.jsonl"
    problems.write_text(json.dumps({"id": "p", "statement": "theorem t : True := by"}) + "\n")
    for name in ("a", "b"):
        run_generation(
            problems,
            "fake",
            tmp_path / name,
            temperatures=(0.6,),
            samples_per_problem=1,
            seed=42,
            revision="fixed-revision",
        )
    assert (tmp_path / "a/samples.jsonl").read_text() == (tmp_path / "b/samples.jsonl").read_text()
    assert all(call["seed"] == 42 and call["revision"] == "fixed-revision" for call in calls)
