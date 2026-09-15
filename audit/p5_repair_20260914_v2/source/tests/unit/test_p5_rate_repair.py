import math
import re

import numpy as np
import pytest
from onebigjump.experiments.p5_rate import diagnose_records, fit_length_rate, score_heldout
from onebigjump.readiness.deduction_format import grammar_for_length, regex_for_length

from onebigjump.readiness.deduction import check, make_problem, prompt


def test_rate_recovers_exact_exponential_without_any_tail_observations():
    counts = {length: (4096 // 2**length, 4096) for length in range(3, 13)}
    result = fit_length_rate(counts)
    assert result["rate_per_step"] == pytest.approx(math.log(2), abs=1e-10)
    assert result["lr_statistic"] == pytest.approx(0, abs=1e-8)
    assert result["p_value"] is None and result["theta"] is None and result["tau"] is None


@pytest.mark.parametrize(
    "success,status,rate", [(0, "all_failure_boundary", None), (10, "all_success_boundary", 0.0)]
)
def test_boundary_outcomes_are_explicit(success, status, rate):
    result = fit_length_rate(dict.fromkeys(range(3, 13), (success, 10)))
    assert result["status"] == status
    assert result["rate_per_step"] == rate
    assert result["loglik"] == 0 and result["lr_statistic"] == 0


def test_heldout_zero_probability_event_is_reported_without_epsilon_clipping():
    fit = fit_length_rate(dict.fromkeys(range(3, 13), (0, 10)))
    result = score_heldout(fit, dict.fromkeys(range(3, 13), (1, 10)))
    assert result["loglik"] is None
    assert "negative_infinity" in result["loglik_status"]
    assert result["brier"] == pytest.approx(0.1)


@pytest.mark.parametrize(
    "counts",
    [
        {3: (1, 2)},
        {3: (1, 2), 4: (1, 0), 5: (1, 2)},
        {3: (3, 2), 4: (1, 2), 5: (1, 2)},
        {3: (1.5, 2), 4: (1, 2), 5: (1, 2)},
        {0: (1, 2), 4: (1, 2), 5: (1, 2)},
    ],
)
def test_invalid_counts_fail_closed(counts):
    with pytest.raises(ValueError):
        fit_length_rate(counts)


@pytest.mark.parametrize("length", range(3, 13))
def test_syntax_accepts_wrong_inferences_without_helping_the_solver(length):
    p = make_problem(length, "test", 0, seed=2026091405)
    gold = "\n".join(f"Mira is {fact}." for fact in p["gold_chain"]) + "\nAnswer: true"
    wrong = "\n".join([f"Mira is {p['initial']}."] * length) + "\nAnswer: true"
    invented = "\n".join(["Mira is p9999."] * length) + "\nAnswer: true"
    assert re.fullmatch(regex_for_length(length), gold)
    assert re.fullmatch(regex_for_length(length), wrong)
    assert re.fullmatch(regex_for_length(length), invented)
    assert check(gold, p)["verified"]
    rejected = check(wrong, p)
    assert rejected["format_eligible"] and rejected["t_star"] == 0
    assert all(s["status"] == "unreached" for s in rejected["steps"][1:])
    assert not re.fullmatch(regex_for_length(length), gold + "\nMira is p1234.")
    assert not re.fullmatch(regex_for_length(length), "\n".join(gold.splitlines()[1:]))
    assert p["initial"] not in grammar_for_length(length)
    assert p["goal"] not in grammar_for_length(length)
    without_gold = {k: v for k, v in p.items() if k != "gold_chain"}
    assert prompt(p, "worked-example-v2") == prompt(without_gold, "worked-example-v2")


def test_task_roles_and_attempt_identity_cannot_leak():
    record = {
        "trace_id": "a",
        "problem_id": "p",
        "role": "calibration",
        "length": 3,
        "temperature": 0.6,
        "verified": False,
        "format_eligible": False,
        "category": "format_error",
    }
    with pytest.raises(ValueError, match="duplicate"):
        diagnose_records([record, record])
    with pytest.raises(ValueError, match="overlap"):
        diagnose_records([record, {**record, "trace_id": "b", "role": "evaluation"}])


def test_rate_is_monotone_in_successes():
    rates = [
        fit_length_rate(dict.fromkeys(range(3, 13), (s, 100)))["rate_per_step"]
        for s in [1, 10, 50, 90]
    ]
    assert np.all(np.diff(rates) < 0)
