"""Decide when saved labels require a fresh kernel run after the bounded v8 repair."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .spans import SourceExclusion, formal_body
from .verification import theorem_name, trusted_prefix


def parser_result(
    parser: Callable[..., dict[str, Any]],
    sample: dict[str, Any],
    problem: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    try:
        return {
            "parsed": parser(
                sample["completion"],
                problem["statement"],
                trusted_prefix(problem, settings["max_heartbeats"]),
            )
        }
    except SourceExclusion as exc:
        return {"exclusion": exc.category, "reason": str(exc)}


def rerun_reasons(
    sample: dict[str, Any],
    problem: dict[str, Any],
    settings: dict[str, Any],
    previous: dict[str, Any],
    old_parser: Callable[..., dict[str, Any]],
) -> list[str]:
    """Outcome-independent parser/name changes select all affected attempts, including failures."""
    reasons = []
    if theorem_name(problem) != problem["problem_id"]:
        reasons.append("trusted_declaration_name_differs_from_dataset_id")
    if parser_result(old_parser, sample, problem, settings) != parser_result(
        formal_body, sample, problem, settings
    ):
        reasons.append("parser_output_changed")
    if previous["unexplained_disagreement"]:
        reasons.append("recorded_whole_replay_disagreement")
    if previous["category"] == "infrastructure_error":
        reasons.append("recorded_infrastructure_error")
    return reasons
