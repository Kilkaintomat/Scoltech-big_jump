"""Seeding, environment capture and atomic writes."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np

TRACKED_PACKAGES = (
    "numpy", "scipy", "pandas", "pyarrow", "pydantic", "scikit-learn", "statsmodels",
    "matplotlib", "torch", "transformers", "tokenizers", "accelerate", "datasets",
)


def seed_everything(seed: int, deterministic: bool = True) -> int:
    """Seed python/numpy/torch. Returns the seed for logging."""
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:
        pass
    return seed


def rng(seed: int) -> np.random.Generator:
    """Preferred RNG: an explicit, independent generator."""
    return np.random.default_rng(seed)


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def git_info(repo: Path | None = None) -> dict[str, Any]:
    cwd = str(repo or Path.cwd())

    def g(args: list[str]) -> str | None:
        return _run(["git", "-C", cwd, *args])

    status = g(["status", "--porcelain"])
    return {
        "commit": g(["rev-parse", "HEAD"]),
        "branch": g(["rev-parse", "--abbrev-ref", "HEAD"]),
        "describe": g(["describe", "--always", "--dirty"]),
        "dirty": bool(status),
        "status": (status or "")[:8000],
        "remote": g(["config", "--get", "remote.origin.url"]),
    }


def package_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in TRACKED_PACKAGES:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            continue
    return out


def hardware_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
    }
    try:
        import psutil

        info["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 2)
    except ImportError:
        pass
    try:
        import torch

        info["torch"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        info["cuda_version"] = torch.version.cuda
        info["mps_available"] = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        if torch.cuda.is_available():
            info["gpus"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        else:
            info["gpus"] = []
    except ImportError:
        info["torch"] = None
    return info


def file_digest(path: Path, algo: str = "sha256", max_bytes: int = 1 << 30) -> str | None:
    path = Path(path)
    if not path.is_file():
        return None
    h = hashlib.new(algo)
    read = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            read += len(chunk)
            if read > max_bytes:
                return f"{algo}:partial:{h.hexdigest()}"
    return f"{algo}:{h.hexdigest()}"


@contextlib.contextmanager
def atomic_path(target: Path, suffix: str = "") -> Iterator[Path]:
    """Yield a temp path in the same directory; rename onto `target` on success."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=suffix or target.suffix + ".tmp")
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        yield tmp_path
        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def write_json(target: Path, obj: Any, indent: int = 2) -> Path:
    with atomic_path(Path(target)) as tmp:
        tmp.write_text(json.dumps(obj, indent=indent, default=_json_default), encoding="utf-8")
    return Path(target)


def _json_default(o: Any) -> Any:
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, set):
        return sorted(o)
    if hasattr(o, "model_dump"):
        return o.model_dump()
    raise TypeError(f"not JSON serializable: {type(o)}")
