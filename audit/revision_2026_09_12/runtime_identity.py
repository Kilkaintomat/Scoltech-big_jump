import os
from pathlib import Path
from onebigjump.e1.artifacts import digest, finish, read_json, write_once
from onebigjump.e1.stages import lean_fingerprint
from onebigjump.lean import discover
base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
source=Path(os.environ['E1_SNAPSHOT'])/'source-manifest.json'
config=base/'runs/lean_recovery_20260911_v3/deepseek/main/protocol.json'
settings=read_json(config)['lean']
assert not os.environ.get('E1_LOCAL_LEAN'), 'this test checks the unstaged analysis/extraction environment'
env=discover(settings['workspace'])
assert env.repl_binary==Path(os.environ['ONEBIGJUMP_REPL_BINARY'])
pin=read_json(source.parent/'configs/repl_runtime.json')
identity=lean_fingerprint(settings)
assert identity['repl_binary_sha256']==pin['binary_sha256']
assert identity['repl_local_patch_manifest_sha256']==pin['manifest_sha256']
folder=base/'audit/revision_2026_09_12'/('runtime-identity-'+os.environ['SLURM_JOB_ID'])
path=write_once(folder/'metrics.json',{'passed':True,'executes_lean':False,'fingerprint':identity})
finish(folder,stage='unstaged-runtime-identity-check',context={'source':digest(source)},inputs=[source,config,Path(pin['manifest']),Path(__file__)],outputs=[path],metrics={'passed':True})
print('Unstaged runtime identity matches the pinned binary.',flush=True)
