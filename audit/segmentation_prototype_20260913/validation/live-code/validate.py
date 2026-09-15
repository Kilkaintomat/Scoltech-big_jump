from pathlib import Path
import json,datetime,hashlib,os,platform,time,traceback,collections,statistics
from segmenter import Segmenter,errors,reconstruct,align_points
from onebigjump.lean import LeanREPL,discover
from onebigjump.lean.segmentation import segment_proof
O=Path(__file__).parent;B=O.parents[1];out=O/'validation';out.mkdir(exist_ok=True)
curated=json.loads((O/'curated.json').read_text(encoding='utf-8'))
saved=json.loads((O/'sample.json').read_text(encoding='utf-8'))
assert len(saved)==24
cases=[dict(group='curated',**x) for x in curated]
for j,r in enumerate(saved):
 cases.append(dict(name='saved_%02d_%s'%(j,r['model']),group='saved',model=r['model'],trace_id=r['trace_id'],
  header=r['replay']['header'],body=r.get('replay_body',r['body']),expected_ok=r['category']=='verified',
  old_L=len(r['steps']),old_t_star=r.get('t_star')))
for name in ['deepseek_sqrt','kimina_sequence']:
 p=B/'audit/p1_report_20260913T1950Z/examples'/name/'label.json'
 r=json.loads(p.read_text(encoding='utf-8'))
 cases.append(dict(name=name,group='illustrative',header=r['replay']['header'],body=r.get('replay_body',r['body']),
   expected_ok=False,old_L=len(r['steps']),old_t_star=r['t_star']))
