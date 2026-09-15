"""Diagnostic thresholds are observable, scale equivariant, and versioned prompts preserve checking."""

import numpy as np
import pytest

from onebigjump.readiness.deduction import check, make_problem, prompt
from onebigjump.readiness.p3_validation import thresholds


def test_support_candidate_uses_observed_minimum():
    cal = np.array([[1.0, 2.0], [3.0, 4.0]])
    fail = np.array([[6.0, 8.0], [7.0, 10.0]])
    got = thresholds(cal, fail, 0.25)
    assert got == {"original": 3.25, "observed_support": 6.0}
    assert thresholds(cal, fail * 0.1, 0.25)["observed_support"] == 3.25
    scaled = thresholds(cal * 7, fail * 7, 0.25)
    assert scaled == {k: v * 7 for k, v in got.items()}


def test_new_prompt_cannot_relax_symbolic_checker():
    p = make_problem(3, "development", 0, seed=20260913)
    assert prompt(p) == prompt(p, "original-v1")
    improved = prompt(p, "worked-example-v2")
    assert "SEPARATE EXAMPLE" in improved and "exactly 3 NEW inference lines" in improved
    actual = improved.split("FINAL PUZZLE")[-1]
    assert p["initial"] in actual and p["goal"] in actual
    gold = "\n".join("Mira is " + fact + "." for fact in p["gold_chain"])
    assert check(gold + "\nAnswer: true", p)["verified"]
    repeated = "\n".join("Mira is " + fact + "." for fact in [p["initial"], *p["gold_chain"][:-1]])
    failure = check(repeated, p)
    assert failure["format_eligible"] and failure["t_star"] == 0 and not failure["verified"]
    with pytest.raises(ValueError):
        prompt(p, "unregistered-version")
