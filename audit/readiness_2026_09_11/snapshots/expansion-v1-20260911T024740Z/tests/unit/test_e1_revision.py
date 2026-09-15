"""Regressions for invalid measurement, corrupt provenance and independent calibration."""

import numpy as np
import pandas as pd
import pytest

from onebigjump.e1.analysis import tail
from onebigjump.e1.artifacts import Journal, finish, write_once
from onebigjump.e1.measurement import fit_transform, transformed_norms
from onebigjump.e1.spans import SourceExclusion, formal_body
from onebigjump.e1.stages import completed, configuration, rows
from onebigjump.experiments.p5_length_law import fit_length_law
from onebigjump.lean.segmentation import strip_comments
from onebigjump.lean.verifier import LeanREPL, ReplError, _is_sorry
from onebigjump.stats import select_k


def test_comments_cannot_join_lean_identifiers_or_damage_quoted_names():
    assert strip_comments("exact/- comment -/h").split() == ["exact", "h"]
    assert "«x--y»" in strip_comments("exact «x--y» -- comment")
    assert not _is_sorry({"proofStatus": "Completed"}, "have «sorry» := True.intro; exact «sorry»")


def test_unterminated_source_is_not_silently_repaired():
    with pytest.raises(SourceExclusion):
        formal_body(
            "'''lean4\ntheorem t : True := by\n /- broken\n'''".replace("'''", "```"),
            "theorem t : True := by",
            "",
        )


def test_command_uses_environment_created_during_timeout_recovery():
    repl = object.__new__(LeanREPL)
    repl._desynced = True
    repl._base_env = 4
    payloads = []

    def recover():
        repl._base_env = 9
        repl._desynced = False

    repl._recover = recover
    repl._exchange = lambda payload, timeout_s=None: payloads.append(payload) or {}
    repl.command("example : True := by trivial")
    assert payloads[0]["env"] == 9


def test_tactic_refuses_proof_state_from_restarted_process():
    repl = object.__new__(LeanREPL)
    repl._desynced = True
    repl.restarts = 0

    def recover():
        repl.restarts += 1
        repl._desynced = False

    repl._recover = recover
    with pytest.raises(ReplError, match="lost after"):
        repl.tactic("trivial", 7)


def test_p5_retains_rate_without_fabricating_an_impossible_tolerance():
    z = np.random.default_rng(22).pareto(3, size=500) + 1
    fit = fit_length_law({3: (1, 100), 4: (1, 100), 5: (1, 100)}, z, k=40, theta=0.01)
    assert fit.converged and fit.rate_per_step > fit.theta
    assert fit.tolerance_status == "incompatible_rate_exceeds_theta"
    assert np.isnan(fit.tau) and np.isnan(fit.fbar_tau)


@pytest.mark.parametrize("theta", [0, -1, 1.1, np.nan])
def test_p5_rejects_invalid_extremal_index(theta):
    with pytest.raises(ValueError, match="theta"):
        fit_length_law({3: (1, 100), 4: (1, 100), 5: (1, 100)}, np.arange(1, 501), theta=theta)


@pytest.mark.parametrize("sample", [[], [0, 0], [1, 2, 3]])
def test_k_selection_rejects_insufficient_positive_sample(sample):
    with pytest.raises(ValueError):
        select_k(np.array(sample))


@pytest.mark.parametrize("n,d", [(6, 12), (20, 5)])
def test_low_rank_transform_matches_dense_whitening_and_ridge(n, d):
    rng = np.random.default_rng(31)
    calibration = [rng.normal(size=(n + 1, d))]
    heldout = rng.normal(size=(9, d))
    fit = fit_transform(calibration, 0.1, 1.0)
    values = transformed_norms(heldout, fit)
    increments = np.diff(calibration[0], axis=0)
    cov = np.cov(increments, rowvar=False)
    cov = 0.9 * cov + 0.1 * np.trace(cov) / d * np.eye(d)
    centered = np.diff(heldout, axis=0) - increments.mean(axis=0)
    expected = np.sqrt(np.einsum("ij,ji->i", centered, np.linalg.solve(cov, centered.T)))
    assert np.allclose(values["whitened"], expected, atol=1e-9)
    x, y = calibration[0][:-1], calibration[0][1:]
    a = np.linalg.solve(
        (x - x.mean(0)).T @ (x - x.mean(0)) + np.eye(d), (x - x.mean(0)).T @ (y - y.mean(0))
    )
    predicted = (heldout[:-1] - x.mean(0)) @ a + y.mean(0)
    assert np.allclose(values["innovation"], np.linalg.norm(heldout[1:] - predicted, axis=1))


def test_verified_calibration_does_not_depend_on_evaluation_values():
    rng = np.random.default_rng(32)
    calibration = [rng.normal(size=(10, 5))]
    first = fit_transform(calibration, 0.1, 1)
    transformed_norms(rng.normal(size=(10, 5)) * 1e6, first)
    second = fit_transform(calibration, 0.1, 1)
    assert all(np.array_equal(first[key], second[key]) for key in first)


