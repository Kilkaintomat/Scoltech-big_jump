import collections,datetime,hashlib,json,os,pathlib,platform,sys
import numpy as np
import pandas as pd
ROOT=pathlib.Path('/beegfs/home/denis.rakhmankin/onebigjump')
BASE=ROOT/'audit/offset_review_20260914_v1'
SOURCE=BASE/'result-8466720'
HERE=BASE/'boundary_review_v1'
OUT=HERE/('result-'+os.environ['SLURM_JOB_ID']);OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
manifest=json.loads((SOURCE/'manifest.json').read_text())
inputs={};models={}
rng=np.random.default_rng(2026091402)
for model in ('deepseek','goedel','kimina'):
 path=SOURCE/(model+'-traces.csv')
 assert sha(path)==manifest['outputs'][str(path)]
 inputs[str(path)]=sha(path)
 df=pd.read_csv(path);N=len(df)
 L=df.L.to_numpy();f=df.failure_step.to_numpy();j=df.max_step.to_numpy()
 assert np.all((1<=f)&(f<=L)&(1<=j)&(j<=L))
 assert np.array_equal(j-f,df.offset.to_numpy())
 left=f>1;right=f<L;both=left&right
 r={'N':N,'error_first':int((f==1).sum()),'error_last':int((f==L).sum()),'one_step':int((L==1).sum()),'offsets':{}}
 for d in (-2,-1,0,1,2):
  eligible=(f+d>=1)&(f+d<=L);hit=j-f==d
  assert not np.any(hit&~eligible)
  chance=np.where(eligible,1/L,0)
  r['offsets'][str(d)]={'hits':int(hit.sum()),'N_all':N,'eligible':int(eligible.sum()),'ineligible':int((~eligible).sum()),
    'all_rate':float(hit.mean()),'conditional_rate':float(hit[eligible].mean()) if eligible.any() else None,
    'uniform_all':float(chance.mean()),'uniform_conditional':float(np.mean(1/L[eligible])) if eligible.any() else None}
 hleft=(j-f==-1);hright=(j-f==1)
 r['interior']={'N':int(both.sum()),'tasks':int(df.loc[both,'prompt_id'].nunique()),
   'left_hits':int(hleft[both].sum()),'right_hits':int(hright[both].sum()),
   'left_rate':float(hleft[both].mean()) if both.any() else None,
   'right_rate':float(hright[both].mean()) if both.any() else None,
   'uniform_each_direction':float(np.mean(1/L[both])) if both.any() else None}
 if r['interior']['tasks']>=20:
  tasks=df.loc[both,'prompt_id'].to_numpy()
  gains=hright[both].astype(float)-hleft[both].astype(float)
  keys=sorted(set(tasks));counts=np.array([(tasks==k).sum() for k in keys])
  sums=np.array([gains[tasks==k].sum() for k in keys])
  weights=rng.multinomial(len(keys),np.ones(len(keys))/len(keys),size=4000)
  draws=(weights@sums)/(weights@counts)
  r['interior']['right_minus_left_ci95']=np.quantile(draws,[.025,.975]).tolist()
  r['interior']['ci_scope']='descriptive task bootstrap; no multiplicity or post-selection calibration'
 else:r['interior']['right_minus_left_ci95']=None
 near=np.abs(j-f)<=1
 admissible=np.minimum(L,f+1)-np.maximum(1,f-1)+1
 r['window']={'hits':int(near.sum()),'all_rate':float(near.mean()),'uniform_all':float(np.mean(admissible/L))}
 r['by_boundary']={}
 for label,mask in [('first',f==1),('last',f==L),('interior',both)]:
  r['by_boundary'][label]={'N':int(mask.sum()),'left_hits':int(hleft[mask].sum()),'right_hits':int(hright[mask].sum()),
      'window_rate':float(near[mask].mean()) if mask.any() else None}
 models[model]=r
def pct(x):return '—' if x is None else f'{100*x:.1f}%'
def table(headers,rows):
 return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)
