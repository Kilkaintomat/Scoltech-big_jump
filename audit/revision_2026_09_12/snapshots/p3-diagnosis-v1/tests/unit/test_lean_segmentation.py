"""Segmenting a Lean 4 proof into the steps that receive labels (Appendix B.1)."""

from __future__ import annotations

import pytest

from onebigjump.lean import segment_proof, split_header_and_proof, strip_comments


class TestStripComments:
    def test_line_comments_go_but_lines_stay(self) -> None:
        out = strip_comments("simp -- why\nring")
        assert out == "simp\nring"

    def test_block_comments_go_and_line_numbering_is_preserved(self) -> None:
        src = "simp\n/- a\n   b -/\nring"
        out = strip_comments(src)
        assert out.split("\n") == ["simp", "", "", "ring"]

    def test_a_comment_marker_inside_a_block_comment_is_not_special(self) -> None:
        assert strip_comments("/- -- not a line comment -/\nsimp").split("\n") == ["", "simp"]

    def test_nested_block_comments(self) -> None:
        assert strip_comments("/- a /- b -/ c -/\nsimp").split("\n") == ["", "simp"]


class TestHeaderSplit:
    def test_by_at_the_end_of_the_statement_line(self) -> None:
        head, body = split_header_and_proof("theorem t : P := by\n  simp\n  ring")
        assert head == "theorem t : P := by"
        assert body == "  simp\n  ring"

    def test_by_followed_by_a_tactic_on_the_same_line(self) -> None:
        head, body = split_header_and_proof("theorem t : P := by simp\n  ring")
        assert head == "theorem t : P := by"
        assert body.split("\n") == ["simp", "  ring"]

    def test_a_multi_line_statement(self) -> None:
        src = "theorem t (a : Nat)\n    (h : a = 0) :\n    a + 0 = 0 := by\n  simp [h]"
        head, body = split_header_and_proof(src)
        assert head.endswith(":= by")
        assert head.count("\n") == 2
        assert body == "  simp [h]"

    def test_no_by_gives_an_empty_header(self) -> None:
        head, body = split_header_and_proof("theorem t : P := trivial")
        assert head == ""
        assert body == "theorem t : P := trivial"


class TestSegmentation:
    def test_one_tactic_per_line(self) -> None:
        segs = segment_proof("  simp\n  ring\n  omega")
        assert [s.text for s in segs] == ["simp", "ring", "omega"]
        assert [s.line_start for s in segs] == [0, 1, 2]

    def test_a_structured_have_block_is_one_segment(self) -> None:
        """The REPL reports one verdict for it, so splitting further would leave holes in v_t."""
        segs = segment_proof("  have h : P := by\n    simp\n    ring\n  exact h")
        assert len(segs) == 2
        assert segs[0].text == "have h : P := by\n  simp\n  ring"
        assert segs[0].is_structured
        assert segs[0].n_lines == 3
        assert segs[1].text == "exact h"

    def test_bullets_belong_to_the_tactic_above_them(self) -> None:
        segs = segment_proof("  cases h with\n  | inl a => simp\n  | inr b => omega\n  rfl")
        assert len(segs) == 2
        assert segs[0].text.startswith("cases h with")
        assert "| inl a => simp" in segs[0].text
        assert "| inr b => omega" in segs[0].text
        assert segs[1].text == "rfl"

    def test_dot_bullets_are_absorbed_too(self) -> None:
        segs = segment_proof("  constructor\n  · simp\n  · ring\n  done")
        assert [s.text.split("\n")[0] for s in segs] == ["constructor", "done"]
        assert segs[0].n_lines == 3

    def test_combinators_stay_on_their_step(self) -> None:
        segs = segment_proof("  simp <;> ring\n  omega")
        assert len(segs) == 2
        assert segs[0].text == "simp <;> ring"
        assert segs[0].has_combinator
        assert not segs[1].has_combinator

    def test_semicolon_sequencing_is_one_step(self) -> None:
        segs = segment_proof("  intro h; simp")
        assert len(segs) == 1
        assert segs[0].has_combinator

    def test_a_type_ascription_colon_is_not_a_combinator(self) -> None:
        segs = segment_proof("  have h : a = b := rfl")
        assert not segs[0].has_combinator

    def test_comments_do_not_become_steps(self) -> None:
        segs = segment_proof("  -- set up\n  simp\n  /- done -/\n  ring")
        assert [s.text for s in segs] == ["simp", "ring"]

    def test_line_numbers_are_offset_by_base_line(self) -> None:
        segs = segment_proof("  simp\n  ring", base_line=10)
        assert [s.line_start for s in segs] == [10, 11]

    def test_every_source_line_lands_in_some_segment(self) -> None:
        """A line with no segment is a step with no label, which absorption cannot tolerate."""
        proof = "  have h : P := by\n    simp\n  cases h with\n  | inl a => rfl\n  exact h"
        segs = segment_proof(proof)
        covered = set()
        for s in segs:
            covered.update(range(s.line_start, s.line_end + 1))
        assert covered == {0, 1, 2, 3, 4}

    def test_an_empty_block_gives_no_segments(self) -> None:
        assert segment_proof("") == []
        assert segment_proof("\n\n   \n") == []

    def test_trailing_blank_lines_are_not_absorbed_into_the_last_step(self) -> None:
        segs = segment_proof("  simp\n\n\n")
        assert len(segs) == 1
        assert segs[0].text == "simp"
        assert segs[0].line_end == 0

    @pytest.mark.parametrize(
        "opener", ["have", "calc", "cases", "rcases", "obtain", "induction", "conv", "suffices"]
    )
    def test_structured_openers_are_flagged(self, opener: str) -> None:
        segs = segment_proof(f"  {opener} x\n    inner")
        assert segs[0].is_structured
