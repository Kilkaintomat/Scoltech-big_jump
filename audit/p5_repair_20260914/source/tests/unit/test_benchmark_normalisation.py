"""Normalising the three benchmarks. Each quirk here was found by running against the real kernel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from onebigjump.lean.problems import (
    header_directives,
    load_problems,
    modernise_binders,
    open_for_tactics,
)

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "raw"
BENCHMARKS = ["minif2f_test", "proofnet_test", "putnambench_test"]


class TestOpenForTactics:
    """The three benchmarks end their statements three different ways, none of them usable."""

    @pytest.mark.parametrize(
        "raw,label",
        [
            ("theorem t : 1 = 1 := sorry", "miniF2F"),
            ("theorem t : 1 = 1 :=", "ProofNet"),
            ("theorem t : 1 = 1 :=\nsorry", "PutnamBench"),
            ("theorem t : 1 = 1 :=\n  sorry", "PutnamBench, indented"),
        ],
    )
    def test_every_ending_becomes_a_tactic_block(self, raw: str, label: str) -> None:
        assert open_for_tactics(raw) == "theorem t : 1 = 1 := by", label

    def test_an_already_open_statement_is_left_alone(self) -> None:
        assert open_for_tactics("theorem t : 1 = 1 := by") == "theorem t : 1 = 1 := by"

    def test_trailing_whitespace_does_not_defeat_it(self) -> None:
        assert open_for_tactics("theorem t : P :=  sorry  \n\n") == "theorem t : P := by"


class TestModerniseBinders:
    """Mathlib renamed `∑ x in S` to `∑ x ∈ S` and now rejects the old spelling outright."""

    @pytest.mark.parametrize(
        "old,new",
        [
            ("∑ x in Finset.range 10, x", "∑ x ∈ Finset.range 10, x"),
            ("∑ q in Q, q[0]", "∑ q ∈ Q, q[0]"),
            ("∏ i in (range n), f i", "∏ i ∈ (range n), f i"),
            ("⋃ i in S, f i", "⋃ i ∈ S, f i"),
        ],
    )
    def test_the_deprecated_binder_is_rewritten(self, old: str, new: str) -> None:
        assert modernise_binders(old) == new

    def test_modern_syntax_is_untouched(self) -> None:
        for text in ("∑ k ∈ S, k", "∏ i ∈ Finset.range n, i"):
            assert modernise_binders(text) == text

    def test_an_unrelated_in_survives(self) -> None:
        """`in` appears in `let ... in` and inside set expressions; only the binder moves."""
        assert (
            modernise_binders("theorem t (h : x in_set S) : P") == "theorem t (h : x in_set S) : P"
        )

    def test_it_is_idempotent(self) -> None:
        once = modernise_binders("∑ x in S, x")
        assert modernise_binders(once) == once


class TestHeaderDirectives:
    def test_imports_are_dropped(self) -> None:
        """An import inside a REPL command is a syntax error; Mathlib is imported once at startup."""
        header = "import Mathlib.Algebra.BigOperators.Basic\nimport Mathlib.Data.Real.Basic"
        assert header_directives(header) == ""

    def test_opens_are_kept(self) -> None:
        """Dropping `open Real` turns a valid theorem into a parse error."""
        header = "import Mathlib\n\nopen BigOperators\nopen Real\nopen scoped Topology"
        assert header_directives(header) == "open BigOperators\nopen Real\nopen scoped Topology"

    def test_set_option_is_kept(self) -> None:
        assert header_directives("import Mathlib\nset_option maxHeartbeats 400000") == (
            "set_option maxHeartbeats 400000"
        )

    def test_an_empty_header_gives_an_empty_string(self) -> None:
        assert header_directives("") == ""


@pytest.mark.skipif(
    not (DATA / "minif2f_test.jsonl").is_file(),
    reason="benchmarks not fetched; run `uv run python scripts/fetch_problems.py --all`",
)
class TestFetchedBenchmarks:
    """Against the statements actually on disk."""

    @pytest.mark.parametrize("name", BENCHMARKS)
    def test_every_statement_opens_a_tactic_block(self, name: str) -> None:
        rows = [json.loads(line) for line in (DATA / f"{name}.jsonl").read_text().splitlines()]
        assert rows
        for row in rows:
            assert row["formal_statement"].rstrip().endswith(":= by"), row["problem_id"]

    @pytest.mark.parametrize("name", BENCHMARKS)
    def test_no_deprecated_binder_survives(self, name: str) -> None:
        import re

        pattern = re.compile(r"[∑∏⨆⨅⋃⋂][^,]*?\bin\b")
        rows = [json.loads(line) for line in (DATA / f"{name}.jsonl").read_text().splitlines()]
        offenders = [r["problem_id"] for r in rows if pattern.search(r["formal_statement"])]
        assert not offenders, offenders[:5]

    @pytest.mark.parametrize("name", BENCHMARKS)
    def test_the_loader_reads_them(self, name: str) -> None:
        problems = load_problems(DATA / f"{name}.jsonl")
        assert len(problems) > 100
        assert all(p.problem_id and p.statement for p in problems)

    @pytest.mark.parametrize("name", BENCHMARKS)
    def test_no_placeholder_rows_survive(self, name: str) -> None:
        """The ports keep rows whose whole statement is commented out; 38 of them in total."""
        from onebigjump.lean.problems import has_declaration

        rows = [json.loads(line) for line in (DATA / f"{name}.jsonl").read_text().splitlines()]
        assert all(has_declaration(r["formal_statement"]) for r in rows)

    def test_putnam_carries_the_scopes_its_notation_needs(self) -> None:
        """`n !` and `u^T` live in scoped namespaces PutnamBench never opens."""
        rows = [
            json.loads(line) for line in (DATA / "putnambench_test.jsonl").read_text().splitlines()
        ]
        assert all("open scoped Nat Matrix" in r["directives"] for r in rows)

    @pytest.mark.parametrize("name", BENCHMARKS)
    def test_directives_never_contain_an_import(self, name: str) -> None:
        rows = [json.loads(line) for line in (DATA / f"{name}.jsonl").read_text().splitlines()]
        assert not any("import " in r["directives"] for r in rows)

    def test_putnam_solution_problems_are_flagged_not_dropped(self) -> None:
        """142 of 272 need the model to supply an answer term as well as a proof."""
        rows = [
            json.loads(line) for line in (DATA / "putnambench_test.jsonl").read_text().splitlines()
        ]
        flagged = [r for r in rows if r["requires_solution_term"]]
        assert 100 < len(flagged) < len(rows)

    def test_the_manifest_records_every_split(self) -> None:
        manifest = json.loads((DATA / "benchmarks.json").read_text())
        keys = {(b["benchmark"], b["split"]) for b in manifest["benchmarks"]}
        assert ("minif2f", "test") in keys
        assert ("proofnet", "test") in keys
        assert ("putnambench", "test") in keys
