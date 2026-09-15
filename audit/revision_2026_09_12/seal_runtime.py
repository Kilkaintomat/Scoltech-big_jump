"""Seal a completed build with immutable copies of all inputs used to build its binary."""
import os
import shutil
from pathlib import Path
from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once

base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
original=base/'runs/repl_runtime_20260912_v2'
manifest=original/'manifest.json'
verify_manifest(manifest)
record=read_json(manifest)
folder=base/'runs/repl_runtime_20260912_sealed'
folder.mkdir(exist_ok=False)
for filename in record['outputs']:
    path=Path(filename)
    target=folder/path.relative_to(original)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,target)
build_record=write_once(folder/'build-record.json',record)
builder=folder/'build_repl_runtime.py'
shutil.copy2(base/'scripts/e1/build_repl_runtime.py',builder)
assert digest(builder)==record['inputs'][str(base/'scripts/e1/build_repl_runtime.py')]
source=Path(os.environ['E1_SNAPSHOT'])/'source-manifest.json'
archive=Path('/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/lean-runtime.tar.sha256')
new=finish(folder,stage='seal-lean-runtime-provenance',context={'source':digest(source)},
    inputs=[source,builder,archive,Path(__file__)],outputs=[p for p in folder.rglob('*') if p.is_file()],
    metrics={'original_build_job_id':record['environment']['slurm_job_id'],
             'build_environment':record['environment'],'build_config':record['metrics'],
             'original_build_manifest_sha256':digest(manifest),'seal_only_no_rebuild':True})
pin=write_once(folder/'pin/runtime.json',{'manifest':str(new),'manifest_sha256':digest(new),
    'binary':str(folder/'repl'),'binary_sha256':digest(folder/'repl')})
finish(folder/'pin',stage='pin-reviewed-lean-runtime',context={},inputs=[new],outputs=[pin],metrics={})
shutil.copy2(pin,base/'configs/repl_runtime.json')
for p in folder.rglob('*'):
    if p.is_file():p.chmod(p.stat().st_mode & ~0o222)
print(pin.read_text(),flush=True)
