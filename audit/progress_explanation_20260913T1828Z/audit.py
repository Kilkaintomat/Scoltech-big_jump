import collections, datetime, hashlib, json, os, statistics
from pathlib import Path
root=Path('/beegfs/home/denis.rakhmankin/onebigjump')
out=Path(__file__).parent
now=datetime.datetime.utcnow().isoformat()+'Z'
models=['deepseek','goedel','kimina']
result={'captured_utc':now,'scope':'Read-only descriptive audit of existing journals; no model generation or Lean proof reruns. Matched cohort uses shards 0 and 1 only.','models':{},'sources':[]}
selected={}
def describe(xs):
    xs=sorted(float(x) for x in xs)
    if not xs:return None
    return {'n':len(xs),'sum':sum(xs),'mean':statistics.mean(xs),'median':statistics.median(xs),'p95':xs[min(len(xs)-1,int(.95*len(xs)))],'max':max(xs)}
for model in models:
    base=root/'runs/lean_reverification_20260913_local'/model/'main'/'verification'
    records=[]; matched=[]; shards=[]
    for f in sorted(base.glob('shard-*/labels.jsonl')):
        raw=f.read_bytes(); digest=hashlib.sha256(raw).hexdigest(); rows=[]; skipped=0
        for line in raw.splitlines():
            try:rows.append(json.loads(line))
            except ValueError:skipped+=1
        records+=rows
        if f.parent.name.startswith(('shard-000-','shard-001-')):matched+=rows
        shards.append({'path':str(f.relative_to(root)),'n':len(rows),'categories':dict(collections.Counter(r['category'] for r in rows)),'mtime_utc':datetime.datetime.utcfromtimestamp(f.stat().st_mtime).isoformat()+'Z','elapsed_s':describe([r['elapsed_s'] for r in rows if r.get('elapsed_s') is not None]),'skipped_partial_lines':skipped})
        result['sources'].append({'path':str(f.relative_to(root)),'bytes':len(raw),'sha256':digest})
    cats=collections.Counter(r['category'] for r in records)
    bycat={}
    for cat in sorted(cats):
        rs=[r for r in records if r['category']==cat]
        bycat[cat]={'n':len(rs),'elapsed_s':describe([r['elapsed_s'] for r in rs if r.get('elapsed_s') is not None]),'whole_proof_ok':dict(collections.Counter(str(r.get('whole_proof_ok')) for r in rs))}
    bad=[]
    for r in records:
        if r.get('unexplained_disagreement'):
            bad.append({k:r.get(k) for k in ['trace_id','category','error','whole_proof_ok','replay_ok','t_star','body','step_spans','steps','replay']})
    result['models'][model]={'n':len(records),'unique_trace_ids':len(set(r['trace_id'] for r in records)),'categories':dict(cats),'by_category':bycat,'shards':shards,'unexplained_disagreements':bad,'verified_step_counts':describe([len(r.get('steps',[])) for r in records if r['category']=='verified'])}
    selected[model]=matched
sets=[set(r['problem_id'] for r in selected[m]) for m in models]
common=set.intersection(*sets)
cohort={'n_tasks':len(common),'same_task_sets':all(s==sets[0] for s in sets),'models':{}}
for m in models:
    rows=[r for r in selected[m] if r['problem_id'] in common]
    groups=collections.defaultdict(list)
    for r in rows:groups[r['problem_id']].append(r)
    bytemp={}
    for temp in sorted(set(r['temperature'] for r in rows)):
        rr=[r for r in rows if r['temperature']==temp]
        solved=set(r['problem_id'] for r in rr if r['category']=='verified')
        bytemp[str(temp)]={'n':len(rr),'verified':sum(r['category']=='verified' for r in rr),'tasks_solved_at_least_once':len(solved),'n_tasks':len(common),'categories':dict(collections.Counter(r['category'] for r in rr))}
    family={}
    for fam in sorted(set(r.get('task_family') for r in rows)):
        rr=[r for r in rows if r.get('task_family')==fam]
        family[fam]={'n':len(rr),'tasks':len(set(r['problem_id'] for r in rr)),'verified':sum(r['category']=='verified' for r in rr),'categories':dict(collections.Counter(r['category'] for r in rr))}
    cohort['models'][m]={'n':len(rows),'categories':dict(collections.Counter(r['category'] for r in rows)),'attempt_counts_per_task':dict(collections.Counter(len(g) for g in groups.values())),'successful_attempts_per_task_histogram':dict(collections.Counter(sum(r['category']=='verified' for r in g) for g in groups.values())),'tasks_solved_at_least_once':sum(any(r['category']=='verified' for r in g) for g in groups.values()),'by_temperature':bytemp,'by_family':family}
result['matched_cohort']=cohort
for name in ['runs/lean_reverification_20260913_local/queue.json','audit/revision_2026_09_13/statistical-fitness-v1/benchmark-guarded/metrics.json']:
    f=root/name
    if f.exists():
        raw=f.read_bytes();result['sources'].append({'path':name,'sha256':hashlib.sha256(raw).hexdigest()})
        data=json.loads(raw)
        if name.endswith('queue.json'):
            result['queue']={k:v for k,v in data.items() if k!='tasks'}
            result['main_tasks']={k:v for k,v in data['tasks'].items() if '/main-' in k}
        else:result['guarded_benchmark']=data
(out/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
(out/'manifest.json').write_text(json.dumps({'created_utc':now,'slurm_job_id':os.environ.get('SLURM_JOB_ID'),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'metrics_sha256':hashlib.sha256((out/'metrics.json').read_bytes()).hexdigest(),'sources':result['sources']},indent=2),encoding='utf8')
print(json.dumps({'captured_utc':now,'models':{m:{'n':result['models'][m]['n'],'categories':result['models'][m]['categories']} for m in models},'matched_cohort':cohort},ensure_ascii=False))
