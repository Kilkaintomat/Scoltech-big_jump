"""Lean source spans and original byte-BPE token alignment; no re-encoding of completions."""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from typing import Any

from ..lean.segmentation import segment_proof


class SourceExclusion(ValueError):
    def __init__(self, category: str, reason: str):
        super().__init__(reason)
        self.category = category


def mask_comments(text: str, *, mask_strings: bool = False) -> str:
    from ..lean.lexical import mask_comments as scan

    try:
        return scan(text, mask_strings=mask_strings)
    except ValueError as exc:
        raise SourceExclusion("unsupported_segmentation", str(exc)) from exc


def lexical_tokens(text: str) -> list[str]:
    return re.findall(
        r'"(?:\\.|[^"\\])*"|«[^»]*»|[\w\u0080-\uffff]+(?:\x27+)?|[^\s]', mask_comments(text)
    )


def formal_body(completion: str, statement: str, trusted_prefix: str) -> dict[str, Any]:
    """Accept one final fenced declaration and run only its body under the trusted header.

    Arbitrary imports/directives/declarations supplied by the model never reach Lean. The
    generated declaration must have the same lexical header as the original problem.
    """
    # Pair all Markdown fences, including non-Lean examples in the reasoning.
    # Ignoring a tactics opening makes its closing fence consume the final proof.
    answer_start = completion.rfind("</think>") + len("</think>") if "</think>" in completion else 0
    fence = re.compile(
        r"^[ \t]*```([^`\n]*)\n(.*?)^[ \t]*```[ \t]*(?=\r?\n|$|<)",
        re.MULTILINE | re.DOTALL,
    )
    blocks = [
        match
        for match in fence.finditer(completion, answer_start)
        if match.group(1).strip() in {"", "lean", "lean4"}
    ]
    if not blocks:
        raise SourceExclusion("parse_error", "no closed Lean code block")
    block = blocks[-1]
    code = block.group(2)
    clean = mask_comments(code)
    declarations = list(re.finditer(r"(?m)^\s*(?:theorem|lemma|example)\s+", clean))
    if len(declarations) != 1:
        raise SourceExclusion("context_statement_mismatch", "expected exactly one declaration")
    decl_start = declarations[0].start()
    while decl_start < len(code) and code[decl_start].isspace():
        decl_start += 1
    prefix = code[:decl_start]
    permitted = {
        tuple(lexical_tokens(line)) for line in trusted_prefix.splitlines() if line.strip()
    }
    for line in mask_comments(prefix).splitlines():
        if line.strip() and tuple(lexical_tokens(line)) not in permitted:
            raise SourceExclusion(
                "context_statement_mismatch", "generated preamble changes trusted context"
            )
    expected = lexical_tokens(statement)
    header_end = None
    for m in re.finditer(r":=\s*by\b", clean[decl_start:]):
        end = decl_start + m.end()
        if lexical_tokens(code[decl_start:end]) == expected:
            header_end = end
            break
    if header_end is None:
        raise SourceExclusion(
            "context_statement_mismatch", "generated theorem differs from original statement"
        )
    body = code[header_end:]
    body_offset = block.start(2) + header_end
    # Turn an inline first tactic into a line with the following block's indentation for replay.
    # The source spans always refer to the original text, independently of replay formatting.
    clean_body = mask_comments(body)
    live = mask_comments(body, mask_strings=True)
    if re.search(
        r"(?m)^\s*(?:theorem|lemma|axiom|def|opaque|namespace|end|import|open|attribute|elab|macro|syntax|set_option)\b",
        live,
    ):
        raise SourceExclusion(
            "context_statement_mismatch", "declaration/directive inside generated body"
        )
    if not clean_body.strip():
        raise SourceExclusion("parse_error", "empty tactic body")
    lines = clean_body.split("\n")
    if lines[0].strip():
        rest_indents = [len(s) - len(s.lstrip()) for s in lines[1:] if s.strip()]
        lines[0] = " " * (min(rest_indents) if rest_indents else 2) + lines[0].lstrip()
    replay_body = "\n".join(lines)
    segments = segment_proof(replay_body)
    starts = [0]
    for m in re.finditer("\n", body):
        starts.append(m.end())
    spans = []
    covered_lines: set[int] = set()
    original_lines = clean_body.split("\n")
    for seg in segments:
        lo = starts[seg.line_start]
        hi = starts[seg.line_end] + len(original_lines[seg.line_end].rstrip())
        while lo < hi and clean_body[lo].isspace():
            lo += 1
        if hi <= lo:
            raise SourceExclusion("unsupported_segmentation", "empty source span")
        covered_lines.update(range(seg.line_start, seg.line_end + 1))
        spans.append(
            {
                "start": body_offset + lo,
                "end": body_offset + hi,
                "tactic": seg.text,
                "line_start": seg.line_start,
                "line_end": seg.line_end,
                "structured": seg.is_structured,
                "combinator": seg.has_combinator,
            }
        )
    if any(s.strip() and i not in covered_lines for i, s in enumerate(original_lines)):
        raise SourceExclusion(
            "unsupported_segmentation", "live source line omitted by segmentation"
        )
    return {
        "body": body,
        "replay_body": replay_body,
        "body_start": body_offset,
        "formal_span": [block.start(2), block.end(2)],
        "step_spans": spans,
        "informal_prefix": completion[: block.start()],
    }


