from pathlib import Path
import hashlib,json,subprocess,datetime,os
root=Path(os.environ["E1_SNAPSHOT"])
previous=Path("audit/revision_2026_09_13/snapshots/statistical-fitness-v1/source-manifest.json").resolve()
out={}
for directory in ["src","tests","scripts","configs","docs"]:
 for p in (root/directory).rglob("*"):
  if p.is_file() and "__pycache__" not in str(p) and p.suffix != ".pyc":
   out[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
for p in root.iterdir():
 if p.is_file() and not p.is_symlink() and p.name != "source-manifest.json":
  out[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads(previous.read_text())
manifest={"inputs":{str(previous):hashlib.sha256(previous.read_bytes()).hexdigest()},"outputs":out,
 "metrics":{**old["metrics"],"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"amendment":"lean-saved-repair-v8","dirty":True}}
(root/"source-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
for name in out:Path(name).chmod(0o444)
print("FROZEN",root,flush=True)
