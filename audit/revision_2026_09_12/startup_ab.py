import concurrent.futures
import json
import os
import time
from pathlib import Path
from onebigjump.lean import LeanREPL, discover
from onebigjump.e1.artifacts import finish, write_once

base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
folder=base/'audit/revision_2026_09_12'/('startup-ab-'+os.environ['SLURM_JOB_ID'])
folder.mkdir()
env=discover(base/'lean_workspace')
def run(i):
    mode='embedded_probe' if i%2 else 'imports_only'
    class Probe(LeanREPL):
        def _exchange(self,payload,timeout_s=None):
            if mode=='embedded_probe' and payload.get('cmd')==self.imports and payload.get('env') is None:
                payload=dict(payload,cmd=payload['cmd']+'\nexample : Nat.Prime 2 := by norm_num\n')
            return super()._exchange(payload,timeout_s)
    repl=Probe(env,imports='import Mathlib\nimport Aesop',startup_attempts=1)
    start=time.monotonic()
    try:
        with repl:
            pass
        status='ok'
    except Exception as exc:
        status=repr(exc)
    row={'index':i,'mode':mode,'status':status,'elapsed_s':time.monotonic()-start,
         'diagnostics':repl.startup_diagnostics,'stderr':list(repl._stderr)}
    write_once(folder/(str(i)+'.json'),row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    records=list(pool.map(run,range(16)))
metrics={mode:{'attempts':sum(r['mode']==mode for r in records),
              'passed':sum(r['mode']==mode and r['status']=='ok' for r in records)} for mode in ('imports_only','embedded_probe')}
path=write_once(folder/'metrics.json',metrics)
finish(folder,stage='lean-startup-ab',context={},inputs=[Path(__file__),Path(os.environ['E1_SNAPSHOT'])/'source-manifest.json'],outputs=[path,*folder.glob('[0-9]*.json')],metrics=metrics)
