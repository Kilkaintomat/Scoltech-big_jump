"""Exploratory offset diagnostic. Run only under Slurm; never edits primary outputs."""
from __future__ import annotations
import collections, datetime, hashlib, importlib.metadata, json, os, pathlib, platform, sys
import numpy as np
import pandas as pd
from onebigjump.experiments.dataset import validate_table

ROOT = pathlib.Path('/beegfs/home/denis.rakhmankin/onebigjump')
HERE = ROOT/'audit/offset_review_20260914_v1'
OUT = HERE/('result-'+os.environ['SLURM_JOB_ID'])
OUT.mkdir(exist_ok=False)
PLAN = json.loads((HERE/'plan.json').read_text())
INPUTS = {}
CHECKS = []
rng = np.random.default_rng(PLAN['seed'])
OFFSETS = PLAN['fixed_offsets']
KEYS = ['lag_%+d'%d for d in OFFSETS]+['near_1','argmin','complement_coverage','random_from_complement','always_first','always_last']

def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def source(p):
    p=pathlib.Path(p)
    INPUTS[str(p)]=sha(p)
    return p

def read(p):
    return json.loads(source(p).read_text())

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def write(name,x):
    (OUT/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+'\n')

def check_digest(manifest, p):
    doc=read(manifest); expected=doc['outputs'].get(str(p))
    if expected is None:
        matches=[v for k,v in doc['outputs'].items() if pathlib.Path(k).name==p.name]
        assert len(matches)==1,(str(p),'ambiguous manifest')
        expected=matches[0]
    actual=sha(p); assert actual==expected,(str(p),'digest mismatch')
    CHECKS.append({'file':str(p),'sha256':actual,'matches_manifest':True})

def scores(tr, drop=False, fail=None):
    lo=int(drop); L=tr['L']; f=tr['fail'] if fail is None else fail
    cand=np.arange(lo,L); z=tr['z'][lo:]; n=len(cand)
    assert n>0 and lo<=f<L
    j=int(cand[np.argmax(z)]); mi=int(cand[np.argmin(z)])
    hit=np.array([float(j-f==d) for d in OFFSETS]+[
        float(abs(j-f)<=1),float(mi==f),float(j!=f),
        float(j!=f)/(n-1) if n>1 else 0.,float(f==lo),float(f==L-1)])
    chance=np.array([float(lo<=f+d<L)/n for d in OFFSETS]+[
        sum(lo<=f+d<L for d in (-1,0,1))/n,1/n,1-1/n,1/n if n>1 else 0.,
        float(f==lo),float(f==L-1)])
    return hit,chance,j,mi

# Independent hand-calculated boundary/unit tests before touching observations.
toy={'L':3,'fail':0,'z':np.array([1.,5.,2.])}
assert scores(toy)[0][KEYS.index('lag_+1')]==1
assert scores(toy)[1][KEYS.index('near_1')]==2/3
assert scores(toy)[1][KEYS.index('lag_-1')]==0
assert scores({'L':2,'fail':0,'z':np.array([1.,2.])})[0][KEYS.index('random_from_complement')]==1
assert scores({'L':2,'fail':1,'z':np.array([10.,2.])},True)[2]==1
assert np.allclose(np.linalg.norm(np.diff(np.array([[1.,2.],[3.,4.]]),axis=0),axis=1),
                   np.linalg.norm(-np.diff(np.array([[1.,2.],[3.,4.]]),axis=0),axis=1))
CHECKS.append({'synthetic_boundary_assertions':6,'passed':True})

def task_bootstrap(traces, values, chances):
    tasks=sorted({t['task'] for t in traces})
    if len(tasks)<20:return {'n_tasks':len(tasks),'ci95':None,'reason':'fewer than 20 independent tasks'}
    sums=np.array([values[[t['task']==k for t in traces]].sum(axis=0) for k in tasks])
    gaps=np.array([(values-chances)[[t['task']==k for t in traces]].sum(axis=0) for k in tasks])
    counts=np.array([sum(t['task']==k for t in traces) for k in tasks])
    weights=rng.multinomial(len(tasks),np.ones(len(tasks))/len(tasks),size=PLAN['bootstrap'])
    den=weights@counts
    draws=(weights@sums)/den[:,None];diff=(weights@gaps)/den[:,None]
    return {'n_tasks':len(tasks),'resamples':PLAN['bootstrap'],'unit':'task',
            'ci95':dict(zip(KEYS,np.quantile(draws,[.025,.975],axis=0).T)),
            'gap_vs_uniform_ci95':dict(zip(KEYS,np.quantile(diff,[.025,.975],axis=0).T)),
            'scope':'descriptive pointwise; post hoc choices and coverage not calibrated'}

