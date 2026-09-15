"""Admission order changes do not bypass dependencies or the GPU submission cap."""

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace


def controller():
    path = Path(os.environ.get("OBJ_DISPATCH_CANDIDATE", "scripts/readiness/dispatch.py"))
    spec = importlib.util.spec_from_file_location("priority_controller_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reserved_pilot_slot_and_task_source(tmp_path, monkeypatch):
    module = controller()
    calls = []
    tasks = {
        "validation": {"external": True, "job_id": "1", "state": "COMPLETED"},
        "p4": {
            "partition": "ais-gpu",
            "job_id": None,
            "state": "WAITING",
            "dependencies": ["validation", "pilot-extract"],
            "group": "other",
            "job_name": "p4",
            "arguments": ["p4-train", "p4"],
            "submission_priority": 10,
        },
        "pilot-extract": {
            "partition": "ais-gpu",
            "job_id": None,
            "state": "WAITING",
            "dependencies": ["pilot"],
            "group": "other",
            "job_name": "extract",
            "arguments": ["deduction-extract", "extract"],
            "submission_priority": -10,
        },
        "pilot": {
            "partition": "ais-gpu",
            "job_id": None,
            "state": "WAITING",
            "dependencies": ["validation"],
            "group": "other",
            "job_name": "pilot",
            "arguments": ["deduction-generate", "pilot"],
            "submission_priority": -10,
            "hours": 2,
            "nice": 0,
            "source": "/frozen/pilot",
        },
        "unrelated": {
            "partition": "ais-gpu",
            "job_id": None,
            "state": "WAITING",
            "dependencies": ["validation"],
            "group": "other",
            "job_name": "later",
            "arguments": ["later", "later"],
            "submission_priority": 20,
        },
    }
    queue = {
        "source": "/frozen/default",
        "tasks": tasks,
        "partition_submit_caps": {"ais-gpu": 1},
        "calibration_submit_cap": 2,
    }
    host = SimpleNamespace(
        ACTIVE={"RUNNING", "PENDING"},
        FAILED={"FAILED"},
        poll=lambda q: None,
        write=lambda p, q: None,
    )

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b"42\n", stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", run)
    module.tick(tmp_path, queue, host)
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert "--job-name=pilot" in command
    assert "--time=2:00:00" in command and "--nice=0" in command
    assert "/frozen/pilot/scripts/readiness/run.sbatch" in command
    assert kwargs["env"]["E1_SNAPSHOT"] == "/frozen/pilot"
    assert tasks["p4"]["job_id"] is None
    assert tasks["pilot-extract"]["job_id"] is None
    assert tasks["unrelated"]["job_id"] is None
    module.tick(tmp_path, queue, host)
    assert len(calls) == 1
