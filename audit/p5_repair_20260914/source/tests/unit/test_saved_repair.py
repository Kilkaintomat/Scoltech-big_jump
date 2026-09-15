"""Regressions for data-name case, source preservation, and dependent tactic syntax."""

import pytest

from onebigjump.e1.spans import SourceExclusion
from onebigjump.e1.verification import theorem_name
from onebigjump.lean.segmentation import segment_proof


@pytest.mark.parametrize("name", ["notEquiv", "ns.Mixed", "«Mixed name»", "name'"])
def test_trusted_name_preserves_case_and_quoting(name):
    assert theorem_name({"statement": f"theorem {name} : True := by"}) == name


def test_anonymous_statement_does_not_invent_a_kernel_name():
    with pytest.raises(SourceExclusion):
        theorem_name({"statement": "example : True := by"})


@pytest.mark.parametrize(
    "proof",
    [
        "  constructor\n<;> trivial",
        "  constructor\n <;> trivial",
        "  skip\n; skip",
        "  (skip\n)",
        "  first\n| skip",
    ],
)
def test_dedenting_never_deletes_non_whitespace_source(proof):
    assert "".join(proof.split()) == "".join("".join(s.text.split()) for s in segment_proof(proof))


def test_all_goals_keeps_its_operand_and_next_step_boundary():
    segments = segment_proof("  constructor\n  all_goals\n  trivial\n  skip")
    assert [s.text for s in segments] == ["constructor", "all_goals\ntrivial", "skip"]
    assert [(s.line_start, s.line_end) for s in segments] == [(0, 0), (1, 2), (3, 3)]


def test_slow_lane_does_not_own_later_pending_samples(monkeypatch):
    from threading import Event

    from onebigjump.e1 import parallel_verification as pv

    released = Event()

    class Fake:
        def __init__(self, *args, **kwargs):
            self.startup_diagnostics = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def verify(repl, sample, problem, settings):
        if sample["trace_id"] == "0":
            assert released.wait(3), "pending work is stranded behind the slow sample"
        if sample["trace_id"] == "2":
            released.set()
        return {"trace_id": sample["trace_id"]}

    monkeypatch.setattr(pv, "LeanREPL", Fake)
    monkeypatch.setattr(pv, "discover", lambda p: p)
    monkeypatch.setattr(pv, "verify_one", verify)
    samples = [
        {"trace_id": str(i), "problem_id": "p", "role": "evaluation", "task_family": "f"}
        for i in range(4)
    ]
    result = list(
        pv.verify_stream(samples, {"p": {}}, {"workspace": ".", "startup_timeout_s": 1}, 2)
    )
    assert {r["trace_id"] for r in result} == {"0", "1", "2", "3"}
