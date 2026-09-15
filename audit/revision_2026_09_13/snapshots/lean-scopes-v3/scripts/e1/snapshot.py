"""Host Python 3.6 compatible source snapshotter; file operations only, no computation jobs."""

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
run = Path(sys.argv[1]).resolve()
name = sys.argv[2] + "-" + datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
out = run / "snapshots" / name
out.mkdir(parents=True, exist_ok=False)
files = []
for folder in ["src", "scripts", "tests", "docs/e1", "configs"]:
    files.extend(
        p
        for p in (root / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("._")
    )
files.extend(root / x for x in ["pyproject.toml", "Makefile", "AGENTS.md"])
outputs = {}
for p in sorted(set(files)):
    dest = out / p.relative_to(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(p), str(dest))
    outputs[str(dest)] = hashlib.sha256(dest.read_bytes()).hexdigest()
    dest.chmod(0o555 if os.access(str(p), os.X_OK) else 0o444)


def git(*args):
    return subprocess.check_output(["git", *args]).decode("utf-8").strip()


manifest = {
    "stage": "immutable-source-snapshot",
    "inputs": {},
    "outputs": outputs,
    "metrics": {
        "original_root": str(root),
        "git_commit": git("rev-parse", "HEAD"),
        "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_status": git("status", "--porcelain"),
        "dirty": bool(git("status", "--porcelain")),
    },
}
(out / "source-manifest.json").write_text(
    json.dumps(manifest, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
)
(out / "source-manifest.json").chmod(0o444)
for directory in sorted(
    [x for x in out.rglob("*") if x.is_dir()], key=lambda x: len(x.parts), reverse=True
):
    directory.chmod(0o555)
out.chmod(0o555)
print(str(out))