def positional_null(traces, drop):
    unique={}
    for tr in sorted(traces,key=lambda t:t['id']):unique.setdefault(tr['task'],tr)
    groups=collections.defaultdict(list)
    for tr in unique.values():groups[(tr['family'],tr['L'])].append(tr)
    selected=[t for k,g in sorted(groups.items()) if len(g)>=2 for t in g]
    if not selected:return {'available':False,'n_tasks':0}
    strata=collections.defaultdict(list)
    for i,t in enumerate(selected):strata[(t['family'],t['L'])].append(i)
    fail=np.array([t['fail'] for t in selected])
    obs=np.mean([scores(t,drop)[0] for t in selected],axis=0)
    # Cache scores at every permissible failure position. No movement of the model scores.
    caches=[np.array([scores(t,drop,f)[0] for f in range(int(drop),t['L'])]) for t in selected]
    permutations=np.empty((PLAN['permutations'],len(KEYS)))
    for b in range(PLAN['permutations']):
        f=fail.copy()
        for inds in strata.values():f[inds]=rng.permutation(fail[inds])
        permutations[b]=np.mean([caches[i][f[i]-int(drop)] for i in range(len(selected))],axis=0)
    center=permutations.mean(axis=0);dev=np.abs(obs-center)
    null_dev=np.abs(permutations-center)
    adjusted=(1+(null_dev.max(axis=1)[:,None]>=dev[None,:]-1e-12).sum(axis=0))/(1+len(permutations))
    upper=(1+(permutations>=obs[None,:]-1e-12).sum(axis=0))/(1+len(permutations))
    return {'available':True,'n_tasks':len(selected),'excluded_tasks':len(unique)-len(selected),
            'min_tasks_met':len(selected)>=20,'unit':'one deterministic trace per task',
            'strata':'exact task family and exact length; discard singleton strata',
            'permutations':len(permutations),'observed':dict(zip(KEYS,obs)),
            'null_mean':dict(zip(KEYS,center)),'p_upper_unadjusted':dict(zip(KEYS,upper)),
            'p_abs_max_stat_adjusted':dict(zip(KEYS,adjusted)),
            'p_abs_max_stat_bonferroni_3_models':dict(zip(KEYS,np.minimum(1,3*adjusted))),
            'interpretation':'exploratory conditional randomization; exchangeability is assumed, not established; subsets are diagnostics'}

def summarize(traces, drop=False, with_null=True):
    if not traces:return {'n':0}
    packed=[scores(t,drop) for t in traces]
    values=np.array([p[0] for p in packed]);chance=np.array([p[1] for p in packed])
    lengths=np.array([t['L'] for t in traces]);fails=np.array([t['fail'] for t in traces]);js=np.array([p[2] for p in packed])
    result={'n':len(traces),'n_tasks':len({t['task'] for t in traces}),
       'length_mean':lengths.mean(),'length_median':np.median(lengths),
       'length_harmonic':1/np.mean(1/lengths),'length_counts':dict(collections.Counter(lengths)),
       'candidate_length_mean':np.mean(lengths-int(drop)),
       'first_error_rate':np.mean(fails==0),'first_jump_rate':np.mean(js==0),
       'last_error_rate':np.mean(fails==lengths-1),'last_jump_rate':np.mean(js==lengths-1),
       'offset_counts':dict(collections.Counter(js-fails)),
       'failure_position_counts_1based':dict(collections.Counter(fails+1)),
       'max_position_counts_1based':dict(collections.Counter(js+1)),
       'rates':dict(zip(KEYS,values.mean(axis=0))),'uniform_chance':dict(zip(KEYS,chance.mean(axis=0))),
       'surprisal_top1':np.mean([int(drop)+np.argmax(t['surprisal'][int(drop):])==t['fail'] for t in traces]),
       'tied_max_traces':sum(np.sum(t['z'][int(drop):]==np.max(t['z'][int(drop):]))>1 for t in traces)}
    result['joint_length_failure_max']=[{'L':k[0],'failure_step':k[1]+1,'max_step':k[2]+1,'count':v}
         for k,v in sorted(collections.Counter(zip(lengths,fails,js)).items())]
    result['bootstrap']=task_bootstrap(traces,values,chance)
    if with_null:result['position_null']=positional_null(traces,drop)
    return result

