"""Failures observed in the first three real prover pilots."""

import pytest

from onebigjump.e1.spans import SourceExclusion, formal_body
from onebigjump.lean.segmentation import segment_proof


@pytest.mark.parametrize("middle", ["\n  <;> ", " <;>\n  ", "\n  <;>\n  ", ";\n  "])
def test_multiline_combinator_keeps_its_operands_and_following_step(middle):
    proof = "  constructor" + middle + "trivial\n  done"
    segments = segment_proof(proof)
    assert len(segments) == 2
    assert "constructor" in segments[0].text and "trivial" in segments[0].text
    assert segments[0].has_combinator
    assert segments[1].text == "done"
    assert segments[0].line_end + 1 == segments[1].line_start


def test_comment_between_operator_and_operand_keeps_original_spans():
    text = "```lean4\ntheorem t : True ∧ True := by\n  constructor\n  <;> -- a comment\n  /- another -/\n  trivial\n```"
    parsed = formal_body(text, "theorem t : True ∧ True := by", "")
    assert len(parsed["step_spans"]) == 1
    span = parsed["step_spans"][0]
    assert text[span["start"] : span["end"]].startswith("constructor")
    assert text[span["start"] : span["end"]].endswith("trivial")


@pytest.mark.parametrize(
    "reasoning",
    [
        "```tactics\ntrivial\n```\n",
        "```python\nprint('example')\n```\n```tactics\ntrivial\n```\n",
        "<think>```lean4\ntheorem t : False := by sorry\n```\n```tactics\ntrivial\n```\n</think>\n",
    ],
)
def test_nonlean_reasoning_fences_do_not_swallow_the_final_declaration(reasoning):
    text = reasoning + "```lean4\ntheorem t : True := by\n  trivial\n```<|im_end|>"
    result = formal_body(text, "theorem t : True := by", "")
    assert result["body"].strip() == "trivial"
    span = result["step_spans"][0]
    assert text[span["start"] : span["end"]] == "trivial"


def test_final_statement_substitution_still_fails():
    text = "```tactics\ntrivial\n```\n```lean4\ntheorem t : True := by trivial\n```"
    with pytest.raises(SourceExclusion, match="differs"):
        formal_body(text, "theorem t : False := by", "")


def test_semicolon_inside_string_does_not_join_following_tactic():
    assert len(segment_proof('  have s := ";"\n  trivial')) == 2


def test_multiline_string_is_lexed_as_a_whole_before_operator_detection():
    proof = '  have s := "hello\n    world;"\n  trivial'
    assert len(segment_proof(proof)) == 2


def test_gather_resume_cannot_hide_recorded_disagreement(tmp_path, monkeypatch):
    from onebigjump.e1 import campaign
    from onebigjump.e1.artifacts import write_once

    write_once(
        tmp_path / "main/verification/manifest.json", {"metrics": {"unexplained_disagreements": 1}}
    )
    monkeypatch.setattr(campaign, "completed", lambda path: True)
    with pytest.raises(ValueError, match="recorded verifier disagreements"):
        campaign.gather(tmp_path, "main", tmp_path / "source-manifest.json", "verification", 2)


@pytest.mark.parametrize("category", ["infrastructure_error", "infrastructure_failure"])
def test_collection_gate_rejects_infrastructure_errors_before_activation_checks(
    tmp_path, monkeypatch, category
):
    from onebigjump.e1 import campaign

    label = {"trace_id": "a", "category": category, "unexplained_disagreement": False}
    monkeypatch.setattr(campaign, "configuration", lambda *args: {})
    monkeypatch.setattr(campaign, "completed", lambda path: path.name != "collection-gate")
    monkeypatch.setattr(campaign, "generation_inputs", lambda *args: ([{"trace_id": "a"}], []))
    monkeypatch.setattr(campaign, "rows", lambda path: [label])
    with pytest.raises(ValueError, match="infrastructure failure"):
        campaign.collection_gate(tmp_path, tmp_path / "source-manifest.json")


