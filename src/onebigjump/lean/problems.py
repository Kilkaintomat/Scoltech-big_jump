"""Theorem statements to prove, and the prompts that ask a model to prove them.

Section 5.1 samples proofs of miniF2F-test, ProofNet and PutnamBench problems. None of those
ships with this repository: they are third-party datasets, and which of them the paper finally
uses is one of its open placeholders. So this module reads problems from whatever is available --
a local JSONL file, or a Hugging Face dataset -- and normalises them into one record.

The prompt is model-family specific. A prover fine-tuned on a particular template produces very
different output when asked in another, and a template mismatch shows up as a wall of parse
errors rather than as an error message, so the templates are explicit rather than guessed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "PROMPT_TEMPLATES",
    "Problem",
    "build_prompt",
    "extract_lean_block",
    "has_declaration",
    "header_directives",
    "load_problems",
    "modernise_binders",
    "open_for_tactics",
    "split_problems",
]

DEFAULT_HEADER = "import Mathlib\nimport Aesop\nset_option maxHeartbeats 400000\n"

#: Prompt templates, keyed by a substring of the model id. `{header}` and `{statement}` are
#: substituted; the model is expected to continue with the tactic block.
PROMPT_TEMPLATES: dict[str, str] = {
    "deepseek-prover": ("Complete the following Lean 4 code:\n\n```lean4\n{header}\n{statement}\n"),
    "goedel": ("Complete the following Lean 4 code:\n\n```lean4\n{header}\n{statement}\n"),
    "kimina": (
        "Think about and solve the following problem step by step in Lean 4.\n"
        "# Problem\nProve the statement below.\n"
        "# Formal statement\n```lean4\n{header}\n{statement}\n```\n"
    ),
    "default": (
        "Prove the following theorem in Lean 4. Reply with the complete proof.\n\n"
        "```lean4\n{header}\n{statement}\n"
    ),
}

_LEAN_BLOCK = re.compile(r"```(?:lean4?|)\n(.*?)(?:```|\Z)", re.DOTALL)
_THEOREM_START = re.compile(r"^\s*(theorem|lemma|example)\b", re.MULTILINE)


@dataclass
class Problem:
    """One theorem to prove."""

    problem_id: str
    statement: str
    header: str = DEFAULT_HEADER
    split: str = ""
    source: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "statement": self.statement,
            "header": self.header,
            "split": self.split,
            "source": self.source,
            "meta": self.meta,
        }


_BIG_OPERATOR_IN = re.compile(r"(?<=[\u2211\u220f\u2a06\u2a05\u22c3\u22c2])([^,]*?)\s+in\s+")


def modernise_binders(statement: str) -> str:
    """Rewrite the deprecated big-operator binder `\u2211 x in S,` as `\u2211 x \u2208 S,`.

    Mathlib renamed this and current versions reject the old spelling outright: against Mathlib
    85e3a25e the old form fails with `unexpected token 'in'; expected ','`. The Lean 4 ports of
    all three benchmarks predate the change -- 70 of the 702 test-split statements use it -- so
    without this rewrite one statement in eight is a parse error that looks like a broken
    benchmark rather than a stale one.
    """
    return _BIG_OPERATOR_IN.sub("\\1 \u2208 ", statement)


def has_declaration(statement: str) -> bool:
    """Is there a real declaration here, or only commented-out text?

    The Lean 4 port of miniF2F keeps rows whose whole statement is commented out, with a note
    about why it could not be ported (`-- Error: Real^Real`). They carry no theorem, and appended
    to a `sorry` they produce `unexpected token 'sorry'; expected command` -- an error that looks
    like a broken pipeline rather than a placeholder row.
    """
    from .segmentation import strip_comments

    live = [line for line in strip_comments(statement).splitlines() if line.strip()]
    return any(_THEOREM_START.match(line) for line in live)


def header_directives(header: str, extra: str = "") -> str:
    """The part of a problem's header that can be re-issued inside a REPL command.

    Benchmark headers carry `import` lines, and those cannot go into a command: the REPL imports
    all of Mathlib once at startup, and an import inside a command is a syntax error. Worse, the
    lines they carry are often stale -- miniF2F's Lean 4 port still asks for
    `Mathlib.Algebra.BigOperators.Basic`, which current Mathlib has renamed away.

    What must be kept is everything else. `open BigOperators`, `open Real`,
    `open scoped Topology` change how the statement elaborates, and dropping them turns a valid
    theorem into a parse error that looks like a model failure.

    `extra` appends directives a benchmark needs but does not declare. PutnamBench writes `n !`
    and `u\u1d40`, whose notations live in scoped namespaces it never opens, so its statements fail
    with `unexpected token '!'` and `unexpected token '\u1d40'` until `open scoped Nat Matrix` is
    supplied.
    """
    kept = [
        line
        for line in header.splitlines()
        if line.strip() and not line.lstrip().startswith("import ")
    ]
    if extra:
        kept.append(extra)
    return "\n".join(kept)


def open_for_tactics(statement: str) -> str:
    """End a statement at `:= by`, so a prover continues with a tactic block.

    The three benchmarks terminate their statements three different ways, and none of them is
    what the sampler needs:

        miniF2F (cat-searcher/minif2f-lean4)   `... := sorry`
        ProofNet (HaimingW/proofnet-lean4)     `... :=`        (bare)
        PutnamBench (HaimingW/...-lean4)       `... :=\nsorry`

    Left alone, the first and third hand the model a finished declaration and the second an
    incomplete one. Both produce garbage rather than an error.
    """
    text = statement.rstrip()
    if text.endswith("sorry"):
        text = text[: -len("sorry")].rstrip()
    if text.endswith(":="):
        return text + " by"
    if re.search(r":=\s*by\s*$", text):
        return text
    return text + " := by" if not text.endswith("by") else text


def _normalise(record: dict[str, Any], source: str, index: int) -> Problem | None:
    """Map one dataset row onto a `Problem`, or `None` if it carries no statement.

    Field names differ between miniF2F releases, ProofNet, PutnamBench and hand-written files, so
    several spellings are accepted. A row without a statement is skipped rather than turned into
    an empty problem that would later look like a model failure.
    """
    statement = ""
    for key in ("formal_statement", "lean4_statement", "statement", "formal", "theorem", "goal"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            statement = value.strip()
            break
    if not statement:
        return None

    header = ""
    for key in ("header", "srcHeader", "imports"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            header = value.strip()
            break

    problem_id = str(
        record.get("problem_id")
        or record.get("name")
        or record.get("id")
        or f"{source}-{index:05d}"
    )
    return Problem(
        problem_id=problem_id,
        statement=statement,
        header=header or DEFAULT_HEADER,
        split=str(record.get("split", "")),
        source=source,
        meta={k: v for k, v in record.items() if k not in {"formal_statement", "statement"}},
    )


def load_problems(
    source: str | Path,
    *,
    split: str | None = None,
    limit: int | None = None,
    name: str | None = None,
) -> list[Problem]:
    """Load problems from a local JSONL file or a Hugging Face dataset.

    A path that exists on disk is read as JSONL; anything else is treated as a dataset id and
    passed to `datasets.load_dataset`, which is an optional import so that the rest of the
    package works without it.
    """
    path = Path(source)
    if path.is_file():
        records = (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        problems = [p for i, r in enumerate(records) if (p := _normalise(r, path.stem, i))]
    else:
        try:
            from datasets import load_dataset
        except ImportError as exc:  # pragma: no cover - depends on the optional extra
            raise ImportError(
                f"{source!r} is not a file, so it is treated as a Hugging Face dataset id, "
                "which needs the `ml` extra: uv sync --extra ml"
            ) from exc
        ds = load_dataset(str(source), name=name, split=split or "test")
        problems = [p for i, r in enumerate(ds) if (p := _normalise(dict(r), str(source), i))]

    if split:
        filtered = [p for p in problems if p.split == split]
        if filtered:
            problems = filtered
    return problems[:limit] if limit else problems


def split_problems(
    problems: Sequence[Problem], calibration_frac: float = 0.5, seed: int = 0
) -> tuple[list[Problem], list[Problem]]:
    """Split problems into a calibration set and an analysis set.

    The split is by **problem**, not by trace. Appendix B.1 fits the whitening and innovation
    parameters on verified traces of a *disjoint problem split*; splitting by trace would leave
    traces of the same theorem on both sides and leak the analysed distribution into the fit.
    """
    import numpy as np

    order = np.random.default_rng(seed).permutation(len(problems))
    cut = round(calibration_frac * len(problems))
    calib = [problems[int(i)] for i in order[:cut]]
    rest = [problems[int(i)] for i in order[cut:]]
    return calib, rest


def build_prompt(problem: Problem, model_id: str) -> str:
    """The prompt for this model family, with the statement substituted in.

    The header shown to the model is `import Mathlib` plus the problem's own directives, not the
    benchmark's raw import block: those lists are stale (miniF2F still asks for
    `Mathlib.Algebra.BigOperators.Basic`, renamed away) and a prover shown an import that no
    longer resolves tends to reproduce it.
    """
    key = next((k for k in PROMPT_TEMPLATES if k != "default" and k in model_id.lower()), "default")
    directives = problem.meta.get("directives") or header_directives(problem.header)
    header = "import Mathlib" + (f"\n{directives}" if directives else "")
    return PROMPT_TEMPLATES[key].format(header=header, statement=problem.statement)


def extract_lean_block(completion: str, problem: Problem) -> str:
    """Pull the formal proof out of a completion, discarding any informal preamble.

    Provers in chain-of-thought mode emit informal reasoning before the Lean block, and Section
    5.1 labels only the formal tactics. The returned text always begins at the theorem statement,
    so that `split_header_and_proof` sees a well-formed declaration.
    """
    # The prompt templates hand the model an already-open ``` fence and ask it to continue, so a
    # completion normally contains only the *closing* one. Two things follow, and both bit:
    # `_LEAN_BLOCK` happily reads that closer as an opener and captures whatever prose comes
    # after it ("I hope this helps!"), and where nothing follows it the fence itself survives into
    # the proof. In one sampled corpus 3500 of 3616 completions ended in ``` -- a parse error
    # apiece, which reads as a useless model rather than as three stray characters.
    #
    # So a fenced block is only preferred when it actually contains a declaration; otherwise the
    # text is whatever precedes the first fence.
    blocks = [b for b in _LEAN_BLOCK.findall(completion) if _THEOREM_START.search(b)]
    text = max(blocks, key=len) if blocks else completion.split("```", 1)[0]

    match = _THEOREM_START.search(text)
    if match:
        return text[match.start() :].strip()
    # The model continued from a prompt that already contained the statement, so prepend it.
    return f"{problem.statement}\n{text.strip()}" if text.strip() else ""


def iter_jsonl(path: Path | str) -> Iterator[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def write_jsonl(records: Iterable[dict[str, Any]], path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return target
