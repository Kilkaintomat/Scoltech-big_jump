"""Archive the exact installed elan/toolchain for node-local staging, without rebuilding."""
from pathlib import Path
import datetime, hashlib, json, os, tarfile, time
from onebigjump.e1.artifacts import finish
root=Path("/beegfs/home/denis.rakhmankin/onebigjump")
source=Path("/beegfs/home/denis.rakhmankin/.elan")
out=Path("/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/elan-runtime-20260913")
out.mkdir(exist_ok=False)
pin=(root/"lean_workspace/mathlib_project/lean-toolchain").read_text().strip()
name=pin.replace("/","--").replace(":","---")
paths=[source/"settings.toml",source/"bin",source/"toolchains"/name]
entries=[]
for top in paths:
    for p in ([top]+sorted(top.rglob("*")) if top.is_dir() else [top]):
        if p.is_symlink():
            entries.append({"path":str(p.relative_to(source)),"symlink":os.readlink(p)})
        elif p.is_file():
            h=hashlib.sha256()
            with p.open("rb") as f:
                for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
            st=p.stat()
            entries.append({"path":str(p.relative_to(source)),"sha256":h.hexdigest(),"bytes":st.st_size,"mtime_ns":st.st_mtime_ns})
inventory=out/"inventory.json"
inventory.write_text(json.dumps({"toolchain":pin,"source":str(source),"entries":entries},sort_keys=True)+"\n")
archive=out/"elan-runtime.tar"
with tarfile.open(archive,"w") as tar:
    for p in paths:tar.add(p,arcname=str(p.relative_to(source)),recursive=True)
for e in entries:
    p=source/e["path"]
    if "sha256" in e:
        st=p.stat()
        assert st.st_size==e["bytes"] and st.st_mtime_ns==e["mtime_ns"],"source changed while archiving"
h=hashlib.sha256()
with archive.open("rb") as f:
    for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
metrics={"toolchain":pin,"archive_sha256":h.hexdigest(),"archive_bytes":archive.stat().st_size,"files":len(entries),"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"no_compilation_or_version_change":True}
(out/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
manifest=finish(out,stage="lean_toolchain_archive",context={"source":str(source),"slurm_job":os.environ["SLURM_JOB_ID"]},inputs=[Path(__file__),root/"lean_workspace/mathlib_project/lean-toolchain"],outputs=[archive,inventory,out/"metrics.json"],metrics=metrics)
config={"archive":str(archive),"archive_sha256":h.hexdigest(),"manifest":str(manifest),"manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),"toolchain":pin}
(out/"activation.json").write_text(json.dumps(config,indent=2)+"\n")
print(json.dumps(config))
