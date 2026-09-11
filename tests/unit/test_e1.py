"""E1 integrity cases that distinguish a scientific pipeline from a successful process exit."""

import json

import pytest

from onebigjump.e1.artifacts import Journal, finish, verify_manifest
from onebigjump.e1.spans import SourceExclusion, formal_body, mask_comments
from onebigjump.lean.segmentation import segment_proof, strip_comments
from onebigjump.lean.verifier import _is_sorry


def test_journal_rejects_changed_inputs_duplicate_and_corrupt_rows(tmp_path):
    path = tmp_path / "attempts.jsonl"
    with Journal(path, {"source": "one"}) as journal:
        journal.append({"trace_id": "a", "value": 4}, "input-a")
        with pytest.raises(ValueError):
            journal.append({"trace_id": "a"}, "input-a")
    with Journal(path, {"source": "one"}) as journal:
        assert journal.existing("a", "input-a")["value"] == 4
        with pytest.raises(ValueError):
            journal.existing("a", "changed")
    with pytest.raises(ValueError):
        Journal(path, {"source": "two"})
    row = json.loads(path.read_text())
    row["value"] = 99
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError):
        Journal(path, {"source": "one"})


def test_torn_journal_last_line_is_quarantined(tmp_path):
    path = tmp_path / "records.jsonl"
    with Journal(path, {}) as journal:
        journal.append({"trace_id": "a"}, "input")
    before = path.read_bytes()
    with path.open("ab") as f:
        f.write(b'{"trace_id":"unfinished')
    with Journal(path, {}) as journal:
        assert list(journal.rows) == ["a"]
    assert path.read_bytes() == before
    assert len(list(tmp_path.glob("*.torn-*"))) == 1


def test_manifest_graph_blocks_changed_ancestor(tmp_path):
    raw = tmp_path / "raw"
    raw.write_text("original")
    first = tmp_path / "first"
    first.mkdir()
    man = finish(first, stage="one", context={}, inputs=[raw], outputs=[], metrics={})
    second = tmp_path / "second"
    second.mkdir()
    child = finish(second, stage="two", context={}, inputs=[man], outputs=[], metrics={})
    verify_manifest(child)
    raw.write_text("changed")
    with pytest.raises(ValueError, match="mismatch"):
        verify_manifest(child)


def test_comments_inside_strings_do_not_modify_tactics_or_create_holes():
    body = 'have s : String := "-- /- sorry -/"\ntrivial -- sorry'
    assert '"-- /- sorry -/"' in strip_comments(body)
    assert len(segment_proof(body)) == 2
    assert not _is_sorry({"proofStatus": "Completed"}, body)
    assert _is_sorry({"proofStatus": "Completed"}, "exact sorryAx False false")
    assert len(mask_comments(body)) == len(body)


def test_trusted_header_rejects_substitution_and_extra_context():
    statement = "theorem target : False := by"
    with pytest.raises(SourceExclusion) as exc:
        formal_body(
            "```lean4\ntheorem target : True := by\n trivial\n```", statement, "import Mathlib"
        )
    assert exc.value.category == "context_statement_mismatch"
    with pytest.raises(SourceExclusion):
        formal_body(
            "```lean4\naxiom fake : False\ntheorem target : False := by\n exact fake\n```",
            statement,
            "import Mathlib",
        )


def test_inline_and_nested_steps_have_exact_original_spans():
    statement = "theorem target : True := by"
    text = "plan\n```lean4\ntheorem target : True := by have h : True := by\n    trivial\n  exact h\n```"
    parsed = formal_body(text, statement, "")
    assert len(parsed["step_spans"]) == 2
    assert [text[s["start"] : s["end"]] for s in parsed["step_spans"]] == [
        "have h : True := by\n    trivial",
        "exact h",
    ]


@pytest.mark.ml
def test_original_byte_pieces_accept_noncanonical_bpe_without_reencoding():
    pytest.importorskip("transformers")
    from transformers.models.gpt2.tokenization_gpt2 import bytes_to_unicode

    from onebigjump.e1.spans import original_token_spans

    mapping = bytes_to_unicode()
    encoded = ["".join(mapping[b] for b in text.encode()) for text in ["hello", " ", "world"]]

    class FakeTokenizer:
        def get_added_vocab(self):
            return {}

        def convert_ids_to_tokens(self, ids):
            return [encoded[i] for i in ids]

        def decode(self, ids, **kwargs):
            return "hello world"

        def __call__(self, *args, **kwargs):
            raise AssertionError("must not re-encode")

    assert original_token_spans(FakeTokenizer(), [0, 1, 2], "hello world") == [
        (0, 5),
        (5, 6),
        (6, 11),
    ]
