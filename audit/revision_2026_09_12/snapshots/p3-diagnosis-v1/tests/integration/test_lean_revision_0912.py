"""Live checks of the same options and tactic boundaries used by the repaired verifier."""

from pathlib import Path

import pytest

from onebigjump.lean import LeanREPL, discover, verify_trace

pytestmark = [pytest.mark.lean, pytest.mark.slow]


@pytest.fixture(scope="module")
def repl():
    with LeanREPL(discover(Path(__file__).resolve().parents[2] / "lean_workspace")) as r:
        yield r


def test_explicit_replay_budget_reaches_lean_tactic_context(repl):
    body = """  run_tac do
    let budget := (← getOptions).getNat `maxHeartbeats 0
    unless budget == 400000 do throwError "wrong heartbeat budget {budget}"
  trivial"""
    trace = verify_trace(
        repl,
        body,
        trace_id="budget",
        problem_id="budget",
        header="set_option maxHeartbeats 400000\nexample : True := by",
        max_heartbeats=400000,
    )
    assert trace.verified, trace.model_dump()
    assert trace.whole_proof_ok


@pytest.mark.parametrize("body", ["  (try\n    trivial\n  )", "  exact (\n    True.intro\n  )"])
def test_parenthesized_segment_agrees_with_whole_proof(repl, body):
    trace = verify_trace(
        repl,
        body,
        trace_id="parens",
        problem_id="parens",
        header="example : True := by",
        max_heartbeats=400000,
    )
    assert trace.whole_proof_ok and trace.verified, trace.model_dump()
    assert len(trace.steps) == 1
