"""Host-only file management; freeze every code/config/document file by digest."""
import datetime, hashlib, json, shutil, subprocess, sys
from pathlib import Path
base=Path.cwd()
source=base/"audit/revision_2026_09_13/snapshots"/sys.argv[1]
source.mkdir(parents=True,exist_ok=False)
paths=[]
for folder in ("src","scripts","tests","configs","docs"):
    paths += [p for p in (base/folder).rglob("*") if p.is_file() and not p.name.startswith("._") and "__pycache__" not in p.parts and p.suffix not in (".pyc",".pyo")]
paths += [base/p for p in ("pyproject.toml","Makefile","AGENTS.md")]
for p in paths:
    target=source/p.relative_to(base)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(str(p),str(target))
manifest={"inputs":{},"outputs":{str(source/p.relative_to(base)):hashlib.sha256((source/p.relative_to(base)).read_bytes()).hexdigest() for p in paths},"metrics":{
    "git_commit":subprocess.check_output(["git","rev-parse","HEAD"]).decode().strip(),
    "git_branch":subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"]).decode().strip(),
    "dirty":bool(subprocess.check_output(["git","status","--porcelain"])),
    "created_utc":datetime.datetime.utcnow().isoformat()+"Z"}}
(source/"source-manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n",encoding="utf-8")
for p in source.rglob("*"):
    if p.is_file():p.chmod(p.stat().st_mode & ~0o222)
for name in ('lean_workspace', 'data', 'results', '.git'):
    (source/name).symlink_to(base/name,target_is_directory=True)
print(source)
