from pathlib import Path
import json,csv,datetime,collections,statistics,os,hashlib
B=Path('/beegfs/home/denis.rakhmankin/onebigjump');O=Path(__file__).parent
R=B/'runs/lean_reverification_20260913_local';F=B/'audit/revision_2026_09_13/speedup-v2/repaired'
models=['deepseek','goedel','kimina'];sources=[]
def readrows(p):
 data=p.read_bytes();sources.append({'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 return [json.loads(x) for x in data.splitlines(keepends=True) if x.endswith(b'\n')]
def summary(rs):
 cats=collections.Counter(r['category'] for r in rs)
 loc=[r for r in rs if r['category']=='localized_tactic_failure']
 def local(ls):
  if not ls:return {'n':0}
  lens=[len(r['steps']) for r in ls]
  return dict(n=len(ls),tasks=len({r['problem_id'] for r in ls}),with_pre=sum(r['t_star']>0 for r in ls),
   pre_tasks=len({r['problem_id'] for r in ls if r['t_star']>0}),first_failure=sum(r['t_star']==0 for r in ls),
   one_block=sum(x==1 for x in lens),up_to_three_blocks=sum(x<=3 for x in lens),longer_three=sum(x>3 for x in lens),
   chance=sum(1/x for x in lens)/len(ls),chance_top3=sum(min(3,x)/x for x in lens)/len(ls),
   median_L=statistics.median(lens),mean_L=statistics.mean(lens),max_L=max(lens),
   first_position_rate=sum(r['t_star']==0 for r in ls)/len(ls),
   with_pre_and_L_gt3=sum(r['t_star']>0 and len(r['steps'])>3 for r in ls),
   invariants_ok=all([x['status'] for x in r['steps'][:r['t_star']]]==['ok']*r['t_star'] and r['steps'][r['t_star']]['status']=='error' and all(x['status']=='unreached' for x in r['steps'][r['t_star']+1:]) for r in ls))
 primary=[r for r in loc if r['role']=='evaluation' and r['temperature']==0.6]
 return dict(n=len(rs),categories=dict(cats),localized=local(loc),primary_label_candidates=local(primary),
  evaluation_localized=local([r for r in loc if r['role']=='evaluation']),
  primary_pre_only=local([r for r in primary if r['t_star']>0]),
  tasks=len({r['problem_id'] for r in rs}),unexplained=sum(bool(r.get('unexplained_disagreement')) for r in rs))
s={'capture_start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'main':{},'repaired_common':{},'stage':{}}
repaired={m:{p.parent.name:p.parent for p in (F/m).glob('shard-*/manifest.json')} for m in models}
common=set.intersection(*(set(x) for x in repaired.values()))
s['common_completed_repaired_shards']=sorted(common)
compact=[]
for m in models:
 orig=[]
 for f in sorted((R/m/'main/verification').glob('shard-*/labels.jsonl')):orig+=readrows(f)
 assert len(orig)==len({r['trace_id'] for r in orig})
 s['main'][m]=summary(orig)
 ready=[]
 for shard in sorted(common):ready+=readrows(repaired[m][shard]/'labels.jsonl')
 s['repaired_common'][m]=summary(ready)
 for row in ready:
  compact.append({k:row.get(k) for k in ['trace_id','problem_id','model','temperature','role','category','t_star','task_family'] }|{'model':m,'L':len(row.get('steps',[]))})
 s['stage'][m]={stage:(R/m/'main'/stage/'manifest.json').exists() for stage in ['verification','extraction','measurement','analysis']}
s['queue']=json.loads((R/'queue.json').read_text())
s['continuation']=json.loads((B/'audit/revision_2026_09_13/saved-continuation-v1/state.json').read_text())
s['sidecar_queue']=json.loads((B/'runs/statistical_fitness_20260913/queue.json').read_text())
prev=json.loads((B/'audit/p1_report_20260913T1950Z/summary.json').read_text())
now=datetime.datetime.now(datetime.timezone.utc);dt=(now-datetime.datetime.fromisoformat(prev['captured_utc'])).total_seconds()/60
s['progress']={}
for m in models:
 old=prev['models'][m]['main']['n'];n=s['main'][m]['n'];rate=(n-old)/dt
 s['progress'][m]={'previous_n':old,'current_n':n,'delta_minutes':dt,'rows_per_minute':rate,'remaining_to_6672':6672-n,'linear_minutes_remaining':(6672-n)/rate if rate>0 else None}
s['capture_end_utc']=now.isoformat()
(O/'metrics.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
(O/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
with (O/'p2_label_candidates.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(compact[0]));w.writeheader();w.writerows(compact)
print(json.dumps({k:v for k,v in s.items() if k not in ['queue','continuation','sidecar_queue']},ensure_ascii=False,indent=2))
print('SIDECAR',s['sidecar_queue'].get('counts'))
