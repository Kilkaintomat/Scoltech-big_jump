"""Seeding, environment capture and atomic writes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from onebigjump.manifests import RunManifest
from onebigjump.reproducibility import (
    atomic_path,
    file_digest,
    git_info,
    hardware_info,
    package_versions,
    rng,
    seed_everything,
    write_json,
)


class TestSeeding:
    def test_same_seed_gives_the_same_stream(self) -> None:
        np.testing.assert_array_equal(rng(42).normal(size=10), rng(42).normal(size=10))

    def test_different_seeds_differ(self) -> None:
        assert not np.array_equal(rng(1).normal(size=10), rng(2).normal(size=10))

    def test_seed_everything_is_reported_back(self) -> None:
        assert seed_everything(123) == 123

    def test_seed_everything_survives_a_huge_seed(self) -> None:
        assert seed_everything(2**40 + 7) == 2**40 + 7


class TestEnvironmentCapture:
    def test_hardware_info_has_the_fields_the_manifest_needs(self) -> None:
        info = hardware_info()
        for key in ("platform", "machine", "python", "cpu_count"):
            assert key in info

    def test_package_versions_include_numpy(self) -> None:
        assert "numpy" in package_versions()

    def test_git_info_finds_this_repository(self) -> None:
        """Where a repository exists. A deployed copy has none, and that is not a failure --
        the manifest then records `commit: null`, which is exactly what it should say."""
        root = Path(__file__).resolve().parents[2]
        info = git_info(root)
        if not (root / ".git").exists():
            assert info["commit"] is None
            return
        assert info["commit"] and len(info["commit"]) == 40
        assert isinstance(info["dirty"], bool)

    def test_git_info_on_a_non_repository_is_all_none(self, tmp_path: Path) -> None:
        info = git_info(tmp_path / "nowhere")
        assert info["commit"] is None

    def test_no_repository_is_unknown_provenance_not_a_clean_tree(self, tmp_path: Path) -> None:
        """The failure this guards against actually happened.

        The cluster tree is an rsynced copy with no `.git`, and `git status` there returns None,
        which `bool()` turned into False -- so every manifest written on the cluster claimed
        `dirty: false`, a clean checkout, when in truth nothing was known about the source at all.
        """
        info = git_info(tmp_path / "nowhere")
        assert info["dirty"] is None
        assert info["available"] is False

    def test_a_manifest_with_no_commit_is_not_reproducible(self, tmp_path: Path) -> None:
        man = RunManifest(name="x", kind="test", out_dir=tmp_path, seed=0)
        man.environment["git"] = git_info(tmp_path / "nowhere")
        assert man.reproducible is False


class TestAtomicWrites:
    def test_the_target_appears_only_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "out.json"
        with atomic_path(target) as tmp:
            tmp.write_text("{}", encoding="utf-8")
            assert not target.exists()
        assert target.read_text(encoding="utf-8") == "{}"

    def test_a_failure_leaves_nothing_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        with pytest.raises(RuntimeError), atomic_path(target) as tmp:
            tmp.write_text("partial", encoding="utf-8")
            raise RuntimeError("boom")
        assert not target.exists()
        assert list(tmp_path.iterdir()) == []

    def test_write_json_handles_numpy_and_paths(self, tmp_path: Path) -> None:
        target = write_json(
            tmp_path / "m.json",
            {
                "a": np.int64(3),
                "b": np.float64(1.5),
                "c": np.arange(3),
                "d": Path("x/y"),
                "e": {np.int64(2), np.int64(1)},
                "f": np.float64("nan"),
            },
        )
        got = json.loads(target.read_text(encoding="utf-8"))
        assert got == {"a": 3, "b": 1.5, "c": [0, 1, 2], "d": "x/y", "e": [1, 2], "f": None}

    def test_write_json_overwrites_in_place(self, tmp_path: Path) -> None:
        p = tmp_path / "m.json"
        write_json(p, {"v": 1})
        write_json(p, {"v": 2})
        assert json.loads(p.read_text(encoding="utf-8")) == {"v": 2}

    def test_unserialisable_objects_raise(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="not JSON serializable"):
            write_json(tmp_path / "m.json", {"x": object()})


class TestDigest:
    def test_digest_is_stable_and_content_dependent(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a", tmp_path / "b"
        a.write_bytes(b"hello")
        b.write_bytes(b"hello")
        assert file_digest(a) == file_digest(b)
        b.write_bytes(b"world")
        assert file_digest(a) != file_digest(b)

    def test_missing_file_gives_none(self, tmp_path: Path) -> None:
        assert file_digest(tmp_path / "absent") is None