summary=[];start=time.monotonic()
with LeanREPL(discover(),imports='import Mathlib\nimport Aesop',default_timeout_s=90,startup_attempts=1,drain_timeout_s=30) as repl:
 s=Segmenter(repl)
 for c in cases:
  t=time.monotonic()
  row={k:v for k,v in c.items() if k not in ['header','body']}
  row.setdefault('old_L',len(segment_proof(c['body'])))
  try:
   result=s.inspect(c['header'],c['body'])
   result['case']=c
   row['parse_ok']=result['parse_ok']
   row['checks']={}
   if c.get('expected_parse') is False:
    row['checks']['parse_rejected']=not result['parse_ok']
   else:
    row['checks']['parse_ok']=result['parse_ok']
    if result['parse_ok']:
     row.update(new_L=result['n_blocks'],selected=len(result['selected_node_ids']),
       context_coverage=result['selected_context_coverage'],
       whole_ok=result['whole_elaboration_ok'],whole_errors=[x['data'][:150] for x in result['whole_errors']])
     row['checks']['lossless']=reconstruct(result)==result['source']
     row['checks']['whole_verdict']=result['whole_elaboration_ok']==c['expected_ok']
     if 'expected_points' in c:row['checks']['expected_points']=result['n_blocks']==c['expected_points']
     # Endpoints are fixed by a separate parse, independent of success/failure.
     plain=s.parse(c['body'])
     row['checks']['outcome_independent_endpoints']=[x['end_char'] for x in plain['points']]==[x['end_char'] for x in result['points']]
     row['checks']['tree_containment']=all(n['parent_id'] is None or
       result['nodes'][n['parent_id']]['start_char']<=n['start_char']<n['end_char']<=result['nodes'][n['parent_id']]['end_char'] for n in result['nodes'])
     # Tiny character-token oracle plus a deliberate token crossing the first boundary.
     chars=[(i,i+1) for i in range(len(result['source']))]
     row['checks']['exact_token_endpoints']=len(align_points(result,chars)['mapped'])==len(result['points'])
     if result['points']:
      e=result['points'][0]['end_char']
      crossing=[p for p in chars if not e-1<=p[0]<=e]+[(e-1,e+1)]
      row['checks']['crossing_token_rejected']=0 in align_points(result,crossing)['rejected_points']
     replays=s.replay_frontier(result,limit=60)
     row['replays']=len(replays);row['replay_ok']=sum(r['ok'] for r in replays)
     row['failure_candidate']=result.get('fine_failure_candidate')
     if result.get('fine_failure_candidate') is not None:
      n=result['nodes'][result['fine_failure_candidate']]
      row['fine_failure_text']=n['text'];row['new_pre']=sum(p['end_char']<n['end_char'] for p in result['points'])
      row['failure_reproduced']=result.get('failure_reproduced')
      row['prefix_reproduced']=result.get('prefix_reproduced')
     if c['expected_ok']:
      row['checks']['successful_context_replay']=all(r['ok'] for r in replays)
     if c.get('expected_failure'):
      row['checks']['failure_localized']=row.get('fine_failure_text')==c['expected_failure']
      row['checks']['failure_reproduced']=row.get('failure_reproduced') is True
      row['checks']['prefix_reproduced']=row.get('prefix_reproduced') is True
      row['checks']['pre_count']=row.get('new_pre')==c['expected_pre']
   (out/(c['name']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  except Exception as exc:
   row['exception']=repr(exc);row['traceback']=traceback.format_exc();row['checks']={'no_exception':False}
   # A timed-out exchange may be desynchronised; do not consume it as a later reply.
   if isinstance(exc,TimeoutError):repl.restart();s=Segmenter(repl)
  row['elapsed_s']=time.monotonic()-t;row['passed']=all(row['checks'].values())
  summary.append(row)
  (out/'cases.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
  print('CASE',c['name'],json.dumps(row,ensure_ascii=False),flush=True)
metrics=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job_id=os.environ.get('SLURM_JOB_ID'),
 elapsed_s=time.monotonic()-start,n_cases=len(summary),n_passed=sum(r['passed'] for r in summary),
 n_saved=24,n_curated=len(curated),n_illustrative=2,
 checks=sum(len(r['checks']) for r in summary),checks_passed=sum(sum(r['checks'].values()) for r in summary),
 prototype_promoted=False,main_campaign_modified=False,new_generation=False,
 groups={},limitations=['No model activation extraction or real tokenizer alignment in this bounded run.',
 'calc and tactic search/mapping combinators remain atomic.',
 'Independent replay of stored local contexts is not full chronological replay.',
 'Whole elaboration and no sorries are checked; the existing trusted-statement/axiom audit is not replaced.',
 'A missing context or ambiguous enclosing diagnostic is not labelled exact.'])
for g in ['curated','saved','illustrative']:
 rs=[r for r in summary if r['group']==g]
 good=[r for r in rs if r.get('new_L') is not None]
 metrics['groups'][g]=dict(n=len(rs),passed=sum(r['passed'] for r in rs),
  old_total=sum(r['old_L'] for r in good),new_total=sum(r['new_L'] for r in good),
  old_mean=statistics.mean(r['old_L'] for r in good),new_mean=statistics.mean(r['new_L'] for r in good),
  selected=sum(r['selected'] for r in good),contexts=sum(r['context_coverage'] for r in good),
  replays=sum(r.get('replays',0) for r in good),replay_ok=sum(r.get('replay_ok',0) for r in good),
  localized=sum(r.get('failure_candidate') is not None for r in good),
  reproduced=sum(r.get('failure_reproduced',False) for r in good))
(out/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
manifest=dict(job_id=os.environ.get('SLURM_JOB_ID'),python=platform.python_version(),
 git_commit=os.environ.get('ONEBIGJUMP_GIT_COMMIT'),git_dirty=bool(os.environ.get('ONEBIGJUMP_GIT_STATUS')),
 snapshot=os.environ.get('E1_SNAPSHOT'),files={})
for p in [O/'segmenter.py',O/'syntax_command.lean',O/'curated.json',O/'sample.json',O/'validate.py',O/'validate.sbatch',
 Path(os.environ['E1_REPL_RUNTIME_MANIFEST']),Path(os.environ['E1_ELAN_RUNTIME_MANIFEST']),*out.glob('*.json')]:
 manifest['files'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('METRICS',json.dumps(metrics,ensure_ascii=False,indent=2),flush=True)
