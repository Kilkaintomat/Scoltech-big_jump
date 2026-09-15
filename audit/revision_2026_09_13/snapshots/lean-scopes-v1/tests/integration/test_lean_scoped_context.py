"""Scoped notation must survive replay without exposing the answer or leaking contexts."""

from pathlib import Path

import pytest

from onebigjump.lean import LeanREPL, discover, verify_trace
from onebigjump.lean.verifier import _errors

pytestmark = [pytest.mark.lean, pytest.mark.slow]


@pytest.fixture(scope="module")
def repl():
    with LeanREPL(discover(Path(__file__).resolve().parents[2] / "lean_workspace")) as r:
        yield r


@pytest.mark.parametrize("directive", ["open Topology", "open scoped Topology"])
def test_scoped_notation_in_body_and_statement(repl, directive):
    trace = verify_trace(
        repl,
        "  have h : (𝓝 (0 : ℝ)) = 𝓝 0 := rfl\n  exact h",
        trace_id="notation",
        problem_id="notation",
        header=directive + "\nexample : (𝓝 (0 : ℝ)) = 𝓝 0 := by",
    )
    assert trace.whole_proof_ok and trace.verified, trace.model_dump()
    assert trace.t_star is None and all(s.valid for s in trace.steps)


@pytest.mark.parametrize("directive", ["open Topology", "open scoped Topology"])
def test_both_false_still_localize_later_error(repl, directive):
    trace = verify_trace(
        repl,
        "  have h : (𝓝 (0 : ℝ)) = 𝓝 0 := rfl\n  exact Nat.zero_ne_one rfl\n  trivial",
        trace_id="later-error",
        problem_id="later-error",
        header=directive + "\nexample : True := by",
    )
    assert not trace.whole_proof_ok and not trace.verified
    assert trace.t_star == 1, trace.model_dump()
    assert [str(s.status.value) for s in trace.steps] == ["ok", "error", "unreached"]
    assert trace.check_absorbing()


def test_scoped_bigoperators_and_namespace(repl):
    trace = verify_trace(
        repl,
        "  have h : (∑ i ∈ Finset.range 0, i) = (0 : ℕ) := by simp\n  exact h",
        trace_id="operators",
        problem_id="operators",
        header="open scoped BigOperators\nnamespace ContextProbe\nexample : (∑ i ∈ Finset.range 0, i) = (0 : ℕ) := by",
    )
    assert trace.whole_proof_ok and trace.verified, trace.model_dump()


def test_answer_constant_is_unavailable_to_replay(repl):
    opened = repl.command("open scoped Topology\ntheorem noSelfAnswer : True := by sorry")
    assert not _errors(opened)
    response = repl.tactic("exact noSelfAnswer", opened["sorries"][0]["proofState"])
    assert _errors(response), response
    assert _errors(repl.command("#check noSelfAnswer"))


def test_scoped_activations_do_not_leak_to_other_commands(repl):
    opened = repl.command("open scoped Topology\nexample : True := by sorry")
    response = repl.tactic("have h : (𝓝 (0 : ℝ)) = 𝓝 0 := rfl", opened["sorries"][0]["proofState"])
    assert not _errors(response), response
    isolated = repl.command("example : True := by sorry")
    response = repl.tactic(
        "have h : (𝓝 (0 : ℝ)) = 𝓝 0 := rfl", isolated["sorries"][0]["proofState"]
    )
    assert _errors(response), response
