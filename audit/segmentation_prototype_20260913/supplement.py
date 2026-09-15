from pathlib import Path
import json,datetime,os
from segmenter_final import Segmenter,replay_status,errors
from onebigjump.lean import LeanREPL,discover
O=Path(__file__).parent;B=O.parents[1];D=O/'validation_supplement';D.mkdir(exist_ok=True)
assert replay_status({'message':'Lean error:\nfailed'})=='error'
assert replay_status({'message':'Unknown environment.'})=='infrastructure_error'
assert replay_status({'proofState':0,'goals':[],'proofStatus':'Error: kernel rejected'})=='snapshot_kernel_rejection'
assert replay_status({'message':'Lean error: maximum number of heartbeats exceeded'})=='resource_error'
assert replay_status({})=='unknown_reply'
assert replay_status({'proofState':0,'goals':[],'proofStatus':'Completed'})=='ok'
cs=json.loads((O/'curated.json').read_text(encoding='utf-8'))
cases=[dict(c,group='curated') for c in cs if c['name'] in ['cases','nested_failure']]
p=B/'audit/p1_report_20260913T1950Z/examples/kimina_sequence/label.json'
r=json.loads(p.read_text(encoding='utf-8'))
cases.append(dict(name='kimina_sequence',group='illustrative',header=r['replay']['header'],body=r.get('replay_body',r['body']),expected_ok=False,old_L=len(r['steps']),old_t_star=r['t_star']))
summary=[]
with LeanREPL(discover(),imports='import Mathlib\nimport Aesop',startup_attempts=1) as repl:
 s=Segmenter(repl)
 for c in cases:
  r=s.inspect(c['header'],c['body']);r['case']=c
  s.replay_frontier(r)
  assert r['parse_ok']
  assert r['whole_elaboration_ok']==c['expected_ok']
  if c['name'] in ['nested_failure','kimina_sequence']:
   assert r['failure_reproduced']
   assert r['prefix_reproduced']
  (D/(c['name']+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
  summary.append(dict(name=c['name'],blocks=r['n_blocks'],failure_reproduced=r.get('failure_reproduced'),
    prefix_reproduced=r.get('prefix_reproduced'),new_pre=sum(p['end_char']<r['nodes'][r['fine_failure_candidate']]['end_char'] for p in r['points']) if r['fine_failure_candidate'] is not None else None))
(D/'metrics.json').write_text(json.dumps(dict(job_id=os.environ.get('SLURM_JOB_ID'),protocol_guard_tests=6,cases=summary),indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2),flush=True)
