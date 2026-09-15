"""Record types for Lean proof traces and their per-step labels.

The Lean 4 kernel is what makes this project's labels *exact* rather than learned, so the label
vocabulary has to distinguish the cases Appendix B.2 distinguishes, and no fewer:

* `ok`            -- the tactic elaborated against the state left by tactics 1..t-1;
* `error`         -- it did not; this is a genuine `t*`;
* `timeout`       -- the elaborator did not finish; "treated as failures at the offending step
                     and reported separately", so it gets its own label and its own count;
* `sorry`         -- the goal was closed by `sorry`, which is not a proof;
* `unreached`     -- a step after `t*`; labels are absorbing, so its value is 0 but it was never
                     actually run and must not be counted as an observed failure;
* `unsolved_goals`-- the proof ended with goals remaining: "recorded as a failure of the last step".

A trace whose *first* error is a parse error of the whole proof has no step structure at all and
is discarded rather than labelled (`TraceOutcome.parse_error`).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StepStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    SORRY = "sorry"
    UNREACHED = "unreached"
    UNSOLVED_GOALS = "unsolved_goals"


class TraceOutcome(StrEnum):
    VERIFIED = "verified"
    REFUTED = "refuted"
    PARSE_ERROR = "parse_error"  # discarded: no step structure
    TIMEOUT = "timeout"
    REPL_FAILURE = "repl_failure"  # infrastructure, not a property of the proof
    STATEMENT_MISMATCH = "statement_mismatch"  # the model changed the requested theorem


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class StepLabel(Record):
    """One tactic and the kernel's verdict on it."""

    index: int = Field(ge=0, description="position t in the trace, 0-based")
    tactic: str
    status: StepStatus
    valid: bool = Field(description="v_t; absorbing, so 0 at and after t*")
    line_start: int = Field(ge=0, description="first source line of the segment")
    line_end: int = Field(ge=0)
    n_lines: int = Field(ge=1)
    message: str = ""
    goals_before: int | None = None
    goals_after: int | None = None
    elapsed_s: float = 0.0
    has_combinator: bool = False
    is_structured: bool = False

    @property
    def is_first_failure(self) -> bool:
        return self.status in {StepStatus.ERROR, StepStatus.TIMEOUT, StepStatus.SORRY}


class ProofTrace(Record):
    """A sampled whole proof, its steps, and the labels the kernel assigned to them."""

    trace_id: str
    problem_id: str
    model_id: str = ""
    temperature: float | None = None
    sample_index: int = 0
    theorem_statement: str = ""
    header: str = ""
    proof_text: str = ""
    steps: list[StepLabel] = Field(default_factory=list)
    outcome: TraceOutcome = TraceOutcome.REPL_FAILURE
    t_star: int | None = Field(default=None, description="first rejected step; None if verified")
    whole_proof_ok: bool | None = None
    elapsed_s: float = 0.0
    error: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def n_steps(self) -> int:
        return len(self.steps)

    @property
    def verified(self) -> bool:
        return self.outcome == TraceOutcome.VERIFIED

    @property
    def labelled(self) -> bool:
        """Usable for P1-P3: it has step structure and a definite verdict."""
        return self.outcome in {TraceOutcome.VERIFIED, TraceOutcome.REFUTED}

    def labels(self) -> list[int]:
        """`v_t` for every step, already absorbing."""
        return [int(s.valid) for s in self.steps]

    def check_absorbing(self) -> bool:
        """Labels must never come back to 1 after a 0 (Section 2)."""
        seen_zero = False
        for s in self.steps:
            if not s.valid:
                seen_zero = True
            elif seen_zero:
                return False
        return True


class VerificationSummary(Record):
    """Counts Appendix B.2 asks to be reported: '[Report the number of traces in each category.]'"""

    n_traces: int = 0
    verified: int = 0
    refuted: int = 0
    parse_error_discarded: int = 0
    timeout: int = 0
    step_timeout: int = 0
    repl_failure: int = 0
    statement_mismatch: int = 0
    n_steps_total: int = 0
    mean_trace_length: float = 0.0
    mean_t_star: float | None = None
    elapsed_s: float = 0.0

    @classmethod
    def from_traces(cls, traces: list[ProofTrace]) -> VerificationSummary:
        by = dict.fromkeys(TraceOutcome, 0)
        for t in traces:
            by[t.outcome] += 1
        labelled = [t for t in traces if t.labelled]
        stars = [t.t_star for t in traces if t.t_star is not None]
        return cls(
            n_traces=len(traces),
            verified=by[TraceOutcome.VERIFIED],
            refuted=by[TraceOutcome.REFUTED],
            parse_error_discarded=by[TraceOutcome.PARSE_ERROR],
            timeout=by[TraceOutcome.TIMEOUT],
            step_timeout=sum(any(s.status == StepStatus.TIMEOUT for s in t.steps) for t in traces),
            repl_failure=by[TraceOutcome.REPL_FAILURE],
            statement_mismatch=by[TraceOutcome.STATEMENT_MISMATCH],
            n_steps_total=sum(t.n_steps for t in traces),
            mean_trace_length=(
                sum(t.n_steps for t in labelled) / len(labelled) if labelled else 0.0
            ),
            mean_t_star=(sum(stars) / len(stars) if stars else None),
            elapsed_s=sum(t.elapsed_s for t in traces),
        )
