from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from onebigjump.e1.artifacts import write_once
from onebigjump.e1.campaign import require_collection_gate
from onebigjump.e1.generation import planned_requests, prompt_content
from onebigjump.e1.main_analysis import intervals, paired_scores, subsets


def test_main_shards_preserve_budget_seeds_and_exclude_incompatible_statements(tmp_path: Path):
    problems = [
        {"problem_id": f"p{i}", "eligible": True, "role": "calibration" if i < 4 else "evaluation"}
        for i in range(10)
    ]
    write_once(tmp_path / "inputs/problems.json", problems)
    write_once(
        tmp_path / "inputs/splits.json",
        {
            "calibration": ["p0", "p1", "p2", "p3"],
            "evaluation": [f"p{i}" for i in range(4, 10)],
            "pilot_calibration": ["p0"],
            "pilot_evaluation": ["p4"],
        },
    )
    config = {
        "main_attempts": 8,
        "pilot_attempts": 2,
        "seed": 42,
        "temperatures": [0.6, 1.0],
        "statement_exclusions": ["p9"],
    }
    whole = planned_requests(tmp_path, "main", config)
    sharded = [r for s in range(8) for r in planned_requests(tmp_path, "main", config, s, 8)]
    assert len(whole) == 9 * 16
    assert {r["trace_id"]: r["seed"] for r in whole} == {r["trace_id"]: r["seed"] for r in sharded}
    assert len(sharded) == len({r["trace_id"] for r in sharded})
    assert all(r["problem_id"] != "p9" for r in whole)


def test_kimina_prompt_uses_trusted_statement_and_informal_text():
    problem = {
        "statement": "theorem example_name : True := by",
        "directives": "",
        "informal_statement": "Prove the proposition.",
    }
    config = {"lean": {"max_heartbeats": 400000}, "prompt_style": "kimina"}
    text = prompt_content(problem, config)
    assert "# Problem:Prove the proposition." in text
    assert "theorem example_name : True := by" in text
    assert "import Mathlib" in text


def test_small_task_intervals_do_not_fall_back_to_attempts():
    config = {"statistics": {"min_tasks": 20, "valid_fraction": 0.9, "family_size": 9}}
    small = intervals(np.arange(500.0), config, 19)
    assert small["ci95"] is None
    assert small["ci_family"] is None
    valid = intervals(np.arange(500.0), config, 20)
    assert valid["ci_family"][0] < valid["ci95"][0]
    failed = intervals(np.r_[np.ones(449), np.full(51, np.nan)], config, 30)
    assert failed["ci95"] is None


def test_paired_scores_keep_attempts_together_within_task():
    frame = pd.DataFrame(
        [
            {
                "trace_id": trace,
                "prompt_id": task,
                "t": t,
                "t_star": 1,
                "z": z,
                "surprisal": surprise,
                "outcome": "refuted",
            }
            for trace, task in (("a1", "a"), ("a2", "a"), ("b1", "b"))
            for t, z, surprise in ((0, 1.0, 3.0), (1, 4.0, 1.0), (2, 2.0, 2.0))
        ]
    )
    assert paired_scores(frame) == {"a": [1.0, 1.0], "b": [1.0]}
    parts = subsets(frame)
    assert len(parts["pre"]) == 3
    assert len(parts["at"]) == 3
    assert len(parts["post"]) == 3


def test_main_cannot_start_without_completed_gate(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        require_collection_gate(tmp_path, tmp_path / "source-manifest.json")


def test_joint_bootstrap_uses_real_task_groups_and_writes_full_hill_grid():
    from onebigjump.e1.main_analysis import bootstrap_cell

    rng = np.random.default_rng(901)
    records = []
    for task in range(20):
        for attempt, outcome in enumerate(("verified", "refuted")):
            for t in range(5):
                records.append(
                    {
                        "trace_id": f"task{task}:a{attempt}",
                        "prompt_id": str(task),
                        "t": t,
                        "t_star": 2 if outcome == "refuted" else np.nan,
                        "outcome": outcome,
                        "z": 1 + rng.pareto(3),
                        "surprisal": float(rng.uniform(0, 3)),
                    }
                )
    evaluation = pd.DataFrame(records)
    calibration = evaluation[evaluation["outcome"] == "verified"].copy()
    calibration["prompt_id"] = "cal-" + calibration["prompt_id"]
    config = {
        "seed": 123,
        "statistics": {
            "min_tasks": 20,
            "min_k": 20,
            "valid_fraction": 0.9,
            "bootstrap": 4,
            "inner_bootstrap": 4,
            "family_size": 9,
        },
    }
    result = bootstrap_cell(calibration, evaluation, config)
    assert result["k_reselected_each_replicate"]
    assert result["conditional_on_fitted_transform"]
    assert result["P1"]["verified"]["hill"]["replicates"] == 4
    assert result["P1"]["verified"]["hill_bands"]["k"] == list(range(20, 51))
    assert result["P2_paired_difference"]["n_tasks"] == 20


@pytest.mark.parametrize("defect", ["none", "missing", "duplicate"])
def test_gather_rejects_incomplete_or_duplicate_shards_and_preserves_rows(
    tmp_path: Path, monkeypatch, defect
):
    from onebigjump.e1 import campaign
    from onebigjump.e1.artifacts import Journal, digest, identity, read_json
    from onebigjump.e1.stages import rows

    source = write_once(
        tmp_path / "source-manifest.json",
        {
            "inputs": {},
            "outputs": {},
            "metrics": {"git_commit": "fixture", "git_branch": "fixture", "dirty": False},
        },
    )
    samples = [{"trace_id": "a"}, {"trace_id": "b"}]
    monkeypatch.setattr(campaign, "generation_inputs", lambda root, phase: (samples, []))
    for i in range(2):
        directory = tmp_path / "main/verification" / f"shard-{i:03d}-of-002"
        if defect == "missing" and i == 1:
            continue
        rid = "a" if i == 0 or defect == "duplicate" else "b"
        with Journal(directory / "labels.jsonl", {"fixture": True, "shard": i}) as journal:
            journal.append(
                {"trace_id": rid, "unexplained_disagreement": False, "category": "verified"},
                identity(rid),
            )
        write_once(
            directory / "manifest.json",
            {
                "inputs": {},
                "outputs": {str(p): digest(p) for p in directory.glob("*.json*")},
                "metrics": {"attempts": 1},
            },
        )
    if defect != "none":
        with pytest.raises(ValueError, match=r"incomplete|duplicate"):
            campaign.gather(tmp_path, "main", source, "verification", 2)
    else:
        campaign.gather(tmp_path, "main", source, "verification", 2)
        assert [r["trace_id"] for r in rows(tmp_path / "main/verification/labels.jsonl")] == [
            "a",
            "b",
        ]
        assert read_json(tmp_path / "main/verification/manifest.json")["metrics"]["attempts"] == 2
