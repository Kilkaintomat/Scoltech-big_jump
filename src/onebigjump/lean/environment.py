"""Locate and describe the Lean toolchain, the Mathlib project and the REPL.

Everything lives under `lean_workspace/`, installed in user space by `scripts/setup_lean.sh`.
Nothing here installs anything: it reports what is present, so that a run either starts against a
known toolchain or refuses with a message that says which piece is missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["LeanEnvironment", "LeanNotAvailable", "discover"]

DEFAULT_WORKSPACE = Path("lean_workspace")
PROJECT_DIR = "mathlib_project"
REPL_DIR = "repl"


class LeanNotAvailable(RuntimeError):
    """Raised when a Lean-dependent operation is attempted without a usable toolchain."""


@dataclass
class LeanEnvironment:
    """A resolved Lean toolchain: where everything is, and whether it is usable."""

    workspace: Path
    project: Path | None = None
    repl_binary: Path | None = None
    toolchain: str | None = None
    lake: str | None = None
    lean: str | None = None
    mathlib_rev: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return not self.problems

    def require(self) -> LeanEnvironment:
        """Return self, or raise with everything that is missing at once."""
        if self.problems:
            raise LeanNotAvailable(
                "Lean is not usable:\n  - "
                + "\n  - ".join(self.problems)
                + "\nRun scripts/setup_lean.sh to install it in user space."
            )
        return self

    def env_vars(self) -> dict[str, str]:
        """Environment for a subprocess, with elan's bin directory on the path."""
        env = dict(os.environ)
        elan_home = env.get("ELAN_HOME") or str(Path.home() / ".elan")
        env["ELAN_HOME"] = elan_home
        env["PATH"] = f"{Path(elan_home) / 'bin'}{os.pathsep}{env.get('PATH', '')}"
        return env

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace),
            "project": str(self.project) if self.project else None,
            "repl_binary": str(self.repl_binary) if self.repl_binary else None,
            "toolchain": self.toolchain,
            "mathlib_rev": self.mathlib_rev,
            "lake": self.lake,
            "lean": self.lean,
            "available": self.available,
            "problems": self.problems,
        }


def _which(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    candidate = Path.home() / ".elan" / "bin" / name
    return str(candidate) if candidate.is_file() else None


def _git_rev(path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def discover(workspace: Path | str = DEFAULT_WORKSPACE) -> LeanEnvironment:
    """Find the toolchain and report, item by item, what is missing."""
    ws = Path(workspace)
    env = LeanEnvironment(workspace=ws)

    env.lake = _which("lake")
    env.lean = _which("lean")
    if env.lake is None:
        env.problems.append("`lake` not found (elan is not installed or not on PATH)")

    project = ws / PROJECT_DIR
    if (project / "lakefile.toml").is_file() or (project / "lakefile.lean").is_file():
        env.project = project
        tc = project / "lean-toolchain"
        if tc.is_file():
            env.toolchain = tc.read_text(encoding="utf-8").strip()
        mathlib = project / ".lake" / "packages" / "mathlib"
        if mathlib.is_dir():
            env.mathlib_rev = _git_rev(mathlib)
            built = list((mathlib / ".lake" / "build" / "lib").rglob("Mathlib.olean"))
            if not built:
                env.problems.append(
                    "Mathlib is present but not built (`lake exe cache get && lake build`)"
                )
        else:
            env.problems.append(f"Mathlib not fetched under {project}")
    else:
        env.problems.append(f"no Lean project at {project}")

    for candidate in (
        ws / REPL_DIR / ".lake" / "build" / "bin" / "repl",
        ws / REPL_DIR / "build" / "bin" / "repl",
    ):
        if candidate.is_file():
            env.repl_binary = candidate
            break
    else:
        env.problems.append(f"the Lean REPL is not built under {ws / REPL_DIR}")

    return env
