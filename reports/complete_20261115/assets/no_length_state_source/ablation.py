import os,sys,time,json,copy,collections,datetime,platform,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=Path('/beegfs/home/denis.rakhmankin/onebigjump')
sys.path.insert(0,str(ROOT/'experiments/localizer_putnam_stream_20261113_v1'))
import core as c
import numpy as np
OUT=ROOT/'runs'/HERE.name
ARMS=['PST_state','MD_noN_state']
BASES={'PST':'PST','MD_noN':'MD_noN'}
def basearm(arm):return 'MD_noN' if arm.startswith('MD_noN') else 'PST'
def vararm(arm):return 'state' if arm.endswith('_state') else 'deltaX' if arm.endswith('_deltaX') else 'u' if arm.endswith('_u') else None
def design(rr,pp,arm):
 phi,names=c.scalar_basis(rr,pp);assert names==pp['names']
 base=basearm(arm);idx=c.columns(pp,'PST' if base=='PST' else 'MD')
 idx=[i for i in idx if not names[i].startswith('log_tokens:')]
 # Preserve original base order; append adjacent q changes and then norm.
 main=[i for i in idx if names[i].split(':')[0] not in ['dq','absdq']]
 tail=[i for name in ['dq:0','absdq:0'] for i in idx if names[i]==name]
 idx=main+tail
 if arm.endswith('W'):idx.append(names.index('jump:0'))
 assert not any(names[i].startswith('log_tokens:') for i in idx)
 A=((phi-pp['mean'])/pp['scale'])[:,idx]
 if pp['mode']=='stream':A=np.column_stack([np.ones(len(A)),A])
 if vararm(arm):
  V=(c.vector_raw(rr,pp['vector_arm'],pp['center'])-pp['vector_mean'])/pp['vector_scale']
  A=np.column_stack([A,V])
 return A
def prep(rr,mode,arm):return c.prep(rr,mode,vararm(arm))
def manifest(folder,extra=None):
 import scipy,sklearn
 c.save(folder/'manifest.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job=os.getenv('SLURM_JOB_ID'),array=os.getenv('SLURM_ARRAY_TASK_ID'),
 git_commit=os.getenv('ONEBIGJUMP_GIT_COMMIT'),git_dirty=bool(os.getenv('ONEBIGJUMP_GIT_STATUS')),host=platform.node(),
 versions=dict(numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),source={str(p):c.sha(p) for p in list(HERE.glob('*.py'))+list(HERE.glob('*.md'))+list(HERE.glob('*.sbatch'))+[Path(c.__file__)]},
 inputs=c.INPUTS,outputs={str(p):c.sha(p) for p in folder.rglob('*') if p.is_file() and p.name!='manifest.json'},extra=extra))
def splits(ds,mode):
 if ds=='ProofNet' and mode=='offline':
  sp=c.read(ROOT/'runs/lean_localizer_20260925_v1/splits.json')
  for o in sp['outer']:
   for d in [o]+o['inner']:
    for k in ['train_groups','test_groups','validation_groups']:
     if k in d:d[k]=['ProofNet:'+g for g in d[k]]
  return sp
 return c.read(c.checked(c.OUT/'data/goedel'/ds/(mode+'_splits.json'),c.OUT/'data/goedel/manifest.json'))
def folder(mode,ds,fold,arm):return OUT/'fits'/mode/ds/str(fold)/arm
def done(u):return (folder(*u)/'manifest.json').exists()
def ready(u):
 mode,ds,fold,arm=u
 return not(mode=='offline' and ds=='ProofNet' and fold=='frozen') or all(done((mode,ds,str(i),arm)) for i in range(5))
def units():
 # Direct user question first, then the same contrasts in transfer and streaming.
 for mode,ds in [('offline','ProofNet'),('offline','Putnam'),('stream','ProofNet'),('stream','Putnam')]:
  for arm in ARMS:
   for fold in map(str,range(5)):yield mode,ds,fold,arm
 for mode in ['offline','stream']:
  for arm in ARMS:yield mode,'ProofNet','frozen',arm
