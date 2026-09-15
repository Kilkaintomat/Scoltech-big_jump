from pathlib import Path
import json,csv,datetime,collections,hashlib,os,platform
import numpy as np
B=Path('/beegfs/home/denis.rakhmankin/onebigjump');O=Path(__file__).parent
F=B/'audit/revision_2026_09_13/speedup-v2/repaired'
R=B/'runs/lean_reverification_20260913_local'
models=['deepseek','goedel','kimina'];sources=[]
def read(p):
 data=p.read_bytes();sources.append(dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 return [json.loads(x) for x in data.splitlines()]
def dist(rs):
 ls=np.array([len(r.get('steps',[])) for r in rs]); nonzero=ls[ls>0]
 out=dict(n=len(rs),tasks=len({r['problem_id'] for r in rs}),zero_steps=int((ls==0).sum()))
 if not len(nonzero):return out
 out.update(dict(n_segmented=len(nonzero),mean=float(nonzero.mean()),median=float(np.median(nonzero)),
 q10=float(np.quantile(nonzero,.1)),q25=float(np.quantile(nonzero,.25)),q75=float(np.quantile(nonzero,.75)),
 q90=float(np.quantile(nonzero,.9)),q95=float(np.quantile(nonzero,.95)),q99=float(np.quantile(nonzero,.99)),
 min=int(nonzero.min()),max=int(nonzero.max()),total_steps=int(nonzero.sum()),mean_points=float(nonzero.mean()+1),
 one_step=int((nonzero==1).sum()),le3=int((nonzero<=3).sum()),gt20=int((nonzero>20).sum()),
 histogram=dict(sorted(collections.Counter(map(int,nonzero)).items()))))
 loc=[r for r in rs if r['category']=='localized_tactic_failure']
 if loc:out['failure']=dict(n=len(loc),with_pre=sum(r['t_star']>0 for r in loc),first=sum(r['t_star']==0 for r in loc),
 mean_pre=float(np.mean([r['t_star'] for r in loc])),mean_post=float(np.mean([len(r['steps'])-r['t_star']-1 for r in loc])))
 return out
def describe(rs):
 return {scope:{cat:dist([r for r in rr if (r['category']==cat if cat not in ['all','usable'] else cat=='all' or r['category'] in ['verified','localized_tactic_failure'])]) for cat in ['all','usable','verified','localized_tactic_failure']} for scope,rr in [
 ('all_roles_temperatures',rs),('evaluation_T06',[r for r in rs if r['role']=='evaluation' and r['temperature']==.6])]}
s=dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job_id=os.environ.get('SLURM_JOB_ID'),latest={},common={},scope='read existing labels only; no resegmentation or reverification of population')
shards={m:{p.parent.name:p.parent for p in (F/m).glob('shard-*/manifest.json')} for m in models}
common=sorted(set.intersection(*(set(v) for v in shards.values())))
s['common_shards']=common;compact=[];sample=[]
for m in models:
 commonrows=[]
 for sh in common:commonrows+=read(shards[m][sh]/'labels.jsonl')
 assert len(commonrows)==len({r['trace_id'] for r in commonrows})
 s['common'][m]=describe(commonrows)
 full=R/m/'main/verification/manifest.json'
 if full.exists() and json.loads(full.read_text())['stage']=='gather-verification-repaired':
  rs=read(full.parent/'labels.jsonl');origin='accepted_final_gather'
 else:
  rs=[]
  for sh in sorted(shards[m]):rs+=read(shards[m][sh]/'labels.jsonl')
  origin='completed_corrected_shards'
 s['latest'][m]=dict(source=origin,shards=sorted(shards[m]),statistics=describe(rs))
 for r in commonrows:
  compact.append(dict(model=m,trace_id=r['trace_id'],problem_id=r['problem_id'],role=r['role'],temperature=r['temperature'],category=r['category'],L=len(r.get('steps',[])),t_star=r.get('t_star')))
 # Fixed bounded sample: 4 successes + 4 localized errors per model, hash order; maximum 24 saved answers.
 for cat in ['verified','localized_tactic_failure']:
  pool=[r for r in commonrows if r['category']==cat and r['role']=='evaluation' and r['temperature']==.6 and len(r['steps'])<=30]
  ordered=sorted(pool,key=lambda r:hashlib.sha256(('tree-prototype-v1:'+r['trace_id']).encode()).hexdigest())
  for r in ordered[:4]:sample.append(dict(model=m,**r))
 # Outlier inspection based on saved metadata only.
 s['latest'][m]['longest']=[dict(trace_id=r['trace_id'],category=r['category'],L=len(r['steps']),role=r['role'],temperature=r['temperature'],snippet=r.get('body','')[:300]) for r in sorted(rs,key=lambda r:len(r['steps']),reverse=True)[:3]]
(O/'statistics.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'statistics-sources.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
(O/'sample.json').write_text(json.dumps(sample,ensure_ascii=False,indent=2),encoding='utf-8')
with (O/'block-counts.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(compact[0]));w.writeheader();w.writerows(compact)
print(json.dumps({m:{scope:{cat:{k:v for k,v in d.items() if k!='histogram'} for cat,d in cats.items()} for scope,cats in s['common'][m].items()} for m in models},indent=2),flush=True)
print('SAMPLE',len(sample),flush=True)
