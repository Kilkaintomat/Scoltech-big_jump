"""Adversarial verification, task exchangeability, and exact interrupted-training recovery."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from onebigjump.e1.artifacts import read_json, verify_manifest, write_once
from onebigjump.e1.measurement import fit_transform, transformed_norms
from onebigjump.readiness import controls, deduction, p4, whitening


@pytest.fixture
def source(tmp_path):
    return write_once(
        tmp_path / "source-manifest.json",
        {
            "inputs": {},
            "outputs": {},
            "metrics": {"git_commit": "test", "git_branch": "test", "dirty": False},
        },
    )


@pytest.mark.parametrize("length", range(3, 13))
def test_symbolic_checker_rejects_skipped_or_invented_inference(length):
    problem = deduction.make_problem(length, "evaluation", 0)
    gold = "\n".join(f"Mira is {p}." for p in problem["gold_chain"])
    correct = deduction.check(gold + "\nAnswer: true<|im_end|>", problem)
    assert correct["verified"]
    assert [gold[s["start"] : s["end"]] for s in correct["step_spans"]] == gold.splitlines()
    bad = gold.splitlines()
    bad[0] = f"Mira is {problem['goal']}."
    failed = deduction.check("\n".join(bad), problem)
    assert failed["t_star"] == 0
    assert [s["valid"] for s in failed["steps"]] == [0] * length
    assert [s["status"] for s in failed["steps"][1:]] == ["unreached"] * (length - 1)
    assert deduction.check("Answer: true", problem)["category"] == "format_error"
    assert deduction.check(gold + "\nI have a secret rule.", problem)["category"] == "format_error"


def test_disjoint_population_and_shards_keep_all_attempts(tmp_path, source):
    write_once(
        tmp_path / "protocol.json",
        {
            "seed": 3,
            "calibration_per_length": 3,
            "evaluation_per_length": 4,
            "temperatures": [0.6, 1.0],
            "attempts_per_temperature": 2,
        },
    )
    deduction.population(tmp_path, source)
    planned = deduction.requests(tmp_path, "main")
    pilot = deduction.requests(tmp_path, "pilot")
    assert len(planned) == 280 and len(pilot) == 80
    assert not {x["problem"]["problem_id"] for x in planned} & {
        x["problem"]["problem_id"] for x in pilot
    }
    shards = [deduction.requests(tmp_path, "main", i, 8) for i in range(8)]
    ids = [x["trace_id"] for part in shards for x in part]
    assert len(ids) == len(set(ids)) == len(planned)
    assert set(ids) == {x["trace_id"] for x in planned}
    verify_manifest(tmp_path / "inputs/manifest.json")


def test_task_positional_null_removes_shared_end_of_trace_confound():
    frame = pd.DataFrame(
        [
            {
                "prompt_id": f"p{p}",
                "trace_id": f"p{p}-a{a}",
                "task_family": "f",
                "outcome": "refuted",
                "L": 4,
                "t": t,
                "t_star": 3,
                "z": t + 1,
                "surprisal": 4 - t,
            }
            for p in range(25)
            for a in range(3)
            for t in range(4)
        ]
    )
    result = controls.positional_null(frame, 99)
    assert result["n_tasks"] == 25
    assert result["jump_top1"] == result["null_jump_mean"] == result["p_jump"] == 1
    assert result["p_paired_gain"] == 1


def test_sparse_positional_strata_not_pooled():
    _, frame, _ = controls.simulated_cell("heavy_null", 9, tasks=2, attempts=2)
    frame.loc[frame["prompt_id"] == "evaluation:1", "task_family"] = "other"
    result = controls.positional_null(frame, 9)
    assert result["n_tasks"] == 0 and result["omitted_sparse_tasks"] == 2


@pytest.mark.parametrize("dimension", [3, 30])
def test_whitening_stress_matches_original_operator(dimension):
    rng = np.random.default_rng(3)
    states = [rng.normal(size=(5, dimension)) for _ in range(3)]
    evaluation = rng.normal(size=(7, dimension))
    expected = transformed_norms(evaluation, fit_transform(states, 0.1, 1.0))["whitened"]
    observed = whitening.norms(evaluation, whitening.fit_whitening(states, 0.1))
    np.testing.assert_allclose(observed, expected, rtol=1e-10, atol=1e-10)


def test_actual_calibration_pipeline_smoke(tmp_path, source):
    config = {
        "seed": 11,
        "datasets_per_shard": 1,
        "tasks": 20,
        "attempts": 2,
        "length": 8,
        "permutations": 9,
        "statistics": {
            "bootstrap": 2,
            "inner_bootstrap": 20,
            "min_tasks": 20,
            "min_k": 20,
            "valid_fraction": 0.9,
            "family_size": 9,
        },
    }
    controls.calibrate(tmp_path / "mc", config, source, "heavy_null", 0)
    verify_manifest(tmp_path / "mc/manifest.json")
    assert read_json(tmp_path / "mc/manifest.json")["metrics"]["datasets"] == 1


@pytest.mark.ml
def test_p4_resume_restores_weights_and_optimizer(tmp_path, source, monkeypatch):
    import torch

    config = {
        "seed": 2,
        "grokking": {
            "p": 5,
            "d_model": 8,
            "n_heads": 2,
            "d_mlp": 16,
            "steps": 100,
            "checkpoint_every": 25,
            "device": "cpu",
        },
    }
    original_save = torch.save
    count = 0

    def interrupted_save(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 3:
            raise RuntimeError("simulated node failure")
        return original_save(*args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(torch, "save", interrupted_save)
        with pytest.raises(RuntimeError, match="simulated node"):
            p4.train(tmp_path / "interrupted", config, source)
    p4.train(tmp_path / "interrupted", config, source)
    p4.train(tmp_path / "continuous", config, source)
    states = [
        torch.load(tmp_path / name / "step-000100.pt", weights_only=False)
        for name in ("interrupted", "continuous")
    ]
    for key in states[0]["model"]:
        assert torch.equal(states[0]["model"][key], states[1]["model"][key])
    for key in states[0]["optimizer"]["state"]:
        for field in states[0]["optimizer"]["state"][key]:
            assert torch.equal(
                states[0]["optimizer"]["state"][key][field],
                states[1]["optimizer"]["state"][key][field],
            )
    with pytest.raises(ValueError, match="immutable artifact"):
        p4.train(tmp_path / "interrupted", {**config, "seed": 3}, source)
    verify_manifest(tmp_path / "interrupted/manifest.json")
    p4.measure(tmp_path / "measurement", tmp_path / "interrupted", config, source)
    verify_manifest(tmp_path / "measurement/manifest.json")
    frequency = read_json(tmp_path / "measurement/frequencies.json")
    assert frequency["from_step"] == 100
    for step in (0, 25, 50, 75, 100):
        assert (
            read_json(tmp_path / "measurement" / f"step-{step:06d}.json")["key_frequencies"]
            == frequency["frequencies"]
        )


def test_expansion_graph_waits_for_validation_and_external_artifact(tmp_path):
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts/readiness/dispatch.py"
    spec = importlib.util.spec_from_file_location("expansion_dispatch_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tasks = {"tests": {"state": "RUNNING"}}
    artifact = tmp_path / "manifest.json"
    task = {
        "job_id": None,
        "state": "WAITING",
        "dependencies": ["tests"],
        "file_dependencies": [str(artifact)],
    }
    assert not module.ready(task, tasks)
    tasks["tests"]["state"] = "COMPLETED"
    assert not module.ready(task, tasks)
    artifact.write_text("{}")
    assert module.ready(task, tasks)
    task["state"] = "BLOCKED"
    assert not module.ready(task, tasks)
