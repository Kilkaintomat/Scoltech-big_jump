"""Labelling Lean proofs with the kernel. Skipped when the toolchain is absent, never faked.

The REPL costs two to three minutes to import Mathlib, so the whole module shares one process.
"""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

import pytest

from onebigjump.lean import (
    LeanREPL,
    StepStatus,
    TraceOutcome,
    VerificationSummary,
    discover,
    verify_trace,
)

pytestmark = [pytest.mark.lean, pytest.mark.slow]

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def repl():
    env = discover(REPO / "lean_workspace")
    if not env.available:  # pragma: no cover - the collection hook usually catches this
        pytest.skip("; ".join(env.problems))
    with LeanREPL(env) as r:
        yield r


@pytest.fixture(scope="module")
def traces(repl) -> dict:
    path = REPO / "tests" / "fixtures" / "lean_proofs.jsonl"
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        req = json.loads(line)
        out[req["trace_id"]] = verify_trace(
            repl,
            req["proof"],
            trace_id=req["trace_id"],
            problem_id=req["problem_id"],
            model_id=req.get("model_id", ""),
            per_step_timeout_s=60.0,
        )
    return out


class TestOutcomes:
    @pytest.mark.parametrize("trace_id", ["ok-addcomm", "ok-multistep", "ok-structured", "ok-have"])
    def test_correct_proofs_verify(self, traces, trace_id: str) -> None:
        tr = traces[trace_id]
        assert tr.outcome == TraceOutcome.VERIFIED, tr.error or tr.steps
        assert tr.t_star is None
        assert all(s.valid for s in tr.steps)

    @pytest.mark.parametrize(
        "trace_id,expected_t_star",
        [("bad-first", 0), ("bad-middle", 1), ("bad-late", 2), ("bad-unsolved", 0)],
    )
    def test_broken_proofs_are_refuted_at_the_right_step(
        self, traces, trace_id: str, expected_t_star: int
    ) -> None:
        tr = traces[trace_id]
        assert tr.outcome == TraceOutcome.REFUTED
        assert tr.t_star == expected_t_star

    def test_a_type_mismatch_is_caught(self, traces) -> None:
        """The REPL reports these as a top-level `message`, not in `messages`."""
        step = traces["bad-middle"].steps[1]
        assert step.status == StepStatus.ERROR
        assert "type mismatch" in step.message.lower()

    def test_sorry_is_not_a_proof(self, traces) -> None:
        tr = traces["bad-sorry"]
        assert tr.outcome == TraceOutcome.REFUTED
        assert tr.steps[0].status == StepStatus.SORRY
        assert tr.whole_proof_ok, "it compiles, with a warning -- which is exactly the trap"

    def test_unsolved_goals_are_a_failure_of_the_last_step(self, traces) -> None:
        tr = traces["bad-unsolved"]
        assert tr.steps[-1].status == StepStatus.UNSOLVED_GOALS
        assert tr.t_star == tr.steps[-1].index

    def test_a_parse_error_is_discarded(self, traces) -> None:
        tr = traces["bad-parse"]
        assert tr.outcome == TraceOutcome.PARSE_ERROR
        assert tr.t_star is None


class TestLabelInvariants:
    def test_labels_are_absorbing_everywhere(self, traces) -> None:
        for tr in traces.values():
            assert tr.check_absorbing(), tr.trace_id

    def test_steps_after_t_star_are_marked_unreached(self, traces) -> None:
        for tr in traces.values():
            if tr.t_star is None:
                continue
            for step in tr.steps[tr.t_star + 1 :]:
                assert step.status == StepStatus.UNREACHED
                assert not step.valid

    def test_step_replay_agrees_with_whole_proof_compilation(self, traces) -> None:
        """Appendix B.2: the two must agree by construction. `sorry` is the documented exception."""
        for tr in traces.values():
            if not tr.labelled or tr.whole_proof_ok is None:
                continue
            if tr.t_star is not None and tr.steps[tr.t_star].status == StepStatus.SORRY:
                continue
            assert tr.whole_proof_ok == tr.verified, f"{tr.trace_id}: {tr.steps}"

    def test_line_spans_are_ordered_and_disjoint(self, traces) -> None:
        for tr in traces.values():
            spans = [(s.line_start, s.line_end) for s in tr.steps]
            for (_, end), (start, _) in pairwise(spans):
                assert start > end, tr.trace_id

    def test_structured_blocks_are_single_steps(self, traces) -> None:
        tr = traces["ok-structured"]
        assert tr.n_steps == 1
        assert tr.steps[0].is_structured
        assert tr.steps[0].n_lines == 3


class TestSummary:
    def test_categories_add_up(self, traces) -> None:
        s = VerificationSummary.from_traces(list(traces.values()))
        assert s.n_traces == len(traces)
        assert (
            s.verified + s.refuted + s.parse_error_discarded + s.timeout + s.repl_failure
            == s.n_traces
        )
        assert s.verified == 4
        assert s.parse_error_discarded == 1
        assert s.mean_trace_length > 0
