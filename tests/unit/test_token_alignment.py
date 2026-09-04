"""Mapping labelled steps to the token positions where the residual stream is read."""

from __future__ import annotations

import pytest

from onebigjump.lean import segment_proof, split_header_and_proof
from onebigjump.models.token_alignment import (
    StepSpan,
    align_steps,
    line_offsets,
    step_char_spans,
)


class TestLineOffsets:
    def test_offsets_point_at_line_starts(self) -> None:
        text = "aa\nbbb\nc"
        offs = line_offsets(text)
        assert offs == [0, 3, 7]
        assert [text[o] for o in offs] == ["a", "b", "c"]

    def test_single_line(self) -> None:
        assert line_offsets("abc") == [0]


class TestStepCharSpans:
    def test_spans_recover_the_step_text(self) -> None:
        body = "  simp\n  ring\n  omega"
        segs = segment_proof(body)
        spans = step_char_spans(body, segs)
        assert [body[s.start : s.end] for s in spans] == ["  simp", "  ring", "  omega"]

    def test_trailing_whitespace_is_excluded(self) -> None:
        """A readout on a trailing space is neither X_t nor X_{t+1}."""
        body = "  simp   \n  ring"
        spans = step_char_spans(body, segment_proof(body))
        assert body[spans[0].end - 1] == "p"

    def test_multi_line_steps_span_the_whole_block(self) -> None:
        body = "  have h : P := by\n    simp\n  exact h"
        spans = step_char_spans(body, segment_proof(body))
        assert body[spans[0].start : spans[0].end] == "  have h : P := by\n    simp"
        assert body[spans[1].start : spans[1].end] == "  exact h"

    def test_base_offset_shifts_every_span(self) -> None:
        body = "  simp\n  ring"
        a = step_char_spans(body, segment_proof(body))
        b = step_char_spans(body, segment_proof(body), base_offset=100)
        assert [s.start for s in b] == [s.start + 100 for s in a]

    def test_records_work_as_well_as_segments(self) -> None:
        body = "  simp\n  ring"
        as_dicts = [
            {"index": 0, "line_start": 0, "line_end": 0},
            {"index": 1, "line_start": 1, "line_end": 1},
        ]
        assert step_char_spans(body, as_dicts) == step_char_spans(body, segment_proof(body))

    def test_an_empty_span_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty character span"):
            StepSpan(index=0, start=5, end=5)


class TestAlignSteps:
    @staticmethod
    def _offsets(text: str, pieces: list[str]) -> list[tuple[int, int]]:
        """A toy offset mapping: consecutive, non-overlapping pieces of `text`."""
        out, pos = [], 0
        for piece in pieces:
            start = text.index(piece, pos)
            out.append((start, start + len(piece)))
            pos = start + len(piece)
        return out

    def test_readout_positions_are_prompt_end_then_step_ends(self) -> None:
        text = "PROMPT\nsimp\nring"
        offsets = self._offsets(text, ["PROMPT", "\n", "simp", "\n", "ring"])
        spans = [StepSpan(0, 7, 11), StepSpan(1, 12, 16)]
        al = align_steps(offsets, spans, prompt_char_end=7)
        assert al.prompt_end_token == 1  # the newline closing the prompt
        assert al.step_end_tokens == [2, 4]
        assert al.readout_positions == [1, 2, 4]
        assert al.complete

    def test_special_tokens_are_not_treated_as_position_zero(self) -> None:
        text = "PROMPT\nsimp"
        offsets = [(0, 0), *self._offsets(text, ["PROMPT", "\n", "simp"]), (0, 0)]
        al = align_steps(offsets, [StepSpan(0, 7, 11)], prompt_char_end=7)
        assert al.prompt_end_token == 2
        assert al.step_end_tokens == [3]

    def test_a_step_spanning_several_tokens_ends_at_the_last(self) -> None:
        text = "P\nsimp only [h]"
        offsets = self._offsets(text, ["P", "\n", "simp", " only", " [h]"])
        al = align_steps(offsets, [StepSpan(0, 2, 15)], prompt_char_end=2)
        assert al.step_token_spans == [(2, 4)]
        assert al.step_end_tokens == [4]

    def test_an_unmatched_step_is_reported_not_dropped_silently(self) -> None:
        text = "P\nsimp"
        offsets = self._offsets(text, ["P", "\n", "simp"])
        al = align_steps(offsets, [StepSpan(0, 2, 6), StepSpan(1, 900, 950)], prompt_char_end=2)
        assert al.unaligned == [1]
        assert not al.complete

    def test_a_prompt_with_no_tokens_raises(self) -> None:
        with pytest.raises(ValueError, match="no token lies inside the prompt"):
            align_steps([(5, 9)], [StepSpan(0, 5, 9)], prompt_char_end=0)

    def test_no_real_tokens_raises(self) -> None:
        with pytest.raises(ValueError, match="no real tokens"):
            align_steps([(0, 0), (0, 0)], [StepSpan(0, 1, 2)], prompt_char_end=1)

    def test_it_is_serialisable(self) -> None:
        import json

        text = "P\nsimp"
        offsets = self._offsets(text, ["P", "\n", "simp"])
        al = align_steps(offsets, [StepSpan(0, 2, 6)], prompt_char_end=2)
        json.loads(json.dumps(al.as_dict()))


class TestAgainstRealSegmentation:
    def test_a_lean_proof_aligns_end_to_end(self) -> None:
        proof = "theorem t (a b : Nat) : a + b = b + a := by\n  rw [Nat.add_comm]\n  simp\n  done"
        header, body = split_header_and_proof(proof)
        segs = segment_proof(body)
        prompt = "Prove:\n" + header + "\n"
        spans = step_char_spans(body, segs, base_offset=len(prompt))
        full = prompt + body
        for seg, span in zip(segs, spans, strict=True):
            assert full[span.start : span.end].strip() == seg.text.strip()
