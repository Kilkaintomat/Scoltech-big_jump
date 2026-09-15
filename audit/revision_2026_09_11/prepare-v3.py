"""File/job bookkeeping: reuse completed v2 pilot acquisition and freeze new analysis lineage."""
import copy
import importlib.util
import json
from pathlib import Path

base = Path('/beegfs/home/denis.rakhmankin/onebigjump')
audit = base/'audit/revision_2026_09_11'
source = Path((audit/'snapshot-path.txt').read_text().strip())
old = base/'runs/lean_recovery_20260911_v2'
target = base/'runs/lean_recovery_20260911_v3'
storage = Path('/gpfs/gpfs0/denis.rakhmankin/onebigjump-runs/lean_recovery_20260911_v3').resolve()
previous = json.loads((old/'queue.json').read_text())
# No sample is selected or dropped; retain all stopped startup artefacts in v2.
assert not list(old.glob('*/main/generation/*/samples.jsonl'))
spec = importlib.util.spec_from_file_location('recover', str(source/'scripts/campaign/recover.py'))
recover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recover)
recover.prepare(base/'runs/lean_all_20260909',target,storage,source,'8464459')
q=json.loads((target/'queue.json').read_text())
q['tasks']['validation_all'] = {
    'model':None,'job_id':(audit/'validation-job.txt').read_text().strip(),
    'state':'PENDING','dependencies':[],'partition':'ais-htc','external':True,
}
q['tasks']['parser_validation'] = copy.deepcopy(previous['tasks']['parser_validation'])
for model in ('deepseek','goedel','kimina'):
    for stage in ('verification','extraction','measurement'):
        link=target/model/'pilot'/stage
        link.unlink()
        link.symlink_to((old/model/'pilot'/stage).resolve(),target_is_directory=True)
    for path in (old/model/'checks').glob('lean-smoke-*'):
        (target/model/'checks'/path.name).symlink_to(path.resolve(),target_is_directory=True)
    for stage in ('smoke','verify','extract','measure'):
        key=model+'/pilot-'+stage
        assert previous['tasks'][key]['state']=='COMPLETED'
        q['tasks'][key].update(job_id=previous['tasks'][key]['job_id'],state='COMPLETED',external=True,
                               reused_from=str(old),original_source=previous['source'])
    q['tasks'][model+'/pilot-analyze']['dependencies'].append('validation')
for key,t in q['tasks'].items():
    if t.get('stage')=='gate': t['dependencies'].append('validation_all')
    if not t.get('external'): t['job_name']='obj0911v3-'+key.replace('/','-')
q['tasks']['audit/pilot-report'] = {
    'model':None,'stage':'audit-report','partition':'ais-htc','hours':1,
    'dependencies':[k for k,t in q['tasks'].items() if t.get('stage')=='gate'],
    'script':str(audit/'report.sbatch'),'arguments':[],
    'job_name':'obj0911v3-audit-pilot-report','state':'WAITING','job_id':None,
}
q['analysis_revision_of']=str(old)
(target/'queue.json').write_text(json.dumps(q,indent=2)+'\n')
receipt=json.loads((target/'recovery.json').read_text())
receipt.update(pilot_acquisition_reused_from=str(old),analysis_recomputed=True,
               stopped_startup_jobs=['8464445','8464446','8464453','8464454'],
               main_samples_present_before_restart=False)
(target/'recovery.json').write_text(json.dumps(receipt,indent=2)+'\n')
# Archive the predecessor as an explicitly superseded, stopped controller graph.
for name,t in previous['tasks'].items():
    if t.get('stage')=='generate' and t.get('job_id'): t['state']='CANCELLED'
previous['superseded_by']=str(target)
previous['controller_status']='STOPPED_FOR_STATISTICAL_FIX'
(old/'queue.json').write_text(json.dumps(previous,indent=2)+'\n')
print(target)
