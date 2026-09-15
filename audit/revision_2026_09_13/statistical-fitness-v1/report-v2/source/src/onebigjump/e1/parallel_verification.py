"""Bounded concurrency of independent Lean processes; the caller alone writes the journal."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from typing import Any

from ..lean.environment import discover
from ..lean.verifier import LeanREPL
from .verification import verify_one


def verify_stream(
    samples: list[dict[str, Any]],
    problems: dict[str, dict[str, Any]],
    settings: dict[str, Any],
    workers: int = 1,
) -> Iterator[dict[str, Any]]:
    """Each lane owns a REPL. No Lean state or journal is shared between lanes.

    Threads only coordinate external Lean processes. Completed results reach the parent
    immediately. Exceptions stop new work, close every REPL, and propagate to the caller.
    Heartbeat and wall-clock budgets are unchanged. Output order is completion order.
    """
    if not 1 <= workers <= 4:
        raise ValueError("verification workers must be between 1 and 4")
    ids = [str(sample["trace_id"]) for sample in samples]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate input trace ID")
    if not samples:
        return
    count = min(workers, len(samples))
    messages: Queue[tuple[str, Any]] = Queue()
    stop = Event()

    def lane(index: int) -> None:
        try:
            with LeanREPL(
                discover(settings["workspace"]),
                imports="import Mathlib\nimport Aesop",
                startup_timeout_s=settings["startup_timeout_s"],
            ) as repl:
                for sample in samples[index::count]:
                    if stop.is_set():
                        break
                    result = verify_one(repl, sample, problems[sample["problem_id"]], settings)
                    result["role"] = sample["role"]
                    result["task_family"] = sample["task_family"]
                    result["execution"] = {
                        "workers": workers,
                        "lane": index,
                        "startup_diagnostics": list(repl.startup_diagnostics),
                    }
                    messages.put(("result", result))
        except BaseException as exc:
            stop.set()
            messages.put(("error", exc))
        finally:
            messages.put(("done", index))

    with ThreadPoolExecutor(max_workers=count, thread_name_prefix="lean-lane") as pool:
        futures = [pool.submit(lane, index) for index in range(count)]
        done = 0
        try:
            while done < count:
                kind, value = messages.get()
                if kind == "result":
                    yield value
                elif kind == "error":
                    raise value
                else:
                    done += 1
            for future in futures:
                future.result()
        finally:
            stop.set()
