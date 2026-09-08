"""Run manifests: every artifact in this repository says how it was made.

No number in `paper_outputs/` is hand-entered. Each run writes a manifest next to its outputs
recording the resolved config, the git commit and whether the tree was dirty, the package
versions, the hardware, the wall time, and a digest of every file it produced. A figure whose
manifest says `dirty: true` is a figure that cannot be reproduced, and the reporting layer says
so rather than quietly shipping it.
"""

from __future__ import annotations

import contextlib
import platform
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .reproducibility import (
    file_digest,
    git_info,
    hardware_info,
    package_versions,
    write_json,
)

__all__ = ["RunManifest", "run_manifest"]

MANIFEST_NAME = "manifest.json"


@dataclass
class RunManifest:
    """Provenance of one run, written to `<out_dir>/manifest.json`."""

    name: str
    kind: str
    out_dir: Path
    config: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    status: str = "running"
    error: str | None = None
    outputs: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)

    def add_output(self, path: Path | str, role: str = "") -> Path:
        """Register a produced file, with its size and digest."""
        p = Path(path)
        self.outputs.append(
            {
                "path": str(p),
                "role": role,
                "bytes": p.stat().st_size if p.is_file() else None,
                "digest": file_digest(p),
            }
        )
        return p

    def add_metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value

    def note(self, text: str) -> None:
        """Record a deviation from the paper's protocol, so it cannot go unreported."""
        self.notes.append(text)

    @property
    def reproducible(self) -> bool:
        """False when the run was made from a dirty working tree, or from no checkout at all.

        `dirty` is None when git could not be asked -- an rsynced tree with no `.git`, which is how
        the cluster runs were made. That is not a clean checkout, it is an unknown one, and the
        figure it produced cannot be traced back to a commit either way.
        """
        return self.environment.get("git", {}).get("dirty", True) is False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "out_dir": str(self.out_dir),
            "seed": self.seed,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "reproducible": self.reproducible,
            "config": self.config,
            "metrics": self.metrics,
            "notes": self.notes,
            "outputs": self.outputs,
            "environment": self.environment,
        }

    def write(self) -> Path:
        return write_json(self.out_dir / MANIFEST_NAME, self.as_dict())


@contextlib.contextmanager
def run_manifest(
    name: str,
    kind: str,
    out_dir: Path | str,
    config: dict[str, Any] | None = None,
    seed: int | None = None,
    repo: Path | None = None,
) -> Iterator[RunManifest]:
    """Create `out_dir`, capture the environment, and write the manifest on the way out.

    The manifest is written whether the body succeeds or raises, because a failed run is also
    something to be able to reconstruct.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    man = RunManifest(
        name=name,
        kind=kind,
        out_dir=out,
        config=dict(config or {}),
        seed=seed,
        started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        environment={
            "git": git_info(repo or Path.cwd()),
            "packages": package_versions(),
            "hardware": hardware_info(),
            "python_build": platform.python_build(),
        },
    )
    try:
        yield man
        man.status = "ok"
    except BaseException as exc:
        man.status = "failed"
        man.error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        man.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        man.duration_s = round(time.time() - started, 3)
        man.write()
