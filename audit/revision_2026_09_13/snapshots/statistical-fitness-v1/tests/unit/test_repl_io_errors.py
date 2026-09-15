"""Filesystem diagnostics must never become mathematical failure labels."""

import io
import json
from unittest.mock import Mock

import pytest

from onebigjump.lean.verifier import LeanREPL, ReplError, verify_trace


@pytest.mark.parametrize("channel", ["message", "messages", "proofStatus"])
@pytest.mark.parametrize(
    "diagnostic",
    [
        "failed to read file: Remote I/O error",
        "Input/output error",
        "Too many open files in system",
        "Stale file handle",
    ],
)
def test_io_diagnostics_fail_transport(channel, diagnostic):
    repl = LeanREPL(env=Mock())
    repl._proc = Mock(stdin=io.StringIO())
    if channel == "messages":
        reply = {"messages": [{"severity": "error", "data": diagnostic}]}
    else:
        reply = {channel: ("Error: " if channel == "proofStatus" else "") + diagnostic}
    repl._out.put(json.dumps(reply))
    with pytest.raises(ReplError, match="infrastructure diagnostic"):
        repl._exchange({"cmd": "example : True := by trivial"})


def test_io_error_during_tactic_has_no_mathematical_t_star():
    repl = LeanREPL(env=Mock())
    repl._proc = Mock(stdin=io.StringIO())
    repl._base_env = 0
    repl.restart = Mock()
    repl._out.put(json.dumps({"sorries": [{"proofState": 0}]}))
    repl._out.put(json.dumps({"message": "failed to read file: Remote I/O error"}))
    trace = verify_trace(
        repl,
        "  trivial\n  trivial",
        trace_id="io",
        problem_id="io",
        header="example : True := by",
        check_whole_proof=False,
    )
    assert trace.outcome.value == "repl_failure"
    assert trace.t_star is None
    assert len(trace.steps) == 1 and trace.steps[0].status.value == "unreached"
    repl.restart.assert_called_once()


def test_regular_kernel_failure_stays_a_reply():
    repl = LeanREPL(env=Mock())
    repl._proc = Mock(stdin=io.StringIO())
    reply = {"proofStatus": "Error: kernel type check failed"}
    repl._out.put(json.dumps(reply))
    assert repl._exchange({"cmd": "example : True := by trivial"}) == reply
