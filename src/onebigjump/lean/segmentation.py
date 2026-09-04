"""Split a Lean 4 proof into the steps that get labels.

Appendix B.1 fixes the rule: one tactic per line; tactic blocks joined by `;` or `<;>` and
structured blocks (`have`, `calc`, `cases` with bullets) are segmented **at the granularity at
which the REPL reports errors, so that every segment receives a label**.

That last clause is the operative one and it fixes the algorithm: a segment is a tactic at the
current indentation together with every more-indented line that follows it. The REPL evaluates
`have h : P := by\n  simp\n  ring` as a single tactic and reports a single verdict for it, so
splitting it further would produce segments that cannot be labelled -- and an unlabelled segment
is a hole in `v_t`, which the absorption argument of Section 2 does not tolerate.

Combinators are kept on their line for the same reason: the REPL reports one verdict for
`simp <;> ring`, so it is one step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["Segment", "segment_proof", "split_header_and_proof", "strip_comments"]

# `by` opening a proof, possibly at the end of the theorem line.
_BY_TAIL = re.compile(r":=\s*by\b\s*$")
_BY_INLINE = re.compile(r":=\s*by\b")
# `<;>` first so it is reported as the combinator it is; a bare `;` also sequences.
_COMBINATOR = re.compile(r"<;>|;")
_STRUCTURED = re.compile(
    r"^\s*(have|calc|cases|rcases|obtain|induction|match|conv|suffices|show|refine)\b"
)
_BULLET = re.compile(r"^\s*([·.]|\||\d+\.)\s")


@dataclass
class Segment:
    """One labelled step: a tactic plus where it came from in the source."""

    text: str
    line_start: int
    line_end: int
    indent: int
    has_combinator: bool = False
    is_structured: bool = False
    continuation_lines: list[str] = field(default_factory=list)

    @property
    def n_lines(self) -> int:
        return self.line_end - self.line_start + 1


def strip_comments(text: str) -> str:
    """Remove `--` line comments and `/- ... -/` block comments, preserving line numbering.

    Line numbering is preserved because the segment boundaries are reported back against the
    original source, and a trace whose steps point at the wrong lines is unusable for the
    activation extraction of Appendix B.1, which reads at the token that ends each step.
    """
    out: list[str] = []
    depth = 0
    for line in text.split("\n"):
        buf: list[str] = []
        i = 0
        while i < len(line):
            two = line[i : i + 2]
            if depth == 0 and two == "--":
                break
            if two == "/-":
                depth += 1
                i += 2
                continue
            if two == "-/" and depth > 0:
                depth -= 1
                i += 2
                continue
            if depth == 0:
                buf.append(line[i])
            i += 1
        out.append("".join(buf).rstrip())
    return "\n".join(out)


def split_header_and_proof(text: str) -> tuple[str, str]:
    """Separate everything up to and including the opening `by` from the tactic block.

    Provers in chain-of-thought mode emit informal reasoning before the formal proof; the caller
    is responsible for having isolated the Lean block. What this handles is the boundary *inside*
    the Lean block, between the theorem statement and the first tactic.
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if _BY_TAIL.search(line):
            return "\n".join(lines[: i + 1]), "\n".join(lines[i + 1 :])
        m = _BY_INLINE.search(line)
        if m:
            # `:= by tac` on one line: the tail after `by` is the first tactic.
            head = line[: m.end()]
            tail = line[m.end() :].strip()
            rest = lines[i + 1 :]
            if tail:
                rest = [tail, *rest]
            return "\n".join([*lines[:i], head]), "\n".join(rest)
    return "", text


def segment_proof(proof: str, *, base_line: int = 0) -> list[Segment]:
    """Split a tactic block into labelled segments.

    A segment starts at a line whose indentation is the block's minimum and absorbs every
    following line indented further. Bullet lines (`·`, `.`, `|`) belong to the structured
    tactic above them and never start a segment of their own.
    """
    cleaned = strip_comments(proof)
    lines = cleaned.split("\n")

    # The block's own indentation level: the smallest indent among its non-empty lines.
    indents = [len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()]
    if not indents:
        return []
    base_indent = min(indents)

    segments: list[Segment] = []
    current: Segment | None = None

    for offset, raw in enumerate(lines):
        if not raw.strip():
            if current is not None:
                current.continuation_lines.append(raw)
            continue
        indent = len(raw) - len(raw.lstrip())
        starts_segment = indent <= base_indent and not _BULLET.match(raw)

        if starts_segment:
            if current is not None:
                _finalise(current)
                segments.append(current)
            current = Segment(
                text=raw.strip(),
                line_start=base_line + offset,
                line_end=base_line + offset,
                indent=indent,
                has_combinator=bool(_COMBINATOR.search(raw)),
                is_structured=bool(_STRUCTURED.match(raw)),
            )
        else:
            if current is None:
                # A block that starts indented (a stray continuation); treat it as its own step
                # rather than dropping it, so that every source line lands in some segment.
                current = Segment(
                    text=raw.strip(),
                    line_start=base_line + offset,
                    line_end=base_line + offset,
                    indent=indent,
                    has_combinator=bool(_COMBINATOR.search(raw)),
                    is_structured=bool(_STRUCTURED.match(raw)),
                )
                continue
            current.continuation_lines.append(raw)
            current.line_end = base_line + offset
            if _COMBINATOR.search(raw):
                current.has_combinator = True

    if current is not None:
        _finalise(current)
        segments.append(current)
    return segments


def _finalise(seg: Segment) -> None:
    """Re-attach continuation lines, dedented to the segment's own indentation."""
    body = [ln for ln in seg.continuation_lines if ln.strip() or seg.continuation_lines]
    while body and not body[-1].strip():
        body.pop()
    if not body:
        seg.continuation_lines = []
        return
    seg.text = "\n".join(
        [seg.text, *(ln[seg.indent :] if len(ln) > seg.indent else ln.lstrip() for ln in body)]
    )
    seg.continuation_lines = body
