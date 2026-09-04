"""Map labelled steps to the token positions at which their residual stream is read.

Appendix B.1: `X_t` is the residual stream after block `l` **at the last token of step `s_t`**,
and `X_0` is the same quantity at the last prompt token. Getting this wrong is not a small error:
reading one token early or late samples the state in the middle of a tactic rather than at its
end, and the whole coupling hypothesis is about the state *after* a step.

The mapping goes through character offsets rather than through re-tokenising each step on its
own. Tokenizers are not compositional -- `tokenize(a + b) != tokenize(a) + tokenize(b)` for
byte-level BPE, because a token can straddle the boundary -- so a step's tokens are found by
locating its character span in the full sequence and taking the last token that overlaps it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

__all__ = [
    "StepSpan",
    "TokenAlignment",
    "align_steps",
    "line_offsets",
    "step_char_spans",
]


class _HasOffsets(Protocol):
    """The slice of the tokenizer API used here."""

    def __call__(self, text: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class StepSpan:
    """A step's extent in the generated text, in characters."""

    index: int
    start: int
    end: int  # exclusive

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"empty character span for step {self.index}: [{self.start}, {self.end})")


@dataclass
class TokenAlignment:
    """Where each step ends, in token positions of the full prompt+completion sequence."""

    prompt_end_token: int
    step_end_tokens: list[int]
    step_token_spans: list[tuple[int, int]]
    n_tokens: int
    unaligned: list[int]

    @property
    def readout_positions(self) -> list[int]:
        """`X_0, X_1, ..., X_L`: the last prompt token, then the last token of each step."""
        return [self.prompt_end_token, *self.step_end_tokens]

    @property
    def complete(self) -> bool:
        return not self.unaligned

    def as_dict(self) -> dict[str, Any]:
        return {
            "prompt_end_token": self.prompt_end_token,
            "step_end_tokens": self.step_end_tokens,
            "step_token_spans": [list(s) for s in self.step_token_spans],
            "n_tokens": self.n_tokens,
            "unaligned": self.unaligned,
        }


def line_offsets(text: str) -> list[int]:
    """Character offset at which each line of `text` starts."""
    offsets = [0]
    for line in text.split("\n")[:-1]:
        offsets.append(offsets[-1] + len(line) + 1)
    return offsets


def step_char_spans(
    body: str, steps: Sequence[Any], *, base_offset: int = 0
) -> list[StepSpan]:
    """Character spans of each step, from the line spans the segmenter recorded.

    A step's span ends at its last **non-whitespace** character: trailing spaces and the newline
    belong to no tactic, and a readout taken on them would sample the state after the step's text
    has ended but before the next has begun -- which is neither `X_t` nor `X_{t+1}`.
    """
    starts = line_offsets(body)
    n = len(starts)
    spans: list[StepSpan] = []
    for step in steps:
        first = int(getattr(step, "line_start", step["line_start"]))
        last = int(getattr(step, "line_end", step["line_end"]))
        if not (0 <= first < n):
            continue
        last = min(max(last, first), n - 1)
        start = starts[first]
        end = starts[last] + len(body.split("\n")[last])
        text_slice = body[start:end]
        stripped = text_slice.rstrip()
        if not stripped:
            continue
        idx = int(getattr(step, "index", step.get("index", len(spans))))
        spans.append(
            StepSpan(index=idx, start=base_offset + start, end=base_offset + start + len(stripped))
        )
    return spans


def align_steps(
    offset_mapping: Sequence[tuple[int, int]],
    spans: Sequence[StepSpan],
    prompt_char_end: int,
) -> TokenAlignment:
    """Turn character spans into token positions.

    `offset_mapping` is the `(start, end)` character span of every token of the full sequence, as
    returned by a fast tokenizer with `return_offsets_mapping=True`. Special tokens carry the
    degenerate span `(0, 0)` and are skipped rather than treated as position 0.
    """
    real = [
        (i, s, e)
        for i, (s, e) in enumerate(offset_mapping)
        if e > s  # drop special tokens, which carry (0, 0)
    ]
    if not real:
        raise ValueError("the offset mapping contains no real tokens")

    prompt_tokens = [i for i, s, _ in real if s < prompt_char_end]
    if not prompt_tokens:
        raise ValueError(f"no token lies inside the prompt (prompt_char_end={prompt_char_end})")
    prompt_end = max(prompt_tokens)

    step_end: list[int] = []
    step_spans: list[tuple[int, int]] = []
    unaligned: list[int] = []
    for span in spans:
        inside = [i for i, s, e in real if s < span.end and e > span.start]
        if not inside:
            unaligned.append(span.index)
            continue
        step_end.append(max(inside))
        step_spans.append((min(inside), max(inside)))

    return TokenAlignment(
        prompt_end_token=prompt_end,
        step_end_tokens=step_end,
        step_token_spans=step_spans,
        n_tokens=len(offset_mapping),
        unaligned=unaligned,
    )
