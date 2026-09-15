from pathlib import Path
import json,collections,statistics,datetime,os
O=Path(__file__).parent;B=O.parents[1]
s=json.loads((O/'statistics.json').read_text(encoding='utf-8'));out={}
for m in ['deepseek','goedel','kimina']:
 rs=[]
 for sh in s['common_shards']:
  p=B/'audit/revision_2026_09_13/speedup-v2/repaired'/m/sh/'labels.jsonl'
  rs.extend(json.loads(x) for x in p.read_text(encoding='utf-8').splitlines())
 usable=[r for r in rs if r['category'] in ['verified','localized_tactic_failure']]
 st=[t for r in usable for t in r['steps']]
 out[m]=dict(usable=len(usable),total_steps=len(st),
  structured_steps=sum(t.get('is_structured',False) for t in st),
  multiline_steps=sum(t.get('n_lines',1)>1 for t in st),
  mean_lines=statistics.mean(t.get('n_lines',1) for t in st),
  recorded_empty_goals_before=sum(t.get('goals_before')==0 for t in st),
  empty_goal_traces=sum(any(t.get('goals_before')==0 for t in r['steps']) for r in usable),
  mean_without_L_gt30=statistics.mean(len(r['steps']) for r in usable if len(r['steps'])<=30),
  n_L_gt30=sum(len(r['steps'])>30 for r in usable),longest=[])
 for r in sorted(usable,key=lambda r:len(r['steps']),reverse=True)[:3]:
  d=dict(trace_id=r['trace_id'],L=len(r['steps']),category=r['category'],t_star=r.get('t_star'),
   empty_goals_before=sum(t.get('goals_before')==0 for t in r['steps']),
   statuses=dict(collections.Counter(t['status'] for t in r['steps'])),
   repeated_tactics=collections.Counter(t['tactic'] for t in r['steps']).most_common(5),
   first_steps=r['steps'][:3],last_steps=r['steps'][-3:])
  out[m]['longest'].append(d)
(O/'length-details.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({m:{k:v for k,v in r.items() if k!='longest'} for m,r in out.items()},indent=2))
