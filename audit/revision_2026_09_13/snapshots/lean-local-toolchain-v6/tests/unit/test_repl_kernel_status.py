"""A kernel failure must stop replay at its actual step, even with empty goals."""

from unittest.mock import Mock

import pytest

from onebigjump.lean.verifier import _errors, verify_trace


@pytest.mark.parametrize("status", ["Completed", "Running", "", None])
def test_nonerror_proof_status(status):
    assert _errors({"proofStatus": status}) == []


def test_all_error_channels_are_retained():
    assert _errors(
        {
            "messages": [{"severity": "error", "data": "elaboration"}],
            "message": " hard failure ",
            "proofStatus": "Error: kernel failure",
        }
    ) == ["elaboration", "hard failure", "Error: kernel failure"]


@pytest.mark.parametrize("bad_index", [0, 1])
def test_kernel_error_is_absorbing_without_replaying_suffix(bad_index):
    repl = Mock()
    repl.command.return_value = {"sorries": [{"proofState": 0}]}
    repl.tactic.side_effect = [
        {"proofState": 1, "goals": ["True"], "proofStatus": "Running"}
    ] * bad_index + [
        {"proofState": 2, "goals": [], "proofStatus": "Error: kernel type check failed"}
    ]
    trace = verify_trace(
        repl,
        "  have h : True := True.intro\n  exact h\n  trivial",
        trace_id="kernel",
        problem_id="kernel",
        header="example : True := by",
        check_whole_proof=False,
    )
    assert trace.t_star == bad_index and not trace.verified
    assert [s.status.value for s in trace.steps] == (
        ["ok"] * bad_index + ["error"] + ["unreached"] * (2 - bad_index)
    )
    assert repl.tactic.call_count == bad_index + 1
    assert trace.check_absorbing()
