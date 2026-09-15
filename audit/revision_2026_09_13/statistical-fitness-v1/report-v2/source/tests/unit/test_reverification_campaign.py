"""The repaired lineage must preserve every original token and remain behind validation."""

import importlib.util
import json
from pathlib import Path

import pytest


def fixture_campaign(tmp_path):
    original = tmp_path / "old"
    tasks = {}
    for name in ("deepseek", "goedel", "kimina"):
        for phase in ("pilot", "main"):
            folder = original / name / phase
            (folder / "generation").mkdir(parents=True)
            (folder / "protocol.json").write_text('{"frozen":true}\n')
            (folder / "generation/samples").write_text("original tokens")
        for stage in ("verify", "extract"):
            for shard in range(8):
                key = name + "/main-" + stage + "-" + str(shard)
                tasks[key] = {
                    "model": name,
                    "stage": stage,
                    "state": "FAILED",
                    "job_id": "30",
                    "arguments": [stage, str(original / name)],
                    "dependencies": [name + "/main-generate-0"],
                    "partition": "ais-htc" if stage == "verify" else "ais-gpu",
                }
        for shard in range(8):
            key = name + "/main-generate-" + str(shard)
            tasks[key] = {
                "model": name,
                "stage": "generate",
                "state": "RUNNING" if shard == 7 else "COMPLETED",
                "job_id": str(shard + 1),
                "dependencies": [],
                "partition": "ais-gpu",
            }
        tasks[name + "/gate"] = {
            "model": name,
            "stage": "gate",
            "state": "COMPLETED",
            "job_id": "10",
            "arguments": ["gate", str(original / name)],
            "dependencies": [name + "/pilot-analyze"],
            "partition": "ais-htc",
        }
    (original / "queue.json").write_text(
        json.dumps(
            {
                "source": "old-source",
                "tasks": tasks,
                "partition_submit_caps": {"ais-gpu": 6, "ais-htc": 12},
                "gpu_submitted_per_model": 2,
            }
        )
    )
    script = Path(__file__).resolve().parents[2] / "scripts/campaign/reverify.py"
    spec = importlib.util.spec_from_file_location("reverify", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return original, module


def test_reverification_uses_live_generation_as_external_dependency_without_resampling(tmp_path):
    original, module = fixture_campaign(tmp_path)
    before = (original / "queue.json").read_bytes()
    target = tmp_path / "new"
    module.prepare(original, target, tmp_path / "storage", tmp_path / "source", "41", "42")
    queue = json.loads((target / "queue.json").read_text())
    assert (original / "queue.json").read_bytes() == before
    for name in ("deepseek", "goedel", "kimina"):
        for phase in ("pilot", "main"):
            assert (
                target / name / phase / "generation"
            ).resolve() == original / name / phase / "generation"
            assert (target / name / phase / "protocol.json").read_bytes() == (
                original / name / phase / "protocol.json"
            ).read_bytes()
            assert not list((target / name / phase / "verification").iterdir())
        assert queue["tasks"][name + "/pilot-smoke"]["dependencies"] == ["validation", "regression"]
        for shard in range(8):
            task = queue["tasks"][name + "/main-generate-" + str(shard)]
            assert task["external"] and task["job_id"] == str(shard + 1)
            assert "script" not in task and "arguments" not in task
            verify = queue["tasks"][name + "/main-verify-" + str(shard)]
            assert verify["job_id"] is None and name + "/gate" in verify["dependencies"]


def test_missing_generation_job_refuses_to_create_a_partial_lineage(tmp_path):
    original, module = fixture_campaign(tmp_path)
    path = original / "queue.json"
    queue = json.loads(path.read_text())
    queue["tasks"]["goedel/main-generate-7"]["job_id"] = None
    path.write_text(json.dumps(queue))
    with pytest.raises(ValueError, match="generation must"):
        module.prepare(
            original, tmp_path / "new", tmp_path / "storage", tmp_path / "source", "41", "42"
        )
    assert not (tmp_path / "new").exists()
