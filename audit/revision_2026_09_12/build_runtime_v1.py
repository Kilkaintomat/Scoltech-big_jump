"""Build a separately manifested REPL with the pinned ContextInfo heartbeat repair."""
import os
import shutil
import subprocess
from pathlib import Path
from onebigjump.e1.artifacts import digest, finish, write_once
base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
project=base/'lean_workspace/repl'
folder=base/'runs/repl_runtime_20260912'
folder.mkdir(parents=True,exist_ok=False)
originals={}
for path in sorted(project.rglob('*.lean')):
    if '.lake' not in path.relative_to(project).parts:
        relative=path.relative_to(project)
        target=folder/'source-original'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        originals[str(relative)]=digest(target)
for name in ('lakefile.toml','lean-toolchain','lake-manifest.json'):
    if (project/name).is_file():
        shutil.copy2(project/name,folder/'source-original'/name)
        originals[name]=digest(folder/'source-original'/name)
path=project/'REPL/Snapshots.lean'
s=path.read_text()
old='coreContext := ← readThe Core.Context'
new='coreContext := { (← readThe Core.Context) with\n        maxHeartbeats := Core.getMaxHeartbeats ctx.options }'
if s.count(old)!=1:
    raise RuntimeError('pinned REPL source no longer matches the reviewed patch')
path.write_text(s.replace(old,new))
shutil.copy2(path,folder/'Snapshots.lean')
config={'base_repl_revision':'5d5c49d13dfc0c1d2df43a27c3e56e02ad81b9c3','repair':'ProofSnapshot.create derives active Core.Context.maxHeartbeats from ContextInfo.options','lean_version':subprocess.check_output(['lean','--version'],cwd=project,text=True).strip(),'original_source_sha256':originals,'build_command':['lake','build','repl'],'slurm_job_id':os.environ['SLURM_JOB_ID']}
config_path=write_once(folder/'config.json',config)
subprocess.run(['lake','build','repl'],cwd=project,check=True)
shutil.copy2(project/'.lake/build/bin/repl',folder/'repl')
(folder/'repl').chmod(0o555)
source=Path(os.environ['E1_SNAPSHOT'])/'source-manifest.json'
finish(folder,stage='lean-repl-runtime-build',context={'source':digest(source)},inputs=[source,Path(__file__),Path('/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/lean-runtime.tar.sha256')],outputs=[folder/'repl',folder/'Snapshots.lean',config_path,*sorted((folder/'source-original').rglob('*.lean')),*[folder/'source-original'/n for n in ('lakefile.toml','lean-toolchain','lake-manifest.json') if (folder/'source-original'/n).is_file()]],metrics=config)
print('Repaired runtime:',folder,flush=True)
