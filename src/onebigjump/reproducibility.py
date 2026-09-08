"""Seeding, environment capture and atomic writes."""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
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
    "numpy",
    "scipy",
    "pandas",
    "pyarrow",
    "pydantic",
    "scikit-learn",
    "statsmodels",
    "matplotlib",
    "torch",
    "transformers",
    "tokenizers",
    "accelerate",
    "datasets",
)


def seed_everything(seed: int, deterministic: bool = True) -> int:
    """Seed python/numpy/torch. Returns the seed for logging."""
    random.seed(seed)
    # Legacy global seeding on purpose: third-party code still draws from np.random.*.
    # Project code uses `rng(seed)` below, which returns an explicit Generator.
    np.random.seed(seed % (2**32 - 1))  # noqa: NPY002
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


#: Environment variables a launcher can set when the run happens somewhere `git` does not exist.
GIT_ENV_VARS = {
    "commit": "ONEBIGJUMP_GIT_COMMIT",
    "branch": "ONEBIGJUMP_GIT_BRANCH",
    "describe": "ONEBIGJUMP_GIT_DESCRIBE",
    "status": "ONEBIGJUMP_GIT_STATUS",
    "remote": "ONEBIGJUMP_GIT_REMOTE",
}


def _git_from_environment(repo: Path | None = None) -> dict[str, Any] | None:
    """Provenance handed in by the launcher, for runs inside a container without `git`.

    The Singularity image the cluster runs has no `git` binary, so a run inside it cannot read its
    own commit however good the checkout outside is. `scripts/slurm/common.sh` reads it on the host
    and exports it. This is weaker evidence than asking git directly -- an environment variable can
    say anything -- so it is labelled `source: environment` rather than passed off as the real
    thing.
    """
    if repo is not None:
        declared_root = os.environ.get("ONEBIGJUMP_GIT_ROOT")
        if not declared_root or Path(declared_root).resolve() != repo.resolve():
            return None
    commit = os.environ.get(GIT_ENV_VARS["commit"], "").strip()
    if not commit:
        return None
    status = os.environ.get(GIT_ENV_VARS["status"])
    return {
        "commit": commit,
        "branch": os.environ.get(GIT_ENV_VARS["branch"]) or None,
        "describe": os.environ.get(GIT_ENV_VARS["describe"]) or None,
        "dirty": bool(status.strip()) if status is not None else None,
        "status": (status or "")[:8000],
        "remote": os.environ.get(GIT_ENV_VARS["remote"]) or None,
        "available": True,
        "source": "environment",
    }


def git_info(repo: Path | None = None) -> dict[str, Any]:
    cwd = str(repo or Path.cwd())

    def g(args: list[str]) -> str | None:
        return _run(["git", "-C", cwd, *args])

    commit = g(["rev-parse", "HEAD"])
    status = g(["status", "--porcelain"])
    # `status` is None both for a clean tree that git could not be asked about and for no repo at
    # all, and `bool(None)` is False -- so a run whose provenance is entirely unknown used to be
    # stamped `dirty: false`, i.e. reproducible. That is the one error worth being loud about: the
    # cluster runs are made from an rsynced tree with no .git, and their manifests claimed a clean
    # checkout. When there is no commit there is no answer, so `dirty` is None, not False.
    if commit is None and (from_env := _git_from_environment(Path(cwd))) is not None:
        return from_env
    available = commit is not None
    return {
        "source": "git" if available else "unavailable",
        "commit": commit,
        "branch": g(["rev-parse", "--abbrev-ref", "HEAD"]),
        "describe": g(["describe", "--always", "--dirty"]),
        "dirty": bool(status) if available and status is not None else None,
        "status": (status or "")[:8000],
        "remote": g(["config", "--get", "remote.origin.url"]),
        "available": available,
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
        info["mps_available"] = bool(
            getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
        )
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
    """Write `obj` as strict, standards-conformant JSON, atomically.

    NaN and infinity are written as `null`. They occur legitimately -- the moment estimator
    returns NaN where its denominator vanishes, and a bootstrap interval is NaN when too few
    resamples survive -- but `json.dumps` would emit the bare tokens `NaN` and `Infinity`,
    which are not JSON and which every strict reader rejects.
    """
    with atomic_path(Path(target)) as tmp:
        payload = json.dumps(_sanitize(obj), indent=indent, default=_json_default, allow_nan=False)
        tmp.write_text(payload, encoding="utf-8")
    return Path(target)


def _sanitize(obj: Any) -> Any:
    """Recursively replace non-finite floats with None.

    `numpy.float64` subclasses `float`, so `json.dumps` serialises it directly and never
    consults the `default` hook; the replacement therefore has to happen before the dump.
    """
    if isinstance(obj, float):  # covers numpy.float64
        return None if not math.isfinite(obj) else float(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if not math.isfinite(v) else v
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return _sanitize(obj.tolist())
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, set):
        return [_sanitize(v) for v in sorted(obj)]
    if hasattr(obj, "as_dict"):
        return _sanitize(obj.as_dict())
    if hasattr(obj, "model_dump"):
        return _sanitize(obj.model_dump(mode="json"))
    return obj


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