METRICS={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'job':os.environ['SLURM_JOB_ID'],'plan':PLAN,'models':{},'scientific_decision':'exploratory; no replacement of primary outcomes'}
for model,cell in PLAN['primary_cells'].items():
    base=ROOT/'runs/lean_reverification_20260913_local'/model/'main'
    config=read(base/'protocol.json'); p=base/'measurement/deviations.parquet'
    check_digest(base/'measurement/manifest.json',p)
    frame=pd.read_parquet(source(p));validate_table(frame)
    primary_path=base/'analysis'/('cell-T0.6-layer%d-whitened.json'%cell['layer'])
    check_digest(base/'analysis/manifest.json',primary_path)
    previous=read(primary_path)
    part=frame[(frame.temperature==cell['temperature'])&(frame.layer==cell['layer'])&
        (frame.statistic==cell['statistic'])&(frame.role=='evaluation')&
        frame.primary_eligible&(frame.outcome=='refuted')]
    traces=[]
    for tid,g in part.groupby('trace_id',sort=True):
        g=g.sort_values('t'); L=int(g.L.iloc[0]);fail=int(g.t_star.iloc[0])
        assert np.array_equal(g.t.to_numpy(),np.arange(L)) and 0<=fail<L
        assert np.all(np.isfinite(g.z)) and np.all(np.isfinite(g.surprisal))
        assert not g.loc[g.t>=fail,'valid'].any()
        assert (g.loc[g.t>fail,'status']=='unreached').all()
        traces.append({'id':str(tid),'task':str(g.prompt_id.iloc[0]),'family':str(g.task_family.iloc[0]),
                       'L':L,'fail':fail,'z':g.z.to_numpy(),'surprisal':g.surprisal.to_numpy()})
    assert len(traces)==previous['P2']['n_traces']
    subsets={'all':traces,'failure_after_first':[t for t in traces if t['fail']>0],
             'failure_after_first_drop_first':[t for t in traces if t['fail']>0]}
    result={'cell':cell,'subsets':{},'by_length':{},'primary_summary':{},
            'verification':read(base/'verification/metrics.json')}
    for name,ts in subsets.items():result['subsets'][name]=summarize(ts,name.endswith('drop_first'))
    rates=result['subsets']['all']['rates']
    assert np.isclose(rates['lag_+0'],previous['P2']['jump']['top1'])
    assert np.isclose(result['subsets']['all']['surprisal_top1'],previous['P2']['surprisal']['top1'])
    assert np.isclose(result['subsets']['all']['uniform_chance']['lag_+0'],previous['P2']['chance'])
    for label,pred in [('L=1',lambda L:L==1),('L=2',lambda L:L==2),('L=3',lambda L:L==3),
                       ('L>=4',lambda L:L>=4),('L>=6',lambda L:L>=6)]:
        result['by_length'][label]=summarize([t for t in traces if pred(t['L'])],with_null=False)
    result['primary_summary']['P1']={name:{k:v.get(k) for k in ('hill','moment','gpd','n_steps','n_tasks','tail_tasks','sufficient_sample')}
                                      for name,v in previous['P1'].items()}
    result['primary_summary']['P1_difference']=previous['task_bootstrap']['P1_direct_moment_difference']
    result['primary_summary']['P2']={k:previous['P2'][k] for k in ('jump','surprisal','chance')}
    result['primary_summary']['P3']=previous['P3']
    result['controls']={}
    for sub in ('positional','whitening-01','whitening-04','whitening-10'):
        p=ROOT/'runs/controls_20260913_local/main'/model/sub/'metrics.json'
        check_digest(p.with_name('manifest.json'),p);result['controls'][sub]=read(p)
    # Reconstruct independently on a bounded deterministic sample. Never rerun a model.
    chosen={t['id']:t for t in traces[:3]}
    extraction_path=source(base/'extraction/trajectories.jsonl')
    records={}
    with extraction_path.open() as f:
        for line in f:
            row=json.loads(line)
            if row['trace_id'] in chosen:records[row['trace_id']]=row
    labels={}
    with source(base/'verification/labels.jsonl').open() as f:
        for line in f:
            row=json.loads(line)
            if row['trace_id'] in chosen:labels[row['trace_id']]=row
    fit_path=base/'measurement'/('calibration-T0.6-layer%d.npz'%cell['layer'])
    check_digest(base/'measurement/manifest.json',fit_path)
    with np.load(source(fit_path),allow_pickle=False) as f:
        fit={k:f[k] for k in ('mean','vectors','eigenvalues','base')}
    evidence=[]
    for tid,tr in chosen.items():
        rec=records[tid];lab=labels[tid];sp=source(rec['states_path'])
        assert INPUTS[str(sp)]==rec['states_sha256']
        with np.load(sp,allow_pickle=False) as bundle:
            x=bundle['states_%d'%cell['layer']].astype(np.float64)
            lp=bundle['surprisal'].astype(float)
        assert len(x)==tr['L']+1 and len(lab['steps'])==tr['L'] and lab['t_star']==tr['fail']
        al=rec['alignment'];poss=al['positions'];spans=al['step_token_spans_inclusive']
        assert len(poss)==len(x) and all(poss[i+1]==s[1] for i,s in enumerate(spans))
        inc=x[1:]-x[:-1]
        raw=np.sqrt(np.einsum('ij,ij->i',inc,inc))
        centered=inc-fit['mean'];proj=centered@fit['vectors'].T
        orth=centered-proj@fit['vectors']
        w=np.sqrt(np.einsum('ij,ij->i',proj/np.sqrt(fit['eigenvalues']),proj/np.sqrt(fit['eigenvalues']))+
                  np.einsum('ij,ij->i',orth,orth)/float(fit['base']))
        saved_raw=frame[(frame.trace_id==tid)&(frame.layer==cell['layer'])&(frame.statistic=='raw')].sort_values('t').z.to_numpy()
        assert np.allclose(raw,saved_raw,rtol=1e-10,atol=1e-10)
        assert np.allclose(w,tr['z'],rtol=1e-10,atol=1e-10)
        assert np.allclose(lp,tr['surprisal'],rtol=1e-10,atol=1e-10)
        evidence.append({'trace_id':tid,'problem_id':tr['task'],'L':tr['L'],'failure_step_1based':tr['fail']+1,
           'positions':poss,'token_spans_inclusive':spans,'prompt_to_first_end_tokens':poss[1]-poss[0],
           'gap_before_first_formal_span_tokens':spans[0][0]-poss[0]-1,
           'raw_max_abs_error':np.max(np.abs(raw-saved_raw)),'whitened_max_abs_error':np.max(np.abs(w-tr['z'])),
           'z_whitened':w,'z_raw':raw,'surprisal':lp,
           'labels_steps':lab['steps'],'indexing_numeric_passed':True})
    result['indexing_evidence']=evidence
    result['length_scope']='Primary eligible refuted evaluation traces only; not all 20016 generated proofs.'
    METRICS['models'][model]=result
    write('partial-metrics.json',METRICS)
    per_trace=[{'model':model,'trace_id':t['id'],'prompt_id':t['task'],'family':t['family'],'L':t['L'],
                'failure_step':t['fail']+1,'max_step':int(np.argmax(t['z']))+1,
                'min_step':int(np.argmin(t['z']))+1,'surprisal_step':int(np.argmax(t['surprisal']))+1,
                'offset':int(np.argmax(t['z']))-t['fail'],'z':json.dumps(t['z'].tolist()),
                'surprisal':json.dumps(t['surprisal'].tolist())} for t in traces]
    pd.DataFrame(per_trace).to_csv(OUT/('%s-traces.csv'%model),index=False)
    print(model,json.dumps(clean({k:result['subsets']['all'][k] for k in ('n','length_mean','length_harmonic','length_counts','first_error_rate','first_jump_rate','rates')})),flush=True)

