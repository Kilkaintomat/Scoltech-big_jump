"""Review final guards against the bounded LIVE responses; no new Lean executions."""
from pathlib import Path
import json,hashlib,os,shutil,datetime
from segmenter_final import from_ast,attach,Segmenter,map_to_completion
O=Path(__file__).parent;V=O/'validation';rs=json.loads((V/'cases.json').read_text(encoding='utf-8'))
out=O/'review';out.mkdir(exist_ok=True);rows=[]
for row in rs:
 p=V/(row['name']+'.json')
 if not p.exists():continue
 old=json.loads(p.read_text(encoding='utf-8'))
 if not isinstance(old,dict):
  old=json.loads((O/'validation_supplement'/(row['name']+'.json')).read_text(encoding='utf-8'))
 if not old.get('parse_ok'):continue
 c=old['case'];r=from_ast(old['source'],old['ast'])
 attach(r,c['header']+c['body'],len(c['header'])-2,old['whole_reply'])
 assert [x['end_char'] for x in r['points']]==[x['end_char'] for x in old['points']]
 answers={}
 for t in old['context_replays']:
  n=old['nodes'][t['node_id']];state=n['proof_states'][0]
  answers[(state['proof_state'],state['tactic'])]=t['reply']
 class CachedREPL:
  def _exchange(self,payload,timeout_s):
   return answers[(payload['proofState'],payload['tactic'])]
 s=Segmenter.__new__(Segmenter);s.repl=CachedREPL()
 s.replay_frontier(r)
 expected={x['node_id'] for x in old['context_replays']}
 assert {x['node_id'] for x in r['context_replays']}==expected
 assert not r['label_ready']
 if r.get('prefix_reproduced'):
  stop=r['nodes'][r['fine_failure_candidate']]['end_char']
  wanted={n['id'] for n in r['nodes'] if n['id'] in r['selected_node_ids'] and n['end_char']<stop}
  got={x['node_id'] for x in r['context_replays'] if x['ok']}
  assert wanted<=got
 prefix='arbitrary original prefix 😀\n'
 mapped=map_to_completion(r,prefix+c['body']+'\nEND',len(prefix))
 assert len(mapped)==len(r['points'])
 rejected=False
 try:map_to_completion(r,prefix+c['body']+'\nEND',len(prefix)+1)
 except ValueError:rejected=True
 assert rejected
 r['case']=c
 (out/(row['name']+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 new=dict(row)
 new['replay_ok']=sum(t['ok'] for t in r['context_replays'])
 import collections
 new['replay_status_counts']=dict(collections.Counter(t['status'] for t in r['context_replays']))
 if 'successful_context_replay' in new['checks']:
  new['checks']['successful_context_replay']=all(t['ok'] for t in r['context_replays'])
 new['final_checks_passed']=all(new['checks'].values())
 for k in ['failure_reproduced','prefix_reproduced','prefix_replay_complete','failure_and_prefix_reproduced','replay_skipped_node_ids']:
  new[k]=r.get(k)
 # A zero-run replay check is explicitly skipped, not counted as passed.
 new['skipped_checks']={}
 if not r['context_replays'] and 'successful_context_replay' in new['checks']:
  del new['checks']['successful_context_replay']
  new['skipped_checks']['successful_context_replay']='No unambiguous snapshot for selected compound tactic'
 new['replay_complete']=not r['replay_skipped_node_ids']
 rows.append(new)
summary={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'job_id':os.environ.get('SLURM_JOB_ID'),'scope':'cached bounded live responses; final guard and source mapping checks',
 'reviewed':len(rows),'mapping_guard_checks':2*len(rows),'main_campaign_modified':False,'new_Lean_runs':0,
 'saved':{},'groups':{},'live_incomplete':[r for r in rs if not r['passed']]}
import statistics
for group in ['curated','saved','illustrative']:
 g=[r for r in rows if r['group']==group]
 summary['groups'][group]=dict(n=len(g),old_total=sum(r['old_L'] for r in g),new_total=sum(r['new_L'] for r in g),
  mean_old=statistics.mean(r['old_L'] for r in g),mean_new=statistics.mean(r['new_L'] for r in g),
  selected=sum(r['selected'] for r in g),contexts=sum(r['context_coverage'] for r in g),
  replays=sum(r['replays'] for r in g),replay_ok=sum(r['replay_ok'] for r in g),
  errors=sum(not r['expected_ok'] for r in g),diagnostic_localizations=sum(r.get('failure_candidate') is not None for r in g),
  error_reproduced=sum(bool(r.get('failure_reproduced')) for r in g),
  error_and_entire_prefix_reproduced=sum(bool(r.get('failure_and_prefix_reproduced')) for r in g))
for m in ['deepseek','goedel','kimina']:
 g=[r for r in rows if r.get('model')==m]
 summary['saved'][m]=dict(n=len(g),old=sum(r['old_L'] for r in g),new=sum(r['new_L'] for r in g),
 mean_old=statistics.mean(r['old_L'] for r in g),mean_new=statistics.mean(r['new_L'] for r in g),
 increased=sum(r['new_L']>r['old_L'] for r in g),unchanged=sum(r['new_L']==r['old_L'] for r in g))
summary['replay_status_counts']=dict(collections.Counter(status for row in rows for status,count in row.get('replay_status_counts',{}).items() for _ in range(count)))
summary['saved_replay_status_counts']=dict(collections.Counter(status for row in rows if row['group']=='saved' for status,count in row.get('replay_status_counts',{}).items() for _ in range(count)))
summary['case_checks_failed']=[dict(name=row['name'],failed=[k for k,v in row['checks'].items() if not v]) for row in rows if not row['final_checks_passed']]
(out/'cases.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'metrics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
# Retain the exact original source files named by the live-run manifest.
archive=V/'live-code';archive.mkdir(exist_ok=True)
for name in ['segmenter.py','syntax_command.lean','validate.py','validate.sbatch']:
 if not (archive/name).exists():shutil.copy2(O/name,archive/name)
shutil.copy2(O/'segmenter_final.py',O/'segmenter.py')
files=[O/'segmenter.py',O/'segmenter_final.py',O/'syntax_command.lean',O/'review_cached.py',*out.glob('*.json')]
(out/'manifest.json').write_text(json.dumps(dict(files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
