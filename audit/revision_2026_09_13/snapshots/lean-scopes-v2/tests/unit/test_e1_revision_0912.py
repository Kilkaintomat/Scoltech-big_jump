"""Regressions for resource labels and multiline syntax found in main collection."""

import pytest

from onebigjump.e1.verification import verify_one
from onebigjump.lean.segmentation import segment_proof
from onebigjump.lean.verifier import _is_resource_error, verify_trace


@pytest.mark.parametrize(
    "body",
    [
        "  (try\n    trivial\n  )\n  done",
        "  exact (\n    True.intro\n  )\n  done",
        "  simp only [\n    Nat.add_zero\n  ]\n  done",
        "  refine ⟨\n    True.intro, True.intro\n  ⟩\n  done",
    ],
)
def test_unclosed_delimiter_joins_same_indent_closing_line(body):
    segments = segment_proof(body)
    assert len(segments) == 2
    assert segments[0].line_start == 0 and segments[0].line_end == 2
    assert segments[1].text == "done"


@pytest.mark.parametrize(
    "line",
    [
        'have s := "("',
        "have c := '('",
        "have «(» := True.intro",
        "skip -- (",
        "skip /- [ /- { -/ -/",
    ],
)
def test_inert_delimiters_cannot_swallow_following_tactic(line):
    assert len(segment_proof("  " + line + "\n  trivial")) == 2


@pytest.mark.parametrize(
    "message",
    [
        "(deterministic) timeout at `simp`, maximum number of heartbeats (400000) has been reached",
        "maximum recursion depth has been reached",
    ],
)
def test_lean_resource_diagnostics_are_not_mathematical_failures(message):
    assert _is_resource_error([message])

    class Repl:
        def command(self, text, timeout_s=None):
            return {"sorries": [{"proofState": 0}]}

        def tactic(self, text, state, timeout_s=None):
            return {"message": message}

    trace = verify_trace(
        Repl(),
        "  simp\n  trivial",
        trace_id="test",
        problem_id="test",
        header="example : True := by",
        check_whole_proof=False,
    )
    assert [s.status for s in trace.steps] == ["timeout", "unreached"]
    assert trace.t_star == 0 and trace.check_absorbing()


def test_mentions_of_timeout_are_not_resource_diagnostics():
    assert not _is_resource_error(["unknown identifier 'timeout'", "unsolved goals\n⊢ timeout = 1"])


@pytest.mark.parametrize("resource", [True, False])
def test_resource_disagreement_is_retained_and_only_known_cause_is_excluded(monkeypatch, resource):
    from onebigjump.e1 import verification
    from onebigjump.lean.schemas import ProofTrace, StepLabel, StepStatus, TraceOutcome

    class Repl:
        def command(self, text, timeout_s=None):
            if text.startswith("#check"):
                return {"message": "unknown identifier"}
            return {"messages": [{"severity": "info", "data": "t depends on axioms: []"}]}

    trace = ProofTrace(
        trace_id="x",
        problem_id="t",
        outcome=TraceOutcome.REFUTED,
        t_star=0,
        steps=[
            StepLabel(
                index=0,
                line_start=0,
                line_end=0,
                n_lines=1,
                tactic="trivial",
                valid=False,
                status=StepStatus.TIMEOUT if resource else StepStatus.ERROR,
            )
        ],
    )
    monkeypatch.setattr(verification, "verify_trace", lambda *a, **kw: trace)
    row = verify_one(
        Repl(),
        {
            "trace_id": "x",
            "temperature": 0.6,
            "attempt_index": 0,
            "finish_reason": "stop",
            "model_id": "fixture",
            "completion": "```lean4\ntheorem t : True := by\n  trivial\n```",
        },
        {"problem_id": "t", "directives": "", "statement": "theorem t : True := by"},
        {"max_heartbeats": 400000, "step_timeout_s": 60, "whole_timeout_s": 180},
    )
    assert row["whole_proof_ok"] and not row["replay_ok"]
    assert row["unexplained_disagreement"] == (not resource)
    assert row["explained_resource_disagreement"] == resource
    assert row["category"] == ("timeout_resource" if resource else "unsupported_segmentation")


def test_startup_retries_are_bounded_and_keep_failed_import_evidence(tmp_path):
    import sys

    from onebigjump.lean.environment import LeanEnvironment
    from onebigjump.lean.verifier import LeanREPL

    launcher = tmp_path / "fake-lake"
    counter = tmp_path / "counter"
    launcher.write_text(
        "#!" + sys.executable + "\n"
        "import json,sys,pathlib\n"
        "p=pathlib.Path("
        + repr(str(counter))
        + ")\n"
        "count=int(p.read_text())+1 if p.exists() else 1\n"
        "p.write_text(str(count))\n"
        "for line in sys.stdin:\n"
        " if not line.strip(): continue\n"
        " req=json.loads(line)\n"
        " response={'env':0}\n"
        " if req['env'] is not None and count==1:\n"
        "  response={'env':1,'message':'empty environment on first start'}\n"
        " print(json.dumps(response)+'\n',flush=True)\n".replace("+'\n'", "+'\\n'")
    )
    launcher.chmod(0o700)
    env = LeanEnvironment(
        workspace=tmp_path, project=tmp_path, repl_binary=launcher, lake=str(launcher)
    )
    with LeanREPL(env, startup_attempts=2, startup_timeout_s=5) as repl:
        assert [r["ok"] for r in repl.startup_diagnostics] == [False, True]
        assert repl.startup_diagnostics[0]["import_reply"] == {"env": 0}
        assert "empty environment" in repl.startup_diagnostics[0]["error"]
    assert repl._proc is None
