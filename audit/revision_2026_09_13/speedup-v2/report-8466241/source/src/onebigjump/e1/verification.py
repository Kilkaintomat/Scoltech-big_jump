"""Trusted-header proof verification with separately retained whole/replay evidence."""

from __future__ import annotations

import re
import time
from typing import Any

from ..lean.verifier import (
    LeanREPL,
    ReplError,
    _errors,
    _is_resource_error,
    _looks_like_parse_error,
    verify_trace,
)
from .spans import SourceExclusion, formal_body, mask_comments

ALLOWED_AXIOMS = {
    "propext",
    "Classical.choice",
    "Quot.sound",
    "Lean.ofReduceBool",
    "Lean.trustCompiler",
}


def theorem_name(problem: dict[str, Any]) -> str:
    """Use the trusted, case-sensitive declaration name; dataset IDs may be normalised."""
    statement = mask_comments(problem["statement"])
    match = re.match(r"^\s*(?:theorem|lemma)\s+((?:«[^»]*»|[^\s:()])+)", statement)
    if match is None:
        raise SourceExclusion(
            "context_statement_mismatch", "trusted statement has no named theorem"
        )
    return match.group(1)


def trusted_prefix(problem: dict[str, Any], max_heartbeats: int = 400000) -> str:
    return (
        f"import Mathlib\nimport Aesop\nset_option maxHeartbeats {max_heartbeats}\n"
        + problem["directives"]
    )


