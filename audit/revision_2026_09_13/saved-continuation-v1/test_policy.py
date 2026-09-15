"""Fail-closed transition tests; no scheduler writes."""
import copy
import pytest
from policy import activate, release, MODELS


def fixture():
    tasks = {}
    for model in MODELS:
        tasks[model + "/main-verify-0"] = dict(
            stage="verify", state="RUNNING", job_id="100", dependencies=[], script="old")
        tasks[model + "/main-verify-1"] = dict(
            stage="verify", state="WAITING", job_id=None, dependencies=[], script="old")
        tasks[model + "/gather-verify"] = dict(state="BLOCKED", job_id=None,
            dependencies=[model + "/main-verify-0", model + "/main-verify-1"])
        for i in range(8):
            tasks[model + "/main-extract-" + str(i)] = dict(
                state="BLOCKED", job_id=None, dependencies=[model + "/gather-verify"])
        tasks[model + "/gather-extract"] = dict(state="BLOCKED", job_id=None,
            dependencies=[model + "/main-extract-" + str(i) for i in range(8)])
        tasks[model + "/measure"] = dict(state="BLOCKED", job_id=None,
            dependencies=[model + "/gather-extract"])
        tasks[model + "/analyze"] = dict(state="BLOCKED", job_id=None,
            dependencies=[model + "/measure"])
    return dict(tasks=tasks, source="/x/lean-local-toolchain-v7",
                partition_submit_caps={"ais-htc": 4, "ais-gpu": 6})


def receipt():
    return dict(passed=True, job_id="900", source="/x/lean-io-v9")


def accepted():
    return {"deepseek": dict(stage="gather-verification-repaired", manifest_sha256="abc",
        metrics=dict(attempts=6672, unexplained_disagreements=0, all_planned_attempts_accounted=True))}


def test_activation_preserves_running_tasks_source_and_input():
    q = fixture()
    before = copy.deepcopy(q)
    new = activate(q, receipt(), "v9-wrapper")
    assert q == before
    assert new["source"] == q["source"]
    for model in MODELS:
        key = model + "/main-verify-0"
        assert new["tasks"][key] == q["tasks"][key]
        assert new["tasks"][model + "/main-verify-1"]["script"] == "v9-wrapper"
        assert new["tasks"][model + "/gather-verify"]["state"] == "BLOCKED"


@pytest.mark.parametrize("broken", [
    {}, dict(passed=False, job_id="900"), dict(passed=True, job_id=""),
])
def test_failed_preflight_rejected(broken):
    with pytest.raises(ValueError):
        activate(fixture(), broken, "v9")


def test_unsubmitted_problem_is_not_silently_retried():
    q = fixture()
    q["tasks"]["deepseek/main-verify-1"]["submit_error"] = "bad"
    with pytest.raises(ValueError):
        activate(q, receipt(), "v9")


@pytest.mark.parametrize("field,value", [
    ("attempts", 6671), ("unexplained_disagreements", 1),
    ("all_planned_attempts_accounted", False),
])
def test_incomplete_merge_cannot_release_gpu(field, value):
    q = activate(fixture(), receipt(), "v9")
    a = accepted()
    a["deepseek"]["metrics"][field] = value
    with pytest.raises(ValueError):
        release(q, a, "901", True)


def test_failed_slurm_cannot_release_gpu():
    with pytest.raises(ValueError):
        release(activate(fixture(), receipt(), "v9"), accepted(), "901", False)


def test_only_accepted_model_descendants_release_with_history():
    q = activate(fixture(), receipt(), "v9")
    q["tasks"]["deepseek/main-verify-0"]["state"] = "FAILED"
    q["tasks"]["deepseek/main-extract-1"]["submit_error"] = "previous rejection"
    new = release(q, accepted(), "901", True)
    assert new["tasks"]["deepseek/main-verify-0"]["state"] == "FAILED"
    assert new["tasks"]["deepseek/gather-verify"]["superseded_raw_dependencies"]
    assert new["tasks"]["deepseek/main-extract-0"]["state"] == "WAITING"
    assert new["tasks"]["deepseek/main-extract-1"]["state"] == "BLOCKED"
    assert new["tasks"]["kimina/main-extract-0"]["state"] == "BLOCKED"
    assert new["partition_submit_caps"]["ais-htc"] == 3
    assert q["tasks"]["deepseek/gather-verify"]["job_id"] is None


def test_release_is_idempotent():
    q = activate(fixture(), receipt(), "v9")
    new = release(q, accepted(), "901", True)
    assert release(new, accepted(), "902", True) == new


def test_full_acceptance_restores_cpu_capacity():
    q = activate(fixture(), receipt(), "v9")
    a = {model: copy.deepcopy(accepted()["deepseek"]) for model in MODELS}
    new = release(q, a, "901", True)
    assert new["partition_submit_caps"] == {"ais-htc": 4, "ais-gpu": 2}
