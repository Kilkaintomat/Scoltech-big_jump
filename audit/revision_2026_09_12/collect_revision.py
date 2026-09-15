"""Host file/job management only: immutable status inputs for the Slurm report renderer."""
import datetime
import json
import shutil
import subprocess
from pathlib import Path

base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
audit=base/'audit/revision_2026_09_12'
root=base/'runs/lean_reverification_20260912'
stamp=datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
folder=audit/'reports'/stamp
(folder/'inputs').mkdir(parents=True)
queue=json.loads((root/'queue.json').read_text(encoding='utf-8'))
for name in ('queue.json','submission.json','recovery.json'):
    shutil.copy2(str(root/name),str(folder/'inputs'/name))
ids=sorted({t['job_id'] for t in queue['tasks'].values() if t.get('job_id')} | {'8465485','8465496','8465446','8465447','8465448','8465449','8465450','8465476','8465478'})
accounting=subprocess.check_output(['sacct','-X','-n','-j',','.join(ids),'--format=JobID,State,ExitCode,Elapsed,NodeList','-P']).decode()
active=subprocess.check_output(['squeue','-h','-u','denis.rakhmankin','-o','%i|%j|%T|%M|%R']).decode()
(folder/'inputs/accounting.txt').write_text(accounting,encoding='utf-8')
(folder/'inputs/active.txt').write_text(active,encoding='utf-8')
for phase in ('fast','full'):
    path=audit/(phase+'-'+queue['tasks']['validation']['job_id']+'.xml')
    if path.exists():shutil.copy2(str(path),str(folder/'inputs'/path.name))
config={'cutoff_utc':datetime.datetime.utcnow().isoformat()+'Z','source':queue['source'],'campaign':str(root),
        'previous_campaign':str(base/'runs/lean_recovery_20260911_v3'),'validation':queue['tasks']['validation']['job_id'],
        'regression':queue['tasks']['regression']['job_id'],'runtime_identity':queue['tasks']['runtime_identity']['job_id'],
        'p3_summary':str(base/'runs/p3_diagnosis_20260912/summary/manifest.json'),
        'historical_p3':str(audit/'historical-p3/manifest.json'),
        'runtime_manifest':str(base/'runs/repl_runtime_20260912_sealed/manifest.json'),
        'generation_manifests':{name:[str(p) for p in sorted((root/name/'main/generation').glob('shard-*/manifest.json'))] for name in ('deepseek','goedel','kimina')}}
(folder/'inputs/config.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
for model in ('deepseek','goedel','kimina'):
    task=queue['tasks'][model+'/pilot-verify']
    if task.get('job_id'):
        logfile=root/'logs'/(task['job_name']+'-'+task['job_id']+'.log')
        if logfile.exists():shutil.copy2(str(logfile),str(folder/'inputs'/(model+'-pilot-verify.log')))
shutil.copy2(str(audit/'render_revision.py'),str(folder/'inputs/render_revision.py'))
print(folder)