def verify_one(
    repl: LeanREPL, sample: dict[str, Any], problem: dict[str, Any], settings: dict[str, Any]
) -> dict[str, Any]:
    t0 = time.monotonic()
    result: dict[str, Any] = {
        "trace_id": sample["trace_id"],
        "problem_id": problem["problem_id"],
        "temperature": sample["temperature"],
        "attempt_index": sample["attempt_index"],
        "category": None,
        "whole_proof_ok": None,
        "replay_ok": None,
        "unexplained_disagreement": False,
        "steps": [],
        "resource_limited": False,
        "explained_resource_disagreement": False,
        "budget": {k: settings[k] for k in ("max_heartbeats", "step_timeout_s", "whole_timeout_s")},
        "t_star": None,
        "stop_reason": sample["finish_reason"],
    }
    try:
        parsed = formal_body(
            sample["completion"],
            problem["statement"],
            trusted_prefix(problem, settings["max_heartbeats"]),
        )
        result.update(parsed)
        # Only trusted directives and the original statement enter the environment.
        header = f"set_option maxHeartbeats {settings['max_heartbeats']}\n{problem['directives']}\n{problem['statement']}"
        pid = problem["problem_id"]
        declaration = theorem_name(problem)
        # The base environment must not contain this benchmark answer.
        absent = repl.command(f"#check {declaration}", timeout_s=settings["whole_timeout_s"])
        result["answer_import_check"] = absent
        if not _errors(absent):
            raise SourceExclusion(
                "context_statement_mismatch",
                "benchmark theorem already present in base environment",
            )
        whole_source = header + parsed["body"] + f"\n#print axioms {declaration}\n"
        whole = repl.command(whole_source, timeout_s=settings["whole_timeout_s"])
        result["whole_reply"] = whole
        errors = _errors(whole)
        whole_ok = not errors
        result["whole_proof_ok"] = whole_ok
        axiom_messages = [
            str(x.get("data", ""))
            for x in whole.get("messages", [])
            if "axioms" in str(x.get("data", ""))
        ]
        result["axiom_messages"] = axiom_messages
        axiom_names: list[str] = []
        for message in axiom_messages:
            match = re.search(r"depends on axioms:\s*\[(.*?)\]", message, re.DOTALL)
            if match:
                axiom_names.extend(x.strip() for x in match.group(1).split(",") if x.strip())
        result["axioms"] = axiom_names
        # Literal holes are identified outside strings/comments. The kernel dependency check also
        # catches hidden sorryAx/custom axioms, even when no literal hole appears in the proof.
        live = mask_comments(parsed["body"], mask_strings=True)
        live = re.sub(r"«[^»]*»", "", live)
        hole = bool(re.search(r"\b(?:sorry|admit|sorryAx)\b", live))
        # Lean inserts sorryAx while recovering from ordinary elaboration errors.
        # Axiom dependencies establish an explicit hole only for a successfully elaborated proof.
        axiom_hole = whole_ok and any(x not in ALLOWED_AXIOMS for x in axiom_names)
        if whole_ok and not axiom_messages:
            raise SourceExclusion("infrastructure_error", "kernel axiom audit missing")
        if errors and _looks_like_parse_error(errors):
            raise SourceExclusion("parse_error", "whole-proof parser error: " + errors[0][:800])
        trace = verify_trace(
            repl,
            parsed["replay_body"],
            trace_id=sample["trace_id"],
            problem_id=pid,
            header=header,
            model_id=sample["model_id"],
            temperature=sample["temperature"],
            sample_index=sample["attempt_index"],
            per_step_timeout_s=settings["step_timeout_s"],
            whole_proof_timeout_s=settings["whole_timeout_s"],
            check_whole_proof=False,
        )
        result["replay"] = trace.model_dump(mode="json")
        result["replay_ok"] = trace.verified
        result["t_star"] = trace.t_star
        result["steps"] = [s.model_dump(mode="json") for s in trace.steps]
        if trace.outcome == "timeout":
            result["resource_limited"] = True
            result["explained_resource_disagreement"] = whole_ok
            raise SourceExclusion("timeout_resource", trace.error or "statement replay timed out")
        if trace.outcome == "repl_failure":
            raise SourceExclusion("infrastructure_error", trace.error or "REPL process failed")
        if len(trace.steps) != len(parsed["step_spans"]):
            raise SourceExclusion(
                "unsupported_segmentation", "replay did not account for every source segment"
            )
        if not trace.check_absorbing():
            raise AssertionError("nonabsorbing replay")
        if hole or axiom_hole:
            result["category"] = "sorry_invalid_proof"
        elif sample["finish_reason"] == "length":
            result["category"] = "generation_truncation"
        elif (
            _is_resource_error(errors)
            or trace.outcome == "timeout"
            or any(s.status == "timeout" for s in trace.steps)
        ):
            result["category"] = "timeout_resource"
        elif trace.verified:
            result["category"] = "verified"
        elif trace.t_star is not None:
            status = trace.steps[trace.t_star].status
            result["category"] = (
                "terminal_unsolved_goals"
                if status == "unsolved_goals"
                else "localized_tactic_failure"
            )
        else:
            result["category"] = "infrastructure_error"
        resource_limited = (
            _is_resource_error(errors)
            or trace.outcome == "timeout"
            or any(s.status == "timeout" for s in trace.steps)
        )
        result["resource_limited"] = resource_limited
        result["budget"] = {
            "max_heartbeats": settings["max_heartbeats"],
            "step_timeout_s": settings["step_timeout_s"],
            "whole_timeout_s": settings["whole_timeout_s"],
        }
        result["explained_resource_disagreement"] = whole_ok != trace.verified and resource_limited
        result["unexplained_disagreement"] = whole_ok != trace.verified and not (
            hole or axiom_hole or resource_limited
        )
        if result["unexplained_disagreement"]:
            result["category"] = "unsupported_segmentation"
    except SourceExclusion as exc:
        result["category"] = exc.category
        result["error"] = str(exc)
    except TimeoutError as exc:
        result["resource_limited"] = True
        result["category"] = "timeout_resource"
        result["error"] = str(exc)
    except ReplError as exc:
        result["category"] = "infrastructure_error"
        result["error"] = str(exc)
        repl.restart()
    if sample["finish_reason"] == "length":
        result["pre_truncation_category"] = result["category"]
        result["category"] = "generation_truncation"
    result["elapsed_s"] = time.monotonic() - t0
    return result