def unit(mode,ds,fold,arm):
 dest=folder(mode,ds,fold,arm);dest.mkdir(parents=True,exist_ok=True)
 if done((mode,ds,fold,arm)):return True
 rr=c.load('goedel',ds,mode);sp=splits(ds,mode);start=time.time();limits={}
 if mode=='offline' and ds=='ProofNet' and fold=='frozen':
  errors={lam:float(np.mean([c.read(folder(mode,ds,str(i),arm)/'result.json')['inner_nll'][str(lam)] for i in range(5)])) for lam in c.LAMS}
  tr=rr;te=c.load('goedel','Putnam',mode)
 else:
  sp=sp['frozen'] if fold=='frozen' else sp['outer'][int(fold)]
  tr=c.subset(rr,sp['train_groups']);te=c.load('goedel','Putnam',mode) if fold=='frozen' else c.subset(rr,sp['test_groups'])
  pool={lam:[] for lam in c.LAMS}
  for ins in sp['inner']:
   a=c.subset(tr,ins['train_groups']);b=c.subset(tr,ins['validation_groups'])
   assert a and b and not {r['group'] for r in a}&{r['group'] for r in b}
   pp=None
   for lam in c.LAMS:
    path=dest/('inner-'+str(ins['fold'])+'-'+str(lam)+'.json')
    if path.exists():d=c.read(path)
    else:
     if pp is None:pp=prep(a,mode,arm);A=design(a,pp,arm);B=design(b,pp,arm)
     fit=c.train(a,A,mode,lam);d=dict(fit=fit,predictions=c.predict(b,B,fit,mode,arm),train_groups=ins['train_groups'],validation_groups=ins['validation_groups'])
     c.save(path,d)
    pool[lam]+=d['predictions']
    if time.time()>float(os.getenv('LOCALIZER_DEADLINE','inf')):return False
  errors={lam:c.groupmean(ps,'nll') for lam,ps in pool.items()}
 assert tr and te and not {r['group'] for r in tr}&{r['group'] for r in te}
 best=min(errors.values());lam=max(k for k,v in errors.items() if v<=best+1e-10)
 pp=prep(tr,mode,arm);A=design(tr,pp,arm);B=design(te,pp,arm);fit=c.train(tr,A,mode,lam);ps=c.predict(te,B,fit,mode,arm)
 if mode=='stream':limits=c.thresholds(pool[lam],ds);c.alarms(ps,limits)
 reproduction=None
 if mode=='offline' and ds=='ProofNet' and arm=='PST':
  old=c.read(c.checked(ROOT/'runs/localizer_feature_ablation_20261113_v1/type_length_v2/goedel'/fold/'predictions.json'))
  old={r['trace_id']:r['PST'] for r in old}
  reproduction=max(float(np.max(abs(np.asarray(p['probability'])-old[p['trace_id']]['probability']))) for p in ps)
  assert reproduction<2e-6,('PST reproduction',fold,reproduction)
 c.save(dest/'result.json',dict(model='goedel',mode=mode,train_dataset=ds,fold=fold,arm=arm,fit=fit,preprocessor=pp,selected_lambda=lam,inner_nll=errors,
 thresholds=limits,train_groups=sorted({r['group'] for r in tr}),test_groups=sorted({r['group'] for r in te}),dimension=A.shape[1],seconds=time.time()-start,PST_reproduction_max_error=reproduction))
 c.save(dest/'predictions.json',ps);manifest(dest,dict(stage='fit',unit=[mode,ds,fold,arm],removed_feature='log_tokens'))
 print('DONE',mode,ds,fold,arm,round(time.time()-start,2),flush=True);return True
def guard():
 f=c.read(HERE/'freeze.json')
 for p,h in f.items():assert c.sha(p)==h,('source changed',p)
def pool():
 guard();assert (OUT/'preflight/manifest.json').exists()
 deadline=time.time()+6400;claims=OUT/'claims';claims.mkdir(exist_ok=True);fails=OUT/'failures';fails.mkdir(exist_ok=True)
 for u in units():
  key='--'.join(u);cl=claims/key
  if done(u) or not ready(u) or (fails/(key+'.json')).exists():continue
  try:cl.mkdir()
  except FileExistsError:continue
  c.save(cl/'owner.json',dict(job=os.environ['SLURM_JOB_ID'],array=os.getenv('SLURM_ARRAY_TASK_ID'),unit=u))
  print('CLAIM',u,flush=True)
  rc=subprocess.call([sys.executable,str(HERE/'ablation.py'),'unit',*u],env=dict(os.environ,LOCALIZER_DEADLINE=str(deadline-180)))
  (cl/'owner.json').unlink();cl.rmdir()
  if rc==75 or time.time()>deadline-240:sys.exit(75)
  if rc:
   c.save(fails/(key+'.json'),dict(unit=u,returncode=rc,job=os.getenv('SLURM_JOB_ID')));sys.exit(rc)
 print('POOL_END','completed',sum(done(u) for u in units()),'planned',len(list(units())),flush=True)
if __name__=='__main__':
 assert os.getenv('SLURM_JOB_ID')
 if sys.argv[1]=='pool':pool()
 elif sys.argv[1]=='unit':
  guard()
  if unit(*sys.argv[2:]) is False:sys.exit(75)
