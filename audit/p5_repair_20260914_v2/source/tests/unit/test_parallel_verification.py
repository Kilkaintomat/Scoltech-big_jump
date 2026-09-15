"""A worker owns its Lean process; exceptions prevent silent loss."""

from threading import Lock

import pytest

from onebigjump.e1 import parallel_verification as pv


def setup_fake(monkeypatch, fail=False):
    closed, owners = [], {}
    lock = Lock()

    class Fake:
        def __init__(self, *args, **kwargs):
            self.live = False
            self.startup_diagnostics = [{"ok": True}]

        def __enter__(self):
            self.live = True
            return self

        def __exit__(self, *args):
            self.live = False
            closed.append(self)

    def verify(repl, sample, problem, settings):
        assert repl.live
        with lock:
            assert repl not in owners
            owners[repl] = sample["trace_id"]
        try:
            if fail and sample["trace_id"] == "2":
                raise RuntimeError("worker failed")
            return {"trace_id": sample["trace_id"], "category": "verified"}
        finally:
            with lock:
                owners.pop(repl)

    monkeypatch.setattr(pv, "LeanREPL", Fake)
    monkeypatch.setattr(pv, "discover", lambda workspace: workspace)
    monkeypatch.setattr(pv, "verify_one", verify)
    return closed


def samples(n):
    return [
        {"trace_id": str(i), "problem_id": "p", "role": "evaluation", "task_family": "f"}
        for i in range(n)
    ]


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_each_trace_once_and_all_processes_closed(monkeypatch, workers):
    closed = setup_fake(monkeypatch)
    result = list(
        pv.verify_stream(
            samples(23), {"p": {}}, {"workspace": ".", "startup_timeout_s": 10}, workers
        )
    )
    assert sorted(int(r["trace_id"]) for r in result) == list(range(23))
    assert len(closed) == workers
    assert all(r["execution"]["workers"] == workers for r in result)


def test_worker_failure_propagates_and_closes_processes(monkeypatch):
    closed = setup_fake(monkeypatch, fail=True)
    with pytest.raises(RuntimeError, match="worker failed"):
        list(
            pv.verify_stream(samples(9), {"p": {}}, {"workspace": ".", "startup_timeout_s": 10}, 4)
        )
    assert len(closed) == 4


def test_invalid_and_empty_inputs(monkeypatch):
    closed = setup_fake(monkeypatch)
    assert list(pv.verify_stream([], {}, {}, 4)) == []
    assert not closed
    with pytest.raises(ValueError, match="workers"):
        list(pv.verify_stream(samples(1), {}, {}, 9))
    with pytest.raises(ValueError, match="duplicate"):
        list(pv.verify_stream(samples(1) * 2, {}, {}, 1))