def test_recovery_preserves_generation_and_protocols_without_reusing_failed_labels(tmp_path):
    import importlib.util
    import json
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts/campaign/recover.py"
    spec = importlib.util.spec_from_file_location("recovery", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = tmp_path / "original"
    old.mkdir()
    tasks = {}
    for name in ("deepseek", "goedel", "kimina"):
        for phase in ("pilot", "main"):
            folder = old / name / phase
            folder.mkdir(parents=True)
            (folder / "protocol.json").write_text('{"frozen":true}\n')
        (old / name / "pilot/generation").mkdir()
        tasks[name + "/gate"] = {
            "model": name,
            "stage": "gate",
            "job_id": "12",
            "state": "FAILED",
            "dependencies": ["prepare", name + "/pilot-analyze"],
            "arguments": ["gate", str(old / name)],
        }
    (old / "queue.json").write_text(
        json.dumps(
            {
                "tasks": tasks,
                "partition_submit_caps": {"ais-gpu": 6, "ais-htc": 12},
                "gpu_submitted_per_model": 2,
            }
        )
    )
    target = tmp_path / "recovery"
    module.prepare(old, target, tmp_path / "storage", tmp_path / "snapshot", "42")
    queue = json.loads((target / "queue.json").read_text())
    for name in ("deepseek", "goedel", "kimina"):
        assert (target / name / "pilot/generation").resolve() == old / name / "pilot/generation"
        assert (target / name / "pilot/protocol.json").read_bytes() == (
            old / name / "pilot/protocol.json"
        ).read_bytes()
        assert not list((target / name / "pilot/verification").iterdir())
        assert queue["tasks"][name + "/gate"]["job_id"] is None
        assert queue["tasks"][name + "/pilot-smoke"]["dependencies"] == ["validation"]


def test_overshoot_intervals_count_exceeding_tasks_not_all_evaluation_tasks(monkeypatch):
    import numpy as np
    import pandas as pd

    from onebigjump.e1 import main_analysis

    # Many attempts of one failing task must not manufacture 20 independent tail tasks.
    rows = []
    for task in range(20):
        for attempt in range(6):
            rows.append(
                {
                    "prompt_id": str(task),
                    "trace_id": f"{task}:{attempt}",
                    "outcome": "refuted",
                    "t": 0,
                    "t_star": 0,
                    "z": 100 + attempt if task == 0 else 0.01,
                    "surprisal": 1.0,
                }
            )
    evaluation = pd.DataFrame(rows)
    calibration = evaluation.copy()
    calibration["outcome"] = "verified"
    calibration["z"] = np.linspace(1, 2, len(calibration))
    monkeypatch.setattr(main_analysis, "estimate", lambda *args: np.array([0.2, 0.2, 0.2]))
    config = {
        "seed": 42,
        "statistics": {
            "bootstrap": 2,
            "min_tasks": 20,
            "valid_fraction": 0.5,
            "min_k": 20,
            "inner_bootstrap": 2,
        },
    }
    result = main_analysis.bootstrap_cell(calibration, evaluation, config)["P3"]["0.01"]
    assert result["positive_excess_tasks"] == 1
    assert result["shape"]["n_tasks"] == 1
    assert result["shape"]["ci95"] is None
    assert result["difference_from_pooled_gpd"]["ci_family"] is None


@pytest.mark.parametrize("eos", ["<｜end▁of▁sentence｜>", "<|im_end|>", "<|eot_id|>", "</s>", ""])
def test_final_fence_accepts_original_model_eos_and_never_falls_back_to_earlier_sorry(eos):
    statement = "theorem t : True := by"
    text = (
        "```lean4\n"
        + statement
        + "\n  sorry\n```\nFinal proof:\n```lean4\n"
        + statement
        + "\n  trivial\n```"
        + eos
    )
    result = formal_body(text, statement, "")
    assert result["body"].strip() == "trivial"
    span = result["step_spans"][0]
    assert text[span["start"] : span["end"]] == "trivial"


def test_nonregular_gpd_is_diagnostic_only_in_pilot_and_main(monkeypatch):
    from types import SimpleNamespace

    import numpy as np
    import pandas as pd

    from onebigjump.e1 import analysis, main_analysis

    selection = SimpleNamespace(k=20, as_dict=lambda: {"k": 20})
    monkeypatch.setattr(analysis, "select_k", lambda *args, **kwargs: selection)
    monkeypatch.setattr(main_analysis, "select_k", lambda *args, **kwargs: selection)
    x = np.concatenate([np.linspace(1, 2, 60), np.linspace(100, 101, 20)])
    frame = pd.DataFrame({"z": x, "prompt_id": ["t"] * 80, "trace_id": ["a"] * 80})
    config = {"seed": 42, "statistics": {"inner_bootstrap": 2, "min_k": 20}}
    point = analysis.tail(frame, config)
    assert point["gpd"] is None
    assert point["gpd_fit"]["gamma"] < -1
    assert not point["gpd_fit"]["converged"]
    assert "nonregular" in point["fit_errors"]["gpd"]
    assert np.isnan(main_analysis.estimate(x, config, 42)[2])


def test_failed_overshoot_fits_do_not_enter_bootstrap_intervals(monkeypatch):
    import numpy as np
    import pandas as pd

    from onebigjump.e1 import main_analysis
    from onebigjump.stats.gpd import GPDFit

    rows = [
        {
            "prompt_id": str(task),
            "trace_id": f"{task}:{attempt}",
            "outcome": "refuted",
            "t": 0,
            "t_star": 0,
            "z": 100 + attempt,
            "surprisal": 1.0,
        }
        for task in range(20)
        for attempt in range(6)
    ]
    evaluation = pd.DataFrame(rows)
    calibration = evaluation.copy()
    calibration["outcome"] = "verified"
    calibration["z"] = np.linspace(1, 2, len(calibration))
    monkeypatch.setattr(main_analysis, "estimate", lambda *args: np.array([0.2, 0.2, 0.2]))
    monkeypatch.setattr(
        main_analysis,
        "gpd_fit",
        lambda *args, **kwargs: GPDFit(
            gamma=-6,
            sigma=100,
            threshold=2,
            n_excesses=120,
            loglik=-100,
            converged=False,
            message="nonregular endpoint",
        ),
    )
    config = {
        "seed": 42,
        "statistics": {
            "bootstrap": 2,
            "min_tasks": 20,
            "valid_fraction": 0.5,
            "min_k": 20,
            "inner_bootstrap": 2,
        },
    }
    result = main_analysis.bootstrap_cell(calibration, evaluation, config)["P3"]["0.01"]
    assert result["positive_excess_tasks"] == 20
    assert result["shape"]["valid"] == 0
    assert result["difference_from_pooled_gpd"]["valid"] == 0
    assert result["shape"]["ci95"] is None