METRICS['P4']=read(ROOT/'audit/p4_audit_20260914/summary-audit.json')
METRICS['P5']=read(ROOT/'audit/p5_repair_20260914_v2/review-8466522/metrics.json')
METRICS['P5_current']=read(ROOT/'audit/p5_repair_20260914_v2/CURRENT.json')
source(HERE/'onebigjumpdraft.pdf')
for rel in ('src/onebigjump/e1/measurement.py','src/onebigjump/e1/extraction.py','src/onebigjump/e1/spans.py',
            'src/onebigjump/e1/main_analysis.py','src/onebigjump/models/token_alignment.py'):
    source(ROOT/'audit/revision_2026_09_13/snapshots/lean-local-toolchain-v7'/rel)
source(HERE/'plan.json');source(HERE/'audit.py');source(HERE/'audit.sbatch')
write('metrics.json',METRICS);write('checks.json',CHECKS)
versions={}
for name in ('numpy','pandas','scipy','pyarrow','matplotlib','markdown','reportlab','python-docx'):
    try:versions[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:versions[name]=None
manifest={'stage':'exploratory-offset-audit','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'job':os.environ['SLURM_JOB_ID'],'config':PLAN,'git_commit':os.environ.get('ONEBIGJUMP_GIT_COMMIT'),
 'git_dirty':bool(os.environ.get('ONEBIGJUMP_GIT_STATUS')),
 'source_tracking':'Auditor and directly inspected upstream source files hashed; upstream manifests retained; not a full recursive audit.',
 'environment':{'python':sys.version,'packages':versions,'hostname':platform.node(),'platform':platform.platform(),
                'cpu_count':os.cpu_count(),'allocated_cpus':os.environ.get('SLURM_CPUS_PER_TASK'),'hardware':platform.processor()},
 'inputs':INPUTS,'outputs':{str(p):sha(p) for p in OUT.iterdir() if p.is_file()},
 'limitations':PLAN['limitations']}
write('manifest.json',manifest)
print('FINISHED',str(OUT),flush=True)
