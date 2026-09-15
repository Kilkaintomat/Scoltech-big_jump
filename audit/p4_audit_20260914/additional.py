from pathlib import Path
import os,json,hashlib,time,collections
import numpy as np
from onebigjump.stats.gpd import gpd_from_order_statistics
from scipy import stats
ROOT=Path('/beegfs/home/denis.rakhmankin/onebigjump');OUT=ROOT/'audit/p4_audit_20260914';RUN=ROOT/'runs/expansion_20260911/p4'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
series=read(OUT/'series.json'); runs=read(OUT/'runs.json'); tail=read(OUT/'full-tail.json'); sen=read(OUT/'sensitivity.json'); summary=read(OUT/'original-paired-summary.json')
out={'tail':{'n':len(tail),'k20':sum(t['k']==20 for t in tail),'k_le30':sum(t['k']<=30 for t in tail),'gpd_missing':sum(t['gpd'] is None for t in tail),'gpd_valid_lt_half':sum(t['gpd_n_valid']<250 for t in tail),'gpd_valid_lt_80pct':sum(t['gpd_n_valid']<400 for t in tail),'identified':sum(t['identified'] for t in tail),'identified_after_initialization':sum(t['identified'] and t['step']>0 for t in tail),'n_after_initialization':sum(t['step']>0 for t in tail),'favours':dict(collections.Counter(t['favours'] for t in tail))}}
out['aggregate']={}
for arm in ['real','null']:
 r=[x for x in runs if x['arm']==arm]
 out['aggregate'][arm]={'test_acc_mean':float(np.mean([x['test_acc_last'] for x in r])),'moment_positive_checkpoints':sum(x['moment_n_positive'] for x in r),'gpd_positive_checkpoints':sum(x['gpd_n_positive'] for x in r),'n_checkpoints':sum(x['n_checkpoints'] for x in r)}
out['paired_delta']={}
for name in ['hill','moment','gpd']:
 vals=[p['paired_difference'][name] for p in summary['pairs']]
 out['paired_delta'][name]={'mean':float(np.mean(vals)),'median':float(np.median(vals)),'n_negative':sum(v<0 for v in vals),'values':vals}
out['sensitivity_summary']=[]
for split in ['all','train','test']:
 for f in [.01,.025,.05,.1]:
  r=[x for x in sen if x['arm']=='real' and x['split']==split and x['fraction']==f]
  rr={'split':split,'fraction':f}
  for name in ['hill','moment','gpd']:
   vals=[x[name+'_delta'] for x in r]; rr[name+'_n_drop']=sum(v<0 for v in vals);rr[name+'_mean_delta']=float(np.mean(vals))
   paired=[]
   for x in r:
    y=next(y for y in sen if y['seed']==x['seed'] and y['arm']=='null' and y['split']==split and y['fraction']==f)
    paired.append(x[name+'_delta']-y[name+'_delta'])
   rr[name+'_paired_n_drop']=sum(v<0 for v in paired);rr[name+'_paired_mean_delta']=float(np.mean(paired))
  out['sensitivity_summary'].append(rr)
spans=[]
for seed in range(5):
 ref=summary['pairs'][seed]['real_reference_step']
 for arm in ['real','null']:
  for step in [ref-300,ref+300]:
   with np.load(RUN/f'{arm}-{seed}/measurement/norms-{step:06d}.npz') as z: x=np.sort(z['z'].astype(float))[::-1]
   spans.append({'seed':seed,'arm':arm,'step':step,'min':float(x[-1]),'max':float(x[0]),'threshold5pct':float(x[638]),'tail_max_over_threshold':float(x[0]/x[638]),'tail_log10_span':float(np.log10(x[0]/x[638]))})
out['tail_spans']=spans
# Exact stored resampling seed for GPD is recorded by callers; these 100 new diagnostic replicates
# use an explicitly separate seed and classify convergence, not estimate a scientific CI.
diag=[]
for arm,seed,step in [('real',2,20000),('real',0,20000),('real',0,0)]:
 tag=f'{arm}-{seed}'; k=next(t['k'] for t in tail if t['arm']==arm and t['seed']==seed and t['step']==step)
 with np.load(RUN/tag/'measurement'/f'norms-{step:06d}.npz') as b:z=b['z']
 rs=np.random.default_rng(20260914); reasons=collections.Counter(); gammas=[]
 point=gpd_from_order_statistics(z,k)
 xs=np.sort(z)[::-1];excess=xs[:k]-xs[k]
 scig,_,scis=stats.genpareto.fit(excess,floc=0)
 for _ in range(100):
  est=gpd_from_order_statistics(rs.choice(z,len(z),replace=True),k)
  reasons['ok' if est.converged else est.message]+=1
  if est.converged:gammas.append(est.gamma)
 diag.append({'tag':tag,'step':step,'k':k,'point':{kk:(None if isinstance(v,float) and not np.isfinite(v) else v) for kk,v in point.as_dict().items()},'scipy_unconstrained_shape_diagnostic':float(scig),'new_resamples':100,'new_seed':20260914,'reasons':dict(reasons)})
out['gpd_convergence_diagnostic']=diag
# Check every saved full-tail scalar artifact against its manifest.
errors=[];n=0
for seed in range(5):
 for arm in ['real','null']:
  folder=RUN/f'{arm}-{seed}'/'tail';m=read(folder/'manifest.json')
  for p in folder.glob('step-*.json'):
   n+=1
   if hashlib.sha256(p.read_bytes()).hexdigest()!=m['outputs'].get(str(p.resolve())):errors.append(str(p))
out['full_tail_manifest_check']={'checked':n,'mismatches':errors}
out['job']=os.environ.get('SLURM_JOB_ID');out['utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
write('summary-audit.json',out)
print(json.dumps({k:v for k,v in out.items() if k not in ['tail_spans','gpd_convergence_diagnostic','sensitivity_summary']},indent=2))
print('GPD_DIAGNOSTIC',json.dumps(diag,indent=2))