def test_stage_read_refuses_torn_upstream_and_changed_config(tmp_path):
    path = tmp_path / "data.jsonl"
    with Journal(path, {}) as journal:
        journal.append({"trace_id": "x"}, "request")
    assert rows(path)[0]["trace_id"] == "x"
    with path.open("ab") as stream:
        stream.write(b"{")
    with pytest.raises(ValueError, match="incomplete upstream"):
        rows(path)
    (tmp_path / "inputs").mkdir()
    (tmp_path / "pilot").mkdir()
    (tmp_path / "inputs/problems.json").write_text("changed")
    write_once(tmp_path / "pilot/protocol.json", {"inputs": {"problems.json": "old-digest"}})
    with pytest.raises(ValueError, match="input changed"):
        configuration(tmp_path, "pilot")


def test_completed_stage_checks_ancestor_instead_of_trusting_manifest_presence(tmp_path):
    raw = tmp_path / "input"
    raw.write_text("original")
    man = finish(tmp_path / "stage", stage="test", context={}, inputs=[raw], outputs=[], metrics={})
    assert completed(man.parent)
    raw.write_text("corrupt")
    with pytest.raises(ValueError, match="digest mismatch"):
        completed(man.parent)


def test_pilot_small_sample_keeps_all_estimators_and_no_precise_claim():
    part = pd.DataFrame(
        {"z": [1, 2, 3], "trace_id": ["a", "a", "b"], "prompt_id": ["same", "same", "same"]}
    )
    result = tail(part, {})
    assert result["n_tasks"] == 1 and result["ci"] is None
    assert result["decision"] == "inconclusive"
    assert all(result[k] is None for k in ("hill", "moment", "gpd"))


@pytest.mark.ml
def test_hook_cannot_silently_drop_other_batch_sequences():
    torch = pytest.importorskip("torch")
    from onebigjump.models.hooks import ResidualRecorder

    recorder = ResidualRecorder(layers=[0], positions=[0])
    with pytest.raises(ValueError, match="one sequence"):
        recorder._make_hook(0)(None, None, torch.ones(2, 3, 4))


def test_missing_output_cannot_be_recorded_as_success(tmp_path):
    from onebigjump.manifests import RunManifest

    with pytest.raises(FileNotFoundError):
        RunManifest("missing", "test", tmp_path).add_output(tmp_path / "absent")


def test_log_moments_are_unchanged_by_large_units_on_a_narrow_tail():
    from onebigjump.stats.hill import log_moments

    x = 1 + np.linspace(0, 1e-5, 500)
    _, m1, m2 = log_moments(x * 1e150, k_max=100)
    descending = np.sort(x)[::-1]
    direct = np.log(descending[:100] / descending[100])
    assert np.isclose(m1[-1], direct.mean(), rtol=1e-8)
    assert np.isclose(m2[-1], np.mean(direct**2), rtol=1e-8)


def test_repl_start_rejects_failed_import_even_when_an_env_id_is_returned(tmp_path):
    import sys

    from onebigjump.lean.environment import LeanEnvironment

    launcher = tmp_path / "fake-lake"
    launcher.write_text(
        "#!" + sys.executable + "\n"
        "import sys, json\n"
        "sys.stdin.readline()\n"
        "print(json.dumps({'env': 0, 'messages': [{'severity': 'error', "
        "'data': 'failed import Mathlib'}]}) + '\\n', flush=True)\n"
        "sys.stdin.read()\n"
    )
    launcher.chmod(0o700)
    env = LeanEnvironment(
        workspace=tmp_path, project=tmp_path, repl_binary=launcher, lake=str(launcher)
    )
    repl = LeanREPL(env, startup_timeout_s=5)
    with pytest.raises(ReplError, match="failed import Mathlib"), repl:
        pytest.fail("a failed import must not become an empty theorem environment")
    assert repl._proc is None


def test_repl_start_rejects_silent_empty_environment(tmp_path):
    import sys

    from onebigjump.lean.environment import LeanEnvironment

    launcher = tmp_path / "fake-lake"
    launcher.write_text(
        "#!" + sys.executable + "\n"
        "import sys, json\n"
        "for line in sys.stdin:\n"
        "    if not line.strip(): continue\n"
        "    request = json.loads(line)\n"
        "    response = {'env': 0} if request['env'] is None else "
        "{'env': 1, 'messages': [{'severity': 'error', 'data': 'unknown tactic'}]}\n"
        "    print(json.dumps(response) + '\\n', flush=True)\n"
    )
    launcher.chmod(0o700)
    env = LeanEnvironment(
        workspace=tmp_path, project=tmp_path, repl_binary=launcher, lake=str(launcher)
    )
    repl = LeanREPL(env, startup_timeout_s=5)
    with pytest.raises(ReplError, match="environment failed its proof check"), repl:
        pytest.fail("an environment without standard tactics must not label proofs")
    assert repl._proc is None


def test_unterminated_comment_is_a_parse_exclusion_before_any_kernel_call():
    from onebigjump.lean.schemas import TraceOutcome
    from onebigjump.lean.verifier import verify_trace

    result = verify_trace(
        object(),
        "  trivial /- unclosed",
        header="theorem invalid_lexical_source : True := by",
        trace_id="invalid-lexical",
        problem_id="invalid-lexical",
    )
    assert result.outcome == TraceOutcome.PARSE_ERROR
    assert result.t_star is None
    assert not result.steps
    assert "unterminated" in result.error
