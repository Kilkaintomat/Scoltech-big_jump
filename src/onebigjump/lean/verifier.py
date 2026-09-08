"""Drive the Lean 4 REPL to obtain exact per-step labels (Appendix B.2).

The protocol is line-delimited JSON over a pipe, one blank line between messages:

    {"cmd": "import Mathlib", "env": null}          -> {"env": 0}
    {"cmd": "theorem t : P := by sorry", "env": 0}  -> {"sorries": [{"proofState": 0, ...}], ...}
    {"tactic": "rw [h]", "proofState": 0}           -> {"proofState": 1, "goals": [...], ...}

Two properties of the REPL's replies decide how labels are read:

* a *failing* tactic still returns a `proofState`, with the error only in `messages`. So a step is
  rejected when the reply carries a message of severity `error`, never because its goal list is
  empty -- an empty goal list also follows a failure.
* `proofStatus` reports `Completed` only when the goals are actually closed, which is what turns
  "the proof ended with goals remaining" into a failure of the last step, as Appendix B.2 requires.

Importing Mathlib measured 129s on this machine, so the process is persistent and the import is
paid once for a whole batch. `pickleTo` does not help: it stores module references rather than
their contents, so restoring a snapshot measured 126.7s -- the cost is loading Mathlib's oleans,
not elaborating the import. A timed-out call is therefore recovered by waiting for its late
reply rather than by restarting.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from pathlib import Path
from types import TracebackType
from typing import Any

from ..logging import get_logger
from .environment import LeanEnvironment, discover
from .schemas import ProofTrace, StepLabel, StepStatus, TraceOutcome
from .segmentation import Segment, segment_proof, split_header_and_proof

__all__ = ["LeanREPL", "ReplError", "verify_trace"]

log = get_logger(__name__)

_PARSE_HINTS = (
    "unexpected token",
    "unexpected identifier",
    "expected term",
    "expected command",
    "unexpected end of input",
    "expected ':=' or '|'",
)


class ReplError(RuntimeError):
    """The REPL process failed, hung, or replied with something unparseable."""


class LeanREPL:
    """A persistent Lean REPL with Mathlib imported once.

    Use as a context manager. Every call has a deadline. A call that exceeds it has not failed
    in Lean -- Lean is still elaborating -- so the reply is still coming and would be read as the
    answer to the *next* command, shifting every later label by one. The stream is therefore
    resynchronised by waiting for that late reply, and the process is restarted only if it never
    arrives. Either way the timeout is reported as a property of that step, not of the batch.
    """

    def __init__(
        self,
        env: LeanEnvironment | None = None,
        *,
        imports: str = "import Mathlib",
        startup_timeout_s: float = 900.0,
        default_timeout_s: float = 60.0,
        drain_timeout_s: float = 300.0,
    ) -> None:
        self.env = (env or discover()).require()
        self.imports = imports
        self.startup_timeout_s = startup_timeout_s
        self.default_timeout_s = default_timeout_s
        self._proc: subprocess.Popen[str] | None = None
        self._out: queue.Queue[str | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._base_env: int | None = None
        self._desynced = False
        self.drain_timeout_s = drain_timeout_s
        self.restarts = 0
        self.recoveries = 0

    # -- process lifecycle ---------------------------------------------------------------

    def __enter__(self) -> LeanREPL:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def start(self) -> None:
        assert self.env.project is not None and self.env.repl_binary is not None
        repl = Path(self.env.repl_binary).resolve()
        cmd = [self.env.lake or "lake", "env", str(repl)]
        log.info("starting Lean REPL: %s (cwd=%s)", " ".join(cmd), self.env.project)
        # Fixed argv built from a toolchain discovered on disk; nothing here is user input.
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(self.env.project),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=self.env.env_vars(),
        )
        self._out = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

        self._desynced = False
        t0 = time.time()
        reply = self._exchange({"cmd": self.imports, "env": None}, timeout_s=self.startup_timeout_s)
        self._base_env = reply.get("env")
        if self._base_env is None:
            raise ReplError(f"the REPL did not return an environment for {self.imports!r}: {reply}")
        log.info("imported %r in %.1fs (env=%d)", self.imports, time.time() - t0, self._base_env)

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        finally:
            self._proc = None
            self._base_env = None

    def restart(self) -> None:
        self.restarts += 1
        log.warning("restarting the Lean REPL (restart #%d)", self.restarts)
        self.close()
        self.start()

    # -- transport -----------------------------------------------------------------------

    def _pump(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        buf: list[str] = []
        for line in proc.stdout:
            if line.strip() == "":
                if buf:
                    self._out.put("".join(buf))
                    buf = []
            else:
                buf.append(line)
        if buf:
            self._out.put("".join(buf))
        self._out.put(None)  # process ended

    def _recover(self) -> None:
        """Resynchronise after a timed-out call, restarting only if that fails.

        A timeout is ours, not the REPL's: Lean is still elaborating and will eventually emit the
        reply, which would otherwise be read as the answer to the *next* command and shift every
        later label by one. Waiting for that late reply restores the stream. Restarting instead
        costs a full Mathlib import, and there is no cheaper way back: `pickleTo` stores only
        module references, so restoring a snapshot measured 126.7s against 129.0s to import it.
        """
        try:
            raw = self._out.get(timeout=self.drain_timeout_s)
        except queue.Empty:
            log.warning("the late reply never arrived within %.0fs", self.drain_timeout_s)
            self.restart()
            return
        if raw is None:
            self.restart()
            return
        self._desynced = False
        self.recoveries += 1
        log.info("resynchronised with the REPL without restarting (recovery #%d)", self.recoveries)

    def _exchange(self, payload: dict[str, Any], timeout_s: float | None = None) -> dict[str, Any]:
        if self._desynced:
            self._recover()
        if self._proc is None or self._proc.stdin is None:
            raise ReplError("the REPL is not running")
        deadline = timeout_s if timeout_s is not None else self.default_timeout_s
        try:
            self._proc.stdin.write(json.dumps(payload) + "\n\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            raise ReplError(f"could not write to the REPL: {exc}") from exc

        try:
            raw = self._out.get(timeout=deadline)
        except queue.Empty as exc:
            self._desynced = True
            raise TimeoutError(f"the REPL did not reply within {deadline}s") from exc
        if raw is None:
            raise ReplError("the REPL exited")
        try:
            return dict(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ReplError(f"unparseable REPL reply: {raw[:400]!r}") from exc

    # -- operations ----------------------------------------------------------------------

    @property
    def base_env(self) -> int:
        if self._base_env is None:
            raise ReplError("the REPL has no base environment; call start() first")
        return self._base_env

    def command(self, source: str, timeout_s: float | None = None) -> dict[str, Any]:
        """Elaborate a whole command (a full theorem, proof included) in the base environment."""
        return self._exchange({"cmd": source, "env": self.base_env}, timeout_s=timeout_s)

    def tactic(self, tac: str, proof_state: int, timeout_s: float | None = None) -> dict[str, Any]:
        """Run one tactic against a proof state."""
        return self._exchange({"tactic": tac, "proofState": proof_state}, timeout_s=timeout_s)


def _errors(reply: dict[str, Any]) -> list[str]:
    """Every error in a REPL reply, from *both* places the REPL puts them.

    Elaboration diagnostics arrive as `messages` entries with severity `error`. But a hard
    failure -- a type mismatch on `exact`, an unknown proof state -- arrives instead as a
    top-level `message` string, with no `messages` array and, critically, no `proofState`:

        {"message": "Lean error:\nType mismatch\n  Nat.mul_comm a b\nhas type ..."}

    Reading only `messages` marks such a step valid and then replays the next tactic against the
    stale state, so the rest of the trace elaborates against a proof state it never reached. That
    silently manufactures verified traces out of refuted ones, which is why both are read here.
    """
    out = [
        str(m.get("data", ""))
        for m in reply.get("messages", []) or []
        if str(m.get("severity", "")).lower() == "error"
    ]
    top = reply.get("message")
    if isinstance(top, str) and top.strip():
        out.append(top.strip())
    return out


def _looks_like_parse_error(messages: list[str]) -> bool:
    lowered = " ".join(messages).lower()
    return any(hint in lowered for hint in _PARSE_HINTS)


#: Ways a tactic can leave the goal unproved while looking like it closed it. `sorry` and `admit`
#: are the surface syntax; `sorryAx` is the axiom they elaborate to, and it is what actually
#: appears when the hole arrives through a lemma or a macro rather than being typed at this step.
_SORRY_TOKENS = ("sorry", "admit", "sorryax")


def _is_sorry(reply: dict[str, Any], tactic_text: str) -> bool:
    """Did this step close the goal with a hole rather than a proof?

    Checking only for the literal string `sorry` in the tactic text -- which is what this used to
    do -- misses `admit`, misses a `sorryAx` introduced through a lemma the step applied, and
    misses any hole the REPL reports without the word appearing in the tactic. Every channel the
    REPL offers is inspected, and the tactic text is only one of them: a proof accepted here is
    later counted as evidence that the model proved the theorem.
    """
    # A non-empty `sorries` list is the REPL saying so directly, whatever the entries look like:
    # they are goal records, and the word `sorry` need not appear anywhere inside them.
    if reply.get("sorries"):
        return True
    blob = " ".join(
        [
            str(reply.get("proofStatus", "")),
            json.dumps(reply.get("messages", "")),
            tactic_text,
        ]
    ).lower()
    return any(tok in blob for tok in _SORRY_TOKENS)


def verify_trace(
    repl: LeanREPL,
    proof_text: str,
    *,
    trace_id: str,
    problem_id: str,
    header: str | None = None,
    model_id: str = "",
    temperature: float | None = None,
    sample_index: int = 0,
    per_step_timeout_s: float = 60.0,
    whole_proof_timeout_s: float = 180.0,
    check_whole_proof: bool = True,
) -> ProofTrace:
    """Label every tactic of one sampled proof, and locate `t*`.

    `v_t = 1` iff tactic `t` elaborates without error against the state left by tactics `1..t-1`
    and does not close the goal with `sorry`. Labels are absorbing: after the first rejected step
    every later step is 0 and is marked `unreached`, because it was never run -- treating those as
    observed failures would fabricate data.
    """
    t0 = time.time()
    if header is None:
        header, body = split_header_and_proof(proof_text)
    else:
        body = proof_text
    if not header:
        return ProofTrace(
            trace_id=trace_id,
            problem_id=problem_id,
            model_id=model_id,
            temperature=temperature,
            sample_index=sample_index,
            proof_text=proof_text,
            outcome=TraceOutcome.PARSE_ERROR,
            elapsed_s=time.time() - t0,
            error="no `:= by` found; the trace has no tactic block",
        )

    segments: list[Segment] = segment_proof(body)
    trace = ProofTrace(
        trace_id=trace_id,
        problem_id=problem_id,
        model_id=model_id,
        temperature=temperature,
        sample_index=sample_index,
        theorem_statement=header,
        header=header,
        proof_text=proof_text,
    )
    if not segments:
        trace.outcome = TraceOutcome.PARSE_ERROR
        trace.error = "the tactic block is empty"
        trace.elapsed_s = time.time() - t0
        return trace

    # 1. Whole-proof compilation, which must agree with the step replay by construction.
    if check_whole_proof:
        try:
            whole = repl.command(f"{header}\n{body}", timeout_s=whole_proof_timeout_s)
            errs = _errors(whole)
            trace.whole_proof_ok = not errs
            if errs and _looks_like_parse_error(errs):
                trace.outcome = TraceOutcome.PARSE_ERROR
                trace.error = errs[0][:500]
                trace.elapsed_s = time.time() - t0
                return trace
        except TimeoutError:
            trace.whole_proof_ok = None
        except ReplError as exc:
            repl.restart()
            trace.outcome = TraceOutcome.REPL_FAILURE
            trace.error = str(exc)[:500]
            trace.elapsed_s = time.time() - t0
            return trace

    # 2. Open the goal with `sorry` to obtain the initial proof state.
    try:
        opened = repl.command(f"{header}\n  sorry", timeout_s=whole_proof_timeout_s)
    except TimeoutError:
        trace.outcome = TraceOutcome.TIMEOUT
        trace.error = "timed out elaborating the theorem statement"
        trace.elapsed_s = time.time() - t0
        return trace
    except ReplError as exc:
        repl.restart()
        trace.outcome = TraceOutcome.REPL_FAILURE
        trace.error = str(exc)[:500]
        trace.elapsed_s = time.time() - t0
        return trace

    sorries = opened.get("sorries") or []
    if not sorries:
        # The statement itself does not elaborate: no step structure to label.
        trace.outcome = TraceOutcome.PARSE_ERROR
        trace.error = "; ".join(_errors(opened))[:500] or "the theorem statement did not elaborate"
        trace.elapsed_s = time.time() - t0
        return trace

    state = int(sorries[0]["proofState"])
    goals_before = 1
    t_star: int | None = None
    completed = False

    # 3. Replay tactics one at a time.
    for i, seg in enumerate(segments):
        if t_star is not None:
            trace.steps.append(
                StepLabel(
                    index=i,
                    tactic=seg.text,
                    status=StepStatus.UNREACHED,
                    valid=False,
                    line_start=seg.line_start,
                    line_end=seg.line_end,
                    n_lines=seg.n_lines,
                    has_combinator=seg.has_combinator,
                    is_structured=seg.is_structured,
                )
            )
            continue

        s0 = time.time()
        status = StepStatus.OK
        message = ""
        goals_after: int | None = None
        try:
            reply = repl.tactic(seg.text, state, timeout_s=per_step_timeout_s)
            errs = _errors(reply)
            if errs:
                status = StepStatus.ERROR
                message = errs[0][:500]
            elif "proofState" not in reply:
                # No new state and no diagnostic: the tactic did not advance the proof. Carrying
                # the old state forward would replay the next tactic against a state that was
                # never reached, so this is a rejection, not a step to be skipped.
                status = StepStatus.ERROR
                message = f"the REPL returned no proof state: {json.dumps(reply)[:300]}"
            elif _is_sorry(reply, seg.text):
                status = StepStatus.SORRY
                message = "the step leaves a hole (`sorry`, `admit` or `sorryAx`)"
            else:
                state = int(reply["proofState"])
                goals_after = len(reply.get("goals") or [])
                completed = str(reply.get("proofStatus", "")).startswith("Completed")
        except TimeoutError:
            # The REPL resynchronises itself before the next call; a timeout is a property of
            # this step, reported separately per Appendix B.2, not a reason to lose the batch.
            status = StepStatus.TIMEOUT
            message = f"the tactic did not elaborate within {per_step_timeout_s}s"
        except ReplError as exc:
            trace.steps.append(
                StepLabel(
                    index=i,
                    tactic=seg.text,
                    status=StepStatus.UNREACHED,
                    valid=False,
                    line_start=seg.line_start,
                    line_end=seg.line_end,
                    n_lines=seg.n_lines,
                    message=str(exc)[:500],
                )
            )
            repl.restart()
            trace.outcome = TraceOutcome.REPL_FAILURE
            trace.error = str(exc)[:500]
            trace.elapsed_s = time.time() - t0
            return trace

        valid = status == StepStatus.OK
        trace.steps.append(
            StepLabel(
                index=i,
                tactic=seg.text,
                status=status,
                valid=valid,
                line_start=seg.line_start,
                line_end=seg.line_end,
                n_lines=seg.n_lines,
                message=message,
                goals_before=goals_before,
                goals_after=goals_after,
                elapsed_s=round(time.time() - s0, 4),
                has_combinator=seg.has_combinator,
                is_structured=seg.is_structured,
            )
        )
        goals_before = goals_after if goals_after is not None else goals_before
        if not valid:
            t_star = i

    # 4. "unsolved goals" at the end is a failure of the last step.
    if t_star is None and not completed:
        last = trace.steps[-1]
        last.status = StepStatus.UNSOLVED_GOALS
        last.valid = False
        last.message = last.message or "the proof ended with goals remaining"
        t_star = last.index

    trace.t_star = t_star
    trace.outcome = TraceOutcome.VERIFIED if t_star is None else TraceOutcome.REFUTED
    if t_star is not None and trace.steps[t_star].status == StepStatus.TIMEOUT:
        # Reported separately, per Appendix B.2, but still a refutation at that step.
        trace.meta["timeout_at"] = t_star
    trace.elapsed_s = time.time() - t0
    return trace