md=['**Границы доказательства и знаменатели при сравнении смещений.**',
 'D — разность фактических позиций максимального скачка и первой ошибки. На первом шаге D<0 невозможен; '
 'на последнем D>0 невозможен. Исходная таблица показывает частоты по всем трассам: невозможное событие даёт ноль '
 'в числителе, но трасса остаётся в знаменателе. Это корректное описание общей частоты, однако не симметричное '
 'сравнение опережения и запаздывания. Переноса через границу и прижатия к ближайшему шагу нет.',
 'Условная доля для D=−1 рассчитана только там, где ошибка не первая; для D=+1 — только там, где она не последняя. '
 'Это разные подвыборки, поэтому их сравнение также не устраняет все различия состава.',
 table(['Модель','Слева: попадания / допустимо','Доля при доступном левом соседе','Справа: попадания / допустимо','Доля при доступном правом соседе'],
 [[m,f"{r['offsets']['-1']['hits']} / {r['offsets']['-1']['eligible']}",pct(r['offsets']['-1']['conditional_rate']),
   f"{r['offsets']['1']['hits']} / {r['offsets']['1']['eligible']}",pct(r['offsets']['1']['conditional_rate'])] for m,r in models.items()]),
 'Для симметричного сравнения направлений нужна одна и та же подвыборка 1<t*<L, где существуют оба соседа. '
 'Первый скачок при этом не удаляется: меняется только отбор трасс, а исходный максимум остаётся тем же.',
 table(['Модель','Трасс / задач','D=−1','D=+1','Равномерный уровень каждого направления'],
 [[m,f"{r['interior']['N']} / {r['interior']['tasks']}",pct(r['interior']['left_rate']),pct(r['interior']['right_rate']),
   pct(r['interior']['uniform_each_direction'])] for m,r in models.items()]),
 'Именно эта общая подвыборка отделяет асимметрию доступности соседей от сравнения направлений. '
 'Она не является подтверждением сигнала: остаются позиционные предпочтения максимумов, семейства задач, '
 'разная длина и ограниченное число независимых задач.',
 'Равномерный контроль в исходном аудите уже учитывал границы: для смещения d вероятность равна '
 '1{1≤t*+d≤L}/L, а для окна — числу существующих шагов в окне, делённому на L. Например, при L=3 '
 'и ошибке на первом шаге окно ±1 содержит два шага, то есть случайное покрытие равно 2/3, а не 1. '
 'Позиционный контроль переставляет ошибки между трассами одинаковой длины и также не создаёт несуществующих соседей.',
 'Частоты D=−1 и D=+1 из исходной таблицы нельзя использовать сами по себе как свидетельство направления связи. '
 'Это уточнение интерпретации; исходные числа и метки не изменены.'
]
(OUT/'BOUNDARY_NOTE_RU.md').write_text('\n\n'.join(md)+'\n')
metrics={'job':os.environ['SLURM_JOB_ID'],'scope':'descriptive boundary denominator audit','models':models}
(OUT/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
inputs[str(HERE/'audit.py')]=sha(HERE/'audit.py');inputs[str(SOURCE/'manifest.json')]=sha(SOURCE/'manifest.json')
receipt={'stage':'boundary-denominator-audit','job':os.environ['SLURM_JOB_ID'],
 'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'git_commit':os.environ.get('ONEBIGJUMP_GIT_COMMIT'),'git_dirty':bool(os.environ.get('ONEBIGJUMP_GIT_STATUS')),
 'config':{'offsets':[-2,-1,0,1,2],'common_sample':'1 < first_error < L','bootstrap_unit':'task','resamples':4000,'seed':2026091402},
 'environment':{'host':platform.node(),'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
 'inputs':inputs,'outputs':{str(p):sha(p) for p in OUT.iterdir() if p.is_file()}}
(OUT/'manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
for m,r in models.items():print(m,json.dumps(r),flush=True)
