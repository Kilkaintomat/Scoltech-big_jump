"""Saved-proof regression plus two simultaneous REPL sessions and owned-process cleanup."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os,threading,time
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,verify_manifest
from onebigjump.e1.stages import rows
from onebigjump.e1.verification import verify_one
from onebigjump.lean import LeanREPL,discover
from onebigjump.lean.verifier import _errors
base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
source=Path(os.environ['E1_SNAPSHOT'])/'source-manifest.json'
runtime=Path(os.environ['E1_REPL_RUNTIME_MANIFEST'])
elan_runtime=Path(os.environ['E1_ELAN_RUNTIME_MANIFEST'])
assert os.stat(os.environ['ELAN_HOME']).st_dev == os.stat(os.environ['E1_LOCAL_ELAN']).st_dev
assert os.stat(os.environ['ELAN_HOME']).st_dev != os.stat(base).st_dev
root=base/'runs/lean_reverification_20260912/goedel'
protocol=root/'main/protocol.json';settings=read_json(protocol)['lean']
problems_path=root/'inputs/problems.json'
problems={p['problem_id']:p for p in read_json(problems_path)}
manifest=root/'main/generation/shard-002-of-008/manifest.json'
verify_manifest(manifest)
wanted={'main:aime_1990_p15:T0.6:a06','main:aime_1990_p15:T1.0:a01',
'main:imo_1964_p2:T1.0:a04','main:mathd_numbertheory_495:T0.6:a05',
'main:mathd_algebra_107:T1.0:a05','main:mathd_algebra_31:T0.6:a04'}
samples=[r for r in rows(manifest.parent/'samples.jsonl') if r['trace_id'] in wanted]
assert len(samples)==len(wanted)
def files():
 return [int(x) for x in Path('/proc/sys/fs/file-nr').read_text().split()]
def group_members(pgid):
 result=[]
 for path in Path('/proc').glob('[0-9]*/stat'):
  try:
   fields=path.read_text().rsplit(')',1)[1].split()
   if int(fields[2])==pgid and fields[0]!='Z':result.append(int(path.parent.name))
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 return result
before=files(); barrier=threading.Barrier(2)
def worker(index):
 records=[];counters=[]
 with LeanREPL(discover(settings['workspace']),imports='import Mathlib\nimport Aesop',
               startup_timeout_s=settings['startup_timeout_s']) as repl:
  pgid=repl._proc.pid
  barrier.wait(timeout=600)
  counters.append({'phase':'both-started','files':files()})
  for sample in samples[index::2]:
   result=verify_one(repl,sample,problems[sample['problem_id']],settings)
   if result['category']=='localized_tactic_failure':
    # Independently validate the first failing segment with whole-command prefixes.
    p=problems[sample['problem_id']]
    header=f"set_option maxHeartbeats {settings['max_heartbeats']}\n{p['directives']}\n{p['statement']}"
    prefix_checks=[]
    for count in [result['t_star'],result['t_star']+1]:
     prefix='\n'.join('  '+s['tactic'].replace('\n','\n  ') for s in result['steps'][:count])
     reply=repl.command(header+'\n'+prefix+'\n  all_goals sorry',timeout_s=settings['whole_timeout_s'])
     prefix_checks.append({'segments':count,'errors':_errors(reply)})
    result['independent_prefix_checks']=prefix_checks
   records.append(result)
   print(index,result['trace_id'],result['category'],flush=True)
  counters.append({'phase':'before-close','files':files()})
 deadline=time.monotonic()+5
 remaining=group_members(pgid)
 while remaining and time.monotonic()<deadline:
  time.sleep(0.05);remaining=group_members(pgid)
 counters.append({'phase':'after-close','files':files()})
 return {'worker':index,'results':records,'owned_pgid':pgid,'remaining_processes':remaining,'counters':counters}
with ThreadPoolExecutor(max_workers=2) as pool:
 workers=list(pool.map(worker,range(2)))
all_results=[r for w in workers for r in w['results']]
metrics={'sessions':len(workers),'cases':len(all_results),'before_file_nr':before,'after_file_nr':files(),
 'cases_summary':[{k:r[k] for k in ['trace_id','category','whole_proof_ok','replay_ok','t_star','unexplained_disagreement']} for r in all_results],
 'resources':[{k:v for k,v in w.items() if k!='results'} for w in workers],
 'passed':all(not r['unexplained_disagreement'] and (r['category'] in ['verified','timeout_resource'] or (r['category']=='localized_tactic_failure' and not r['independent_prefix_checks'][0]['errors'] and bool(r['independent_prefix_checks'][1]['errors']))) for r in all_results) and all(not w['remaining_processes'] for w in workers),
 'original_generations_unchanged':True}
new=next(r for r in all_results if 'mathd_algebra_31:' in r['trace_id'])
metrics['passed']=metrics['passed'] and new['category']=='verified'
out=base/'audit/revision_2026_09_13'/(str(os.environ['SLURM_JOB_ID'])+'-preflight')
a=write_once(out/'metrics.json',metrics);b=write_once(out/'results-server-only.json',all_results)
finish(out,stage='scoped-saved-proofs-two-session-preflight',context={'source':digest(source)},
 inputs=[source,runtime,elan_runtime,Path(__file__),protocol,problems_path,manifest],outputs=[a,b],metrics=metrics)
if not metrics['passed']:raise RuntimeError('preflight failed')
print('PREFLIGHT_PASSED',out,flush=True)
