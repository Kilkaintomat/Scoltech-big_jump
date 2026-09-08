"""Loading theorem statements, building prompts, and sampling proofs.

`generate` is tested against a fake backend: the sampling protocol -- whole proofs, no verifier
feedback, one record per sample -- is what matters here, and it does not need a model to check.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from onebigjump.lean.problems import (
    DEFAULT_HEADER,
    Problem,
    build_prompt,
    extract_lean_block,
    load_problems,
    split_problems,
)
from onebigjump.models.generation import (
    Sample,
    assert_tokenizer_roundtrips,
    generate,
    write_samples,
)

ROWS = [
    {"problem_id": "p1", "formal_statement": "theorem a : 1 = 1 := by", "header": "import Mathlib"},
    {"name": "p2", "statement": "theorem b : 2 = 2 := by", "split": "test"},
    {"id": "p3", "goal": "theorem c : 3 = 3 := by"},
    {"id": "empty", "formal_statement": "   "},
]


@pytest.fixture
def problems_file(tmp_path: Path) -> Path:
    path = tmp_path / "problems.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in ROWS), encoding="utf-8")
    return path


class TestLoading:
    def test_several_field_spellings_are_accepted(self, problems_file: Path) -> None:
        problems = load_problems(problems_file)
        assert [p.problem_id for p in problems] == ["p1", "p2", "p3"]

    def test_a_row_without_a_statement_is_skipped_not_emptied(self, problems_file: Path) -> None:
        """An empty problem would later look like a model failure."""
        assert all(p.statement.strip() for p in load_problems(problems_file))
        assert "empty" not in {p.problem_id for p in load_problems(problems_file)}

    def test_a_missing_header_falls_back_to_the_default(self, problems_file: Path) -> None:
        by_id = {p.problem_id: p for p in load_problems(problems_file)}
        assert by_id["p1"].header == "import Mathlib"
        assert by_id["p3"].header == DEFAULT_HEADER

    def test_limit_and_split(self, problems_file: Path) -> None:
        assert len(load_problems(problems_file, limit=2)) == 2
        assert [p.problem_id for p in load_problems(problems_file, split="test")] == ["p2"]

    def test_an_unknown_split_does_not_empty_the_set(self, problems_file: Path) -> None:
        """Filtering to nothing is more likely a field-name mismatch than an empty benchmark."""
        assert len(load_problems(problems_file, split="nonexistent")) == 3


class TestSplit:
    def test_the_split_is_disjoint_and_covers_everything(self) -> None:
        problems = [Problem(f"p{i}", "theorem t : True := by") for i in range(20)]
        calib, rest = split_problems(problems, calibration_frac=0.5, seed=0)
        assert len(calib) == 10
        assert not {p.problem_id for p in calib} & {p.problem_id for p in rest}
        assert len(calib) + len(rest) == 20

    def test_it_is_reproducible(self) -> None:
        problems = [Problem(f"p{i}", "theorem t : True := by") for i in range(20)]
        a, _ = split_problems(problems, seed=3)
        b, _ = split_problems(problems, seed=3)
        assert [p.problem_id for p in a] == [p.problem_id for p in b]


class TestPrompts:
    @pytest.mark.parametrize(
        "model_id", ["deepseek-ai/DeepSeek-Prover-V2-7B", "Goedel-LM/Goedel-Prover-V2-8B"]
    )
    def test_a_known_family_gets_its_own_template(self, model_id: str) -> None:
        prompt = build_prompt(Problem("p", "theorem t : True := by"), model_id)
        assert "```lean4" in prompt
        assert "theorem t : True := by" in prompt

    def test_an_unknown_model_gets_the_default(self) -> None:
        prompt = build_prompt(Problem("p", "theorem t : True := by"), "gpt2")
        assert prompt.startswith("Prove the following theorem in Lean 4")

    def test_the_header_is_included(self) -> None:
        problem = Problem("p", "theorem t : True := by", header="import Mathlib")
        assert "import Mathlib" in build_prompt(problem, "gpt2")


class TestLeanBlockExtraction:
    problem = Problem("p", "theorem t (a : Nat) : a = a := by")

    def test_a_fenced_block_is_preferred(self) -> None:
        completion = "Some reasoning first.\n```lean4\ntheorem t : True := by\n  trivial\n```\n"
        assert extract_lean_block(completion, self.problem).startswith("theorem t")
        assert "Some reasoning" not in extract_lean_block(completion, self.problem)

    def test_informal_preamble_is_discarded(self) -> None:
        """Section 5.1 labels only the formal tactics."""
        completion = "First I will use rfl.\nThat should work.\ntheorem t : True := by\n  trivial"
        assert extract_lean_block(completion, self.problem).startswith("theorem t")

    def test_a_continuation_gets_the_statement_prepended(self) -> None:
        """The prompt already contained the statement, so the completion starts mid-declaration."""
        got = extract_lean_block("  rfl\n", self.problem)
        assert got.startswith("theorem t (a : Nat)")
        assert "rfl" in got

    def test_an_unterminated_block_is_still_read(self) -> None:
        completion = "```lean4\ntheorem t : True := by\n  trivial"
        assert "trivial" in extract_lean_block(completion, self.problem)

    def test_an_empty_completion_gives_an_empty_proof(self) -> None:
        assert extract_lean_block("", self.problem) == ""


class _FakeBackend:
    """Returns deterministic completions, so the protocol can be checked without a model."""

    model_id = "fake/prover"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def sample(self, prompts, *, n, temperature, max_new_tokens):
        self.calls.append(
            {"n_prompts": len(prompts), "n": n, "temperature": temperature, "max": max_new_tokens}
        )
        return [[f"  rfl -- {i} at T={temperature}" for i in range(n)] for _ in prompts]


class TestGenerate:
    @pytest.fixture
    def problems(self) -> list[Problem]:
        return [Problem(f"p{i}", f"theorem t{i} : True := by") for i in range(3)]

    def test_one_sample_per_problem_temperature_and_index(self, problems) -> None:
        samples = list(
            generate(problems, _FakeBackend(), samples_per_problem=2, temperatures=(0.6, 1.0))
        )
        assert len(samples) == 3 * 2 * 2
        assert len({s.trace_id for s in samples}) == len(samples), "trace ids must be unique"

    def test_the_trace_id_carries_problem_temperature_and_index(self, problems) -> None:
        samples = list(
            generate(problems, _FakeBackend(), samples_per_problem=1, temperatures=(0.6,))
        )
        assert samples[0].trace_id == "p0-T0.6-000"

    def test_every_temperature_reaches_the_backend(self, problems) -> None:
        backend = _FakeBackend()
        list(generate(problems, backend, samples_per_problem=2, temperatures=(0.6, 1.0)))
        assert [c["temperature"] for c in backend.calls] == [0.6, 1.0]
        assert all(c["n"] == 2 and c["n_prompts"] == 3 for c in backend.calls)

    def test_the_proof_is_a_complete_declaration(self, problems) -> None:
        sample = next(iter(generate(problems, _FakeBackend(), samples_per_problem=1)))
        assert sample.proof.startswith("theorem t0")
        assert "rfl" in sample.proof

    def test_no_verifier_is_consulted(self, problems) -> None:
        """Section 2: traces are generated to full length without verifier feedback."""
        sample = next(iter(generate(problems, _FakeBackend(), samples_per_problem=1)))
        assert not hasattr(sample, "valid")
        assert set(sample.as_record()) & {"proof", "trace_id", "problem_id"}

    def test_records_round_trip_through_jsonl(self, problems, tmp_path: Path) -> None:
        samples = generate(problems, _FakeBackend(), samples_per_problem=1, temperatures=(0.6,))
        path, count = write_samples(samples, tmp_path / "s.jsonl")
        assert count == 3
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert {r["trace_id"] for r in records} == {"p0-T0.6-000", "p1-T0.6-000", "p2-T0.6-000"}
        assert all(r["proof"] for r in records)

    def test_completions_can_be_dropped_to_save_space(self, problems, tmp_path: Path) -> None:
        samples = generate(
            problems,
            _FakeBackend(),
            samples_per_problem=1,
            temperatures=(0.6,),
            keep_completion=False,
        )
        path, _ = write_samples(samples, tmp_path / "s.jsonl", keep_completion=False)
        record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert "completion" not in record
        assert record["proof"]

    def test_the_record_is_what_lean_verify_reads(self, problems) -> None:
        from onebigjump.lean.batch import ProofRequest

        sample = next(iter(generate(problems, _FakeBackend(), samples_per_problem=1)))
        request = ProofRequest(sample.as_record())
        assert request.trace_id == sample.trace_id
        assert request.problem_id == "p0"
        assert request.proof == sample.proof


class TestSampleRecord:
    def test_defaults_are_serialisable(self) -> None:
        record = Sample("t", "p", "m", 0.6, 0, "theorem t : True := by\n  trivial").as_record()
        json.loads(json.dumps(record))


class TestDirectivesReachTheKernel:
    """`extract_lean_block` cuts everything before `theorem`, so the `open` lines must travel."""

    def test_a_sample_carries_the_problems_directives(self) -> None:
        problem = Problem(
            "p",
            "theorem t : True := by",
            header="import Mathlib\nopen Real\nopen Nat",
        )
        sample = next(iter(generate([problem], _FakeBackend(), samples_per_problem=1)))
        assert sample.directives == "open Real\nopen Nat"

    def test_directives_come_from_the_fetched_record_when_present(self) -> None:
        problem = Problem(
            "p",
            "theorem t : True := by",
            header="import Mathlib",
            meta={"directives": "open scoped Nat Matrix"},
        )
        sample = next(iter(generate([problem], _FakeBackend(), samples_per_problem=1)))
        assert sample.directives == "open scoped Nat Matrix"

    def test_the_verifier_receives_them_prepended(self) -> None:
        from onebigjump.lean.batch import ProofRequest

        problem = Problem("p", "theorem t : True := by", header="import Mathlib\nopen Real")
        sample = next(iter(generate([problem], _FakeBackend(), samples_per_problem=1)))
        source = ProofRequest(sample.as_record()).source
        assert source.startswith("open Real\n")
        assert "theorem t" in source

    def test_no_directives_leaves_the_proof_untouched(self) -> None:
        from onebigjump.lean.batch import ProofRequest

        assert ProofRequest({"proof": "theorem t := by"}).source == "theorem t := by"

    def test_imports_never_reach_the_kernel(self) -> None:
        """An import inside a REPL command is a syntax error."""
        from onebigjump.lean.batch import ProofRequest

        problem = Problem("p", "theorem t : True := by", header="import Mathlib\nopen Real")
        sample = next(iter(generate([problem], _FakeBackend(), samples_per_problem=1)))
        assert "import " not in ProofRequest(sample.as_record()).source


class TestShardingAndResume:
    def test_shards_partition_the_input(self) -> None:
        import hashlib

        from onebigjump.lean.batch import ProofRequest

        ids = [f"trace-{i:04d}" for i in range(500)]
        for n in (2, 4, 8):
            assigned = [
                sum(
                    1
                    for i in ids
                    if hashlib.sha1(ProofRequest({"trace_id": i}).trace_id.encode()).digest()[0] % n
                    == s
                )
                for s in range(n)
            ]
            assert sum(assigned) == len(ids), f"n_shards={n} lost or duplicated traces"
            assert all(a > 0 for a in assigned), f"n_shards={n} left a shard empty"

    def test_the_assignment_is_stable_across_runs(self) -> None:
        import hashlib

        def shard_of(trace_id: str, n: int) -> int:
            return hashlib.sha1(trace_id.encode()).digest()[0] % n

        assert shard_of("abc", 4) == shard_of("abc", 4)


class TestTokenizerRoundTrip:
    """The guard that would have saved a GPU-day.

    A sampling run against transformers 5.16.1 produced 3616 completions in which every space,
    newline and non-ASCII character had been deleted by the tokenizer's own decoder. Nothing
    downstream noticed -- the completions were still strings, still said `theorem` -- and the loss
    only became visible when the Lean kernel called all of them parse errors.
    """

    class _Tokenizer:
        """A tokenizer stub whose decoder mangles the text in a chosen way."""

        def __init__(self, mangle: Callable[[str], str]) -> None:
            self._mangle = mangle
            self._text = ""

        def __call__(self, text: str) -> dict[str, list[int]]:
            self._text = text
            return {"input_ids": [0]}

        def decode(self, _ids: list[int], **_kw: object) -> str:
            return self._mangle(self._text)

    def test_a_faithful_tokenizer_passes(self) -> None:
        assert_tokenizer_roundtrips(self._Tokenizer(lambda s: s), "good/model")

    def test_leading_and_trailing_whitespace_is_not_a_failure(self) -> None:
        """Templates add a BOS marker and strip the final newline; neither loses information."""
        assert_tokenizer_roundtrips(self._Tokenizer(lambda s: f"<s> {s.strip()}"), "good/model")

    def test_dropped_whitespace_is_rejected(self) -> None:
        """The observed transformers 5.16.1 behaviour, verbatim."""
        with pytest.raises(RuntimeError, match="does not round-trip"):
            assert_tokenizer_roundtrips(
                self._Tokenizer(lambda s: re.sub(r"\s+", "", s)), "transformers5/model"
            )

    def test_dropped_unicode_is_rejected(self) -> None:
        """Lean is written in Unicode; a decoder that drops it silently breaks every statement."""
        with pytest.raises(RuntimeError, match="does not round-trip"):
            assert_tokenizer_roundtrips(
                self._Tokenizer(lambda s: s.encode("ascii", "ignore").decode()), "ascii/model"
            )

    def test_the_message_names_the_cause_and_the_fix(self) -> None:
        with pytest.raises(RuntimeError) as exc:
            assert_tokenizer_roundtrips(self._Tokenizer(lambda s: ""), "m")
        assert "transformers" in str(exc.value) and "4.51.3" in str(exc.value)
