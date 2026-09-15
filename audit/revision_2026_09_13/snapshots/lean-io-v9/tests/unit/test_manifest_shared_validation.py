"""Shared DAG validation must retain content checks, including between independent calls."""

import json

import pytest

from onebigjump.e1 import artifacts as a


def graph(tmp_path):
    leaf = tmp_path / "leaf.txt"
    leaf.write_text("first")
    common = tmp_path / "common-manifest.json"
    common.write_text(json.dumps({"inputs": {}, "outputs": {str(leaf): a.digest(leaf)}}))
    parents = []
    for name in ("left", "right"):
        p = tmp_path / (name + "-manifest.json")
        p.write_text(json.dumps({"inputs": {str(common): a.digest(common)}, "outputs": {}}))
        parents.append(p)
    return leaf, parents


def test_finish_checks_shared_leaf_once_but_checks_every_parent(tmp_path, monkeypatch):
    leaf, parents = graph(tmp_path)
    original = a.digest
    reads = []

    def counted(path):
        reads.append(str(path))
        return original(path)

    monkeypatch.setattr(a, "digest", counted)
    output = tmp_path / "result"
    a.finish(output, stage="test", context={}, inputs=parents, outputs=[], metrics={})
    assert reads.count(str(leaf)) == 1
    assert all(str(p) in reads for p in parents)


def test_separate_finish_calls_detect_changed_shared_leaf(tmp_path):
    leaf, parents = graph(tmp_path)
    a.finish(tmp_path / "good", stage="test", context={}, inputs=parents, outputs=[], metrics={})
    leaf.write_text("other")
    with pytest.raises(ValueError, match="manifest digest mismatch"):
        a.finish(tmp_path / "bad", stage="test", context={}, inputs=parents, outputs=[], metrics={})
    assert not (tmp_path / "bad/manifest.json").exists()


def test_second_parent_digest_is_not_skipped(tmp_path):
    _leaf, parents = graph(tmp_path)
    data = json.loads(parents[1].read_text())
    data["inputs"][next(iter(data["inputs"]))] = "0" * 64
    parents[1].write_text(json.dumps(data))
    with pytest.raises(ValueError, match="manifest digest mismatch"):
        a.finish(tmp_path / "bad", stage="test", context={}, inputs=parents, outputs=[], metrics={})
