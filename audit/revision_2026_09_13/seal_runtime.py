"""Seal the reviewed scoped runtime independently of mutable build scripts."""
from pathlib import Path
import os,shutil
from onebigjump.e1.artifacts import digest,finish,read_json,verify_manifest,write_once
base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
original=base/'runs/repl_runtime_20260913_scopes'
record=read_json(original/'manifest.json')
verify_manifest(original/'manifest.json')
folder=base/'runs/repl_runtime_20260913_sealed';folder.mkdir(exist_ok=False)
for filename in record['outputs']:
    p=Path(filename);shutil.copy2(p,folder/p.name)
builder=folder/'build_scoped_repl.py'
shutil.copy2(base/'scripts/e1/build_scoped_repl.py',builder)
assert digest(builder)==record['inputs'][str(base/'scripts/e1/build_scoped_repl.py')]
write_once(folder/'build-record.json',record)
source=Path(os.environ['E1_SNAPSHOT'])/'source-manifest.json'
manifest=finish(folder,stage='seal-scoped-runtime',context={'source':digest(source)},
 inputs=[source,builder,Path(__file__),base/'runs/repl_runtime_20260912_sealed/manifest.json'],
 outputs=[p for p in folder.iterdir() if p.is_file()],
 metrics={'build_job':record['environment']['slurm_job_id'],'build_environment':record['environment'],'build_config':record['metrics'],'original_manifest_sha256':digest(original/'manifest.json')})
pin=write_once(folder/'pin/runtime.json',{'manifest':str(manifest),'manifest_sha256':digest(manifest),'binary':str(folder/'repl'),'binary_sha256':digest(folder/'repl')})
finish(folder/'pin',stage='pin-scoped-runtime',context={},inputs=[manifest],outputs=[pin],metrics={})
shutil.copy2(pin,base/'configs/repl_runtime.json')
for p in folder.rglob('*'):
    if p.is_file():p.chmod(p.stat().st_mode & ~0o222)
print(pin.read_text(),flush=True)
