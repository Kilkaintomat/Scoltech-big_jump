"""Content identities, recoverable journals and immutable stage manifests for E1."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def canonical(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode()


def digest(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def write_once(path: str | Path, obj: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(obj) + b"\n"
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable artifact differs: {path}")
        return path
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return path


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Journal:
    """Each row binds its input identity; a torn final line is quarantined, never guessed.

    One writer per journal, enforced by the stage's file lock. Completed rows are never replaced.
    A changed request/source/config must use a new journal. Recovery preserves the torn bytes.
    """

    def __init__(self, path: str | Path, context: dict[str, Any]):
        from filelock import FileLock

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path) + ".lock")
        self.lock.acquire(timeout=0)
        try:
            write_once(self.path.with_suffix(".identity.json"), context)
            self.context = identity(context)
            self.rows: dict[str, dict[str, Any]] = {}
            data = self.path.read_bytes() if self.path.exists() else b""
            lines = data.splitlines(keepends=True)
            accepted = 0
            for i, line in enumerate(lines):
                if not line.endswith(b"\n"):
                    if i != len(lines) - 1:
                        raise ValueError("unterminated interior journal line")
                    quarantine = self.path.with_name(
                        self.path.name + ".torn-" + hashlib.sha256(line).hexdigest()[:16]
                    )
                    if not quarantine.exists():
                        quarantine.write_bytes(line)
                    with self.path.open("r+b") as f:
                        f.truncate(accepted)
                        f.flush()
                        os.fsync(f.fileno())
                    break
                row = json.loads(line)
                row_hash = row.pop("row_sha256")
                if row_hash != identity(row) or row["context_sha256"] != self.context:
                    raise ValueError("corrupt journal row or changed context")
                rid = row["trace_id"]
                if rid in self.rows:
                    raise ValueError(f"duplicate trace id: {rid}")
                self.rows[rid] = row
                accepted += len(line)
        except BaseException:
            self.lock.release()
            raise

    def existing(self, trace_id: str, request_sha256: str) -> dict[str, Any] | None:
        row = self.rows.get(trace_id)
        if row is not None and row["request_sha256"] != request_sha256:
            raise ValueError(f"input changed for resumed trace {trace_id}")
        return row

    def append(self, row: dict[str, Any], request_sha256: str) -> None:
        if row["trace_id"] in self.rows:
            raise ValueError("duplicate journal append")
        saved = {**row, "request_sha256": request_sha256, "context_sha256": self.context}
        encoded = {**saved, "row_sha256": identity(saved)}
        with self.path.open("ab") as f:
            f.write(canonical(encoded) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        self.rows[row["trace_id"]] = saved

    def close(self) -> None:
        self.lock.release()

    def __enter__(self) -> Journal:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def source_identity(root: Path) -> dict[str, Any]:
    """Digest executable inputs, including changes absent from the base commit."""
    files = sorted(
        {
            p
            for folder in ("src", "scripts/e1", "docs/e1", "tests")
            for p in (root / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("._")
        }
    )
    files.extend(root / name for name in ("pyproject.toml", "Makefile") if (root / name).exists())
    return {str(p.relative_to(root)): digest(p) for p in files}


def environment() -> dict[str, Any]:
    packages: dict[str, str | None] = {}
    for name in (
        "torch",
        "transformers",
        "tokenizers",
        "vllm",
        "numpy",
        "scipy",
        "pandas",
        "pyarrow",
    ):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    try:
        gpu = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,uuid,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except OSError:
        gpu = None
    return {
        "packages": packages,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "gpu": gpu,
        "slurm_job_id": os.getenv("SLURM_JOB_ID"),
        "slurm_cpus": os.getenv("SLURM_CPUS_PER_TASK"),
    }


def finish(
    directory: Path,
    *,
    stage: str,
    context: dict[str, Any],
    inputs: list[Path],
    outputs: list[Path],
    metrics: dict[str, Any],
) -> Path:
    for p in inputs:
        verify_manifest(p) if p.name.endswith("manifest.json") else None
    provenance = [read_json(p)["metrics"] for p in inputs if p.name == "source-manifest.json"]
    manifest = {
        "source_control": [
            {key: info[key] for key in ("git_commit", "git_branch", "dirty")} for info in provenance
        ],
        "stage": stage,
        "context": context,
        "environment": environment(),
        "inputs": {str(p.resolve()): digest(p) for p in inputs},
        "outputs": {str(p.resolve()): digest(p) for p in outputs},
        "metrics": metrics,
    }
    return write_once(directory / "manifest.json", manifest)


def verify_manifest(path: Path, seen: set[str] | None = None) -> None:
    seen = set() if seen is None else seen
    key = str(path.resolve())
    if key in seen:
        return
    seen.add(key)
    man = read_json(path)
    for section in ("inputs", "outputs"):
        for name, expected in man[section].items():
            p = Path(name)
            if not p.is_file() or digest(p) != expected:
                raise ValueError(f"manifest digest mismatch: {p}")
            if section == "inputs" and p.name.endswith("manifest.json"):
                verify_manifest(p, seen)
