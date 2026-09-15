from release_policy import MODELS, release_reason


def ready():
    return {"tasks": {m + "/main-extract-" + str(s): {"state": "COMPLETED"}
                      for m in MODELS for s in range(8)}}


def test_cannot_take_a_temporary_gap_while_main_is_unfinished():
    q = ready()
    q["tasks"]["kimina/main-extract-7"]["state"] = "WAITING"
    assert not release_reason(q, 0, True)[0]


def test_missing_or_failed_jobs_do_not_release():
    q = ready()
    del q["tasks"]["deepseek/main-extract-0"]
    assert not release_reason(q, 0, True)[0]
    q = ready()
    q["tasks"]["deepseek/main-extract-0"]["state"] = "FAILED"
    assert not release_reason(q, 0, True)[0]


def test_needs_both_manifests_and_idle_slots():
    assert not release_reason(ready(), 0, False)[0]
    assert not release_reason(ready(), 1, True)[0]
    assert release_reason(ready(), 0, True)[0]