def original_token_spans(tokenizer: Any, ids: list[int], text: str) -> list[tuple[int, int]]:
    """Reconstruct byte offsets from the original vocabulary pieces and verify exact decoding.

    Byte splits inside Unicode characters and noncanonical BPE segmentations are supported.
    Non-byte-level vocabularies or invalid UTF-8 are explicit exclusions for this E1 model.
    """
    from transformers.models.gpt2.tokenization_gpt2 import bytes_to_unicode

    byte_decoder = {v: k for k, v in bytes_to_unicode().items()}
    added = set(tokenizer.get_added_vocab().values())
    pieces = tokenizer.convert_ids_to_tokens(ids)
    chunks = []
    offsets = []
    end = 0
    for token_id, piece in zip(ids, pieces, strict=True):
        try:
            chunk = (
                piece.encode("utf-8")
                if token_id in added
                else bytes(byte_decoder[c] for c in piece)
            )
        except (KeyError, TypeError) as exc:
            raise SourceExclusion(
                "alignment_error", "token is not a supported byte-BPE piece"
            ) from exc
        chunks.append(chunk)
        offsets.append((end, end + len(chunk)))
        end += len(chunk)
    raw = b"".join(chunks)
    decoded = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    if raw != text.encode("utf-8") or decoded != text:
        raise SourceExclusion(
            "alignment_error", "original byte pieces do not reconstruct saved completion exactly"
        )
    return offsets


def align(
    tokenizer: Any,
    prompt_ids: list[int],
    completion_ids: list[int],
    completion: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    offsets = original_token_spans(tokenizer, completion_ids, completion)
    if not prompt_ids or not steps:
        raise SourceExclusion("alignment_error", "no prompt or steps")
    ends = [hi for _, hi in offsets]
    starts = [lo for lo, _ in offsets]
    token_spans = []
    boundary_crossings = []
    previous_hi = -1
    for step in steps:
        lo = len(completion[: step["start"]].encode("utf-8"))
        hi = len(completion[: step["end"]].encode("utf-8"))
        first = bisect_right(ends, lo)
        last = bisect_left(starts, hi) - 1
        if first > last or last >= len(offsets) or first <= previous_hi:
            raise SourceExclusion("alignment_error", "empty or overlapping step token spans")
        token_spans.append([len(prompt_ids) + first, len(prompt_ids) + last])
        boundary_crossings.append(
            {
                "leading_extra_bytes": lo - offsets[first][0],
                "trailing_extra_bytes": offsets[last][1] - hi,
            }
        )
        previous_hi = last
    return {
        "positions": [len(prompt_ids) - 1] + [s[1] for s in token_spans],
        "step_token_spans_inclusive": token_spans,
        "boundary_crossings": boundary_crossings,
        "n_tokens": len(prompt_ids) + len(completion_ids),
        "boundary_rule": "last original token overlapping the final non-comment tactic byte; shared step tokens excluded",
    }
