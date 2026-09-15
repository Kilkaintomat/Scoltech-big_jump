"""Live Lean checks through the exact E1 container and REPL launcher."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..lean.environment import discover
from ..lean.verifier import LeanREPL, _errors
from .artifacts import digest, finish, read_json, write_once
from .stages import lean_fingerprint
from .verification import trusted_prefix, verify_one


def fixtures() -> list[tuple[str, str, str, str]]:
    return [
        ("correct", "True", "  trivial", "verified"),
        ("reasoning_fences", "True", "  trivial", "verified"),
        ("unicode_eos", "True", "  trivial", "verified"),
        (
            "failure",
            "True",
            "  have h : True := by trivial\n  exact Nat.zero_ne_one\n  trivial",
            "localized_tactic_failure",
        ),
        ("sorry", "False", "  sorry", "sorry_invalid_proof"),
        ("sorryax", "False", "  exact sorryAx False false", "sorry_invalid_proof"),
        ("unsolved", "True", "  skip", "terminal_unsolved_goals"),
        (
            "nested",
            "True ∧ True",
            "  constructor\n  · have h : True := by\n      trivial\n    exact h\n  · trivial",
            "verified",
        ),
        ("calc", "(0 : Nat) = 0", "  calc\n    (0 : Nat) = 0 := by rfl", "verified"),
        ("semicolon", "True ∧ True", "  constructor; trivial", "terminal_unsolved_goals"),
        ("semicolon_complete", "True ∧ True", "  constructor; trivial; trivial", "verified"),
        ("all_goals", "True ∧ True", "  constructor\n  all_goals trivial", "verified"),
        ("leading_combinator", "True ∧ True", "  constructor\n  <;> trivial", "verified"),
        ("trailing_combinator", "True ∧ True", "  constructor <;>\n  trivial", "verified"),
        ("split_combinator", "True ∧ True", "  constructor\n  <;>\n  trivial", "verified"),
        ("split_semicolon", "True ∧ True", "  constructor;\n  trivial;\n  trivial", "verified"),
        (
            "split_combinator_failure",
            "True ∧ True",
            "  constructor\n  <;> exact Nat.zero_ne_one\n  trivial",
            "localized_tactic_failure",
        ),
        ("combinator", "True ∧ True", "  constructor <;> trivial", "verified"),
        ("string", "True", '  have s : String := "-- /- sorry -/"\n  trivial', "verified"),
        (
            "comments",
            "True",
            "  /- outer /- nested -/ comment -/\n  trivial -- sorry in a comment",
            "verified",
        ),
        ("multiline", "True", "  have h :\n      True := by\n    trivial\n  exact h", "verified"),
        ("parser", "True", "  exact (", "parse_error"),
    ]


def run(root: Path, source_manifest: Path) -> None:
    config = read_json(root / "pilot/protocol.json")
    settings = config["lean"]
    out = root / "checks" / ("lean-smoke-" + source_manifest.parent.name)
    out.mkdir(parents=True, exist_ok=False)
    write_once(out / "lean-environment.json", lean_fingerprint(settings))
    results: list[dict[str, Any]] = []
    t0 = time.monotonic()
    with LeanREPL(
        discover(settings["workspace"]),
        imports="import Mathlib\nimport Aesop",
        startup_timeout_s=settings["startup_timeout_s"],
        drain_timeout_s=0.01,
    ) as repl:
        for name, goal, body, expected in fixtures():
            pid = "e1_fixture_" + name
            problem = {
                "problem_id": pid,
                "statement": f"theorem {pid} : {goal} := by",
                "directives": "",
            }
            completion = (
                "```lean4\n"
                + trusted_prefix(problem)
                + "\n"
                + problem["statement"]
                + "\n"
                + body
                + "\n```"
            )
            if name == "unicode_eos":
                completion = (
                    completion.replace("  trivial", "  sorry")
                    + "\n"
                    + completion
                    + "<｜end▁of▁sentence｜>"
                )
            if name == "reasoning_fences":
                completion = "<think>\n```tactics\ntrivial\n```\n</think>\n" + completion
            sample = {
                "trace_id": pid,
                "model_id": "fixture",
                "temperature": 0.6,
                "attempt_index": 0,
                "finish_reason": "stop",
                "completion": completion,
            }
            result = verify_one(repl, sample, problem, settings)
            result.update(
                {
                    "fixture": True,
                    "expected": expected,
                    "passed": result["category"] == expected
                    and not result["unexplained_disagreement"],
                }
            )
            results.append(result)
            print(name, result["category"], "PASS" if result["passed"] else "FAIL", flush=True)
        problem = {
            "problem_id": "e1_fixture_false",
            "statement": "theorem e1_fixture_false : False := by",
            "directives": "",
        }
        sample = {
            "trace_id": "substitution",
            "model_id": "fixture",
            "temperature": 0.6,
            "attempt_index": 0,
            "finish_reason": "stop",
            "completion": "```lean4\ntheorem e1_fixture_false : True := by\n  trivial\n```",
        }
        result = verify_one(repl, sample, problem, settings)
        result.update(
            {
                "fixture": True,
                "expected": "context_statement_mismatch",
                "passed": result["category"] == "context_statement_mismatch",
            }
        )
        results.append(result)
        restart_before = repl.restarts
        timed_out = False
        try:
            repl.command("#eval IO.sleep 2000", timeout_s=0.001)
        except TimeoutError:
            timed_out = True
        recovered = repl.command("example : True := by trivial", timeout_s=180)
        results.append(
            {
                "fixture": True,
                "trace_id": "timeout_restart_isolation",
                "passed": timed_out and repl.restarts > restart_before and not _errors(recovered),
                "reply": recovered,
                "restarts": repl.restarts,
                "recoveries": repl.recoveries,
            }
        )
        # Check source statements without importing or retaining any benchmark theorem.
        source_rows = []
        for problem in read_json(root / "inputs/problems.json"):
            if not problem["eligible"]:
                continue
            pid = problem["problem_id"]
            absent = repl.command(f"#check {pid}", timeout_s=180)
            reply = repl.command(
                f"set_option maxHeartbeats 400000\n{problem['directives']}\n{problem['statement']}\n  sorry",
                timeout_s=180,
            )
            source_rows.append(
                {
                    "problem_id": pid,
                    "already_imported": not bool(_errors(absent)),
                    "elaborates": not bool(_errors(reply)),
                    "reply": reply,
                }
            )
        write_once(out / "statement-checks.json", source_rows)
    write_once(out / "fixtures.json", results)
    passed = all(r["passed"] for r in results)
    write_once(
        out / "summary.json",
        {
            "passed": passed,
            "fixtures": len(results),
            "failed": [r["trace_id"] for r in results if not r["passed"]],
            "elapsed_s": time.monotonic() - t0,
            "source_statements": len(source_rows),
            "source_elaboration_failures": [
                r["problem_id"] for r in source_rows if not r["elaborates"]
            ],
            "imported_answers": [r["problem_id"] for r in source_rows if r["already_imported"]],
        },
    )
    finish(
        out,
        stage="live-lean-smoke",
        context={
            "source_sha256": digest(source_manifest),
            "config_sha256": digest(root / "pilot/protocol.json"),
        },
        inputs=[source_manifest, root / "pilot/protocol.json", root / "inputs/problems.json"],
        outputs=list(out.glob("*.json")),
        metrics={"passed": passed},
    )
    if not passed:
        raise RuntimeError("live Lean smoke tests failed; inspect recorded replies")
