from ablation import *
import importlib.util,csv,shutil
assert os.getenv('SLURM_JOB_ID')
spec=importlib.util.spec_from_file_location('state_summary_helpers',c.HERE/'summarize.py')
bs=importlib.util.module_from_spec(spec);spec.loader.exec_module(bs)
OLD=ROOT/'runs/goedel_no_tactic_length_20261113_v1'
SETTINGS=[('offline','ProofNet','oof'),('offline','Putnam','oof'),('offline','ProofNet','frozen'),('stream','ProofNet','oof'),('stream','Putnam','oof'),('stream','ProofNet','frozen')]
REPORT_ARMS=['PST','PSTW','PST_deltaX','PST_u','PST_state','MD_noN','MD_noNW','MD_noN_deltaX','MD_noN_u','MD_noN_state']
def fmt(v,n=4):
 return 'NA' if v is None else format(v,'.'+str(n)+'f')
def ci(r,scale=1):
 return 'NA' if r['ci95'] is None else '['+'; '.join(fmt(v*scale,2 if scale==100 else 4) for v in r['ci95'])+']'
def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def label(ctx):
 mode,ds,ev=ctx
 return ('Полное доказательство' if mode=='offline' else 'Стриминг')+' / '+ds+(' → Putnam frozen' if ev=='frozen' else ' OOF')
def keyed(ps):
 assert len(ps)==len({p['trace_id'] for p in ps})
 return {p['trace_id']:p for p in ps}
def contrast(a,b,key):
 a,b=keyed(a),keyed(b);assert a.keys()==b.keys()
 by=collections.defaultdict(list)
 for tid,p in a.items():
  q=b[tid];assert (p['group'],p['f'],p['L'])==(q['group'],q['f'],q['L'])
  if key=='exact' and p['f'] is None:continue
  if key=='false_alarm' and p['f'] is not None:continue
  value=q['nll']-p['nll'] if key=='nll' else p['hit']-q['hit'] if key=='hit' else p['alarms']['0.1'][key]-q['alarms']['0.1'][key]
  by[p['group']].append(value)
 if not by:return dict(delta=None,groups=0,ci95=None,p=None)
 return bs.boot([np.mean(by[g]) for g in sorted(by)])
def main(tag):
 guard()
 assert all(done(u) for u in units()),'Some new fits are incomplete'
 dest=OUT/tag;dest.mkdir(exist_ok=False)
 metrics=[];contrasts=[];predictions={};diagnostics=[];folds=[]
 for ctx in SETTINGS:
  mode,ds,ev=ctx;wanted=['frozen'] if ev=='frozen' else list(map(str,range(5)))
  expected=c.load('goedel','Putnam' if ev=='frozen' else ds,mode)
  for arm in REPORT_ARMS:
   ps=[]
   for fold in wanted:
    p=(OUT if arm in ARMS else OLD)/'fits'/mode/ds/fold/arm
    data=c.read(c.checked(p/'predictions.json'))
    ps.extend(dict(r,evaluation_fold=fold) for r in data)
    if arm in ARMS:
     result=c.read(c.checked(p/'result.json'))
     assert result['preprocessor']['vector_arm']=='state'
     gradients=[result['fit']['gradient_max']]
     for f in sorted(p.glob('inner-*.json')):gradients.append(c.read(c.checked(f))['fit']['gradient_max'])
     assert max(gradients)<2e-5
     assert result['dimension']>4096
     diagnostics.append(dict(mode=mode,train_dataset=ds,fold=fold,arm=arm,selected_lambda=result['selected_lambda'],dimension=result['dimension'],seconds=result['seconds'],max_gradient=max(gradients),outer_success=result['fit']['success']))
   assert len(ps)==len(expected)==len({r['trace_id'] for r in ps})
   assert {r['trace_id'] for r in ps}=={r['trace_id'] for r in expected}
   predictions[ctx+(arm,)]=ps
   metrics.append(dict(model='goedel',mode=mode,train_dataset=ds,evaluation=ev,arm=arm,**bs.metric(ps,mode)))
  for arm in ARMS:
   base=basearm(arm);a=predictions[ctx+(arm,)];b=predictions[ctx+(base,)]
   for key in ['nll','hit' if mode=='offline' else 'exact']+(['false_alarm'] if mode=='stream' else []):
    contrasts.append(dict(mode=mode,train_dataset=ds,evaluation=ev,new=arm,base=base,metric=key,**contrast(a,b,key)))
   for fold in wanted:
    aa=[p for p in a if p['evaluation_fold']==fold];bb=[p for p in b if p['evaluation_fold']==fold]
    folds.append(dict(mode=mode,train_dataset=ds,evaluation=ev,fold=fold,arm=arm,base=base,**{'new_'+k:v for k,v in bs.metric(aa,mode).items()},**{'base_'+k:v for k,v in bs.metric(bb,mode).items()}))
 for key in ['nll','localization']:
  rows=[r for r in contrasts if r['p'] is not None and (r['metric']=='nll' if key=='nll' else r['metric'] in ['hit','exact'])]
  assert len(rows)==12
  running=0.
  for i,r in enumerate(sorted(rows,key=lambda x:x['p'])):
   running=max(running,min(1.,(12-i)*r['p']));r['holm12']=running

 # Matched comparison to E4: same model, rows, groups, splits, base columns and state coordinates.
 e4=ROOT/'runs/revision_20261107_v1/E4/goedel'
 old=c.read(c.checked(e4/'predictions.json'));oldmap=keyed(old)
 rr=c.load('goedel','ProofNet','offline');ctx=('offline','ProofNet','oof')
 assert {r['trace_id'] for r in rr}==set(oldmap)
 checks=[]
 for fi,sp in enumerate(splits('ProofNet','offline')['outer']):
  historical=c.read(c.checked(e4/('fold-'+str(fi)+'.json')))['fits']
  for name in ['train_groups','test_groups']:
   assert {'ProofNet:'+g for g in historical['outer'][name]}==set(sp[name])
  assert set(map(float,historical['errors']['state']))==set(c.LAMS)
  for h,n in zip(historical['outer']['inner'],sp['inner']):
   for name in ['train_groups','validation_groups']:
    assert {'ProofNet:'+g for g in h[name]}==set(n[name])
  tr=c.subset(rr,sp['train_groups']);te=c.subset(rr,sp['test_groups'])
  pp=c.prep(tr,'offline','state')
  names=pp['names']
  oldnames=[n+':0' if n in ['first','last'] else n for n in historical['preprocessor']['feature_names']]
  oldnames+=['dq:0','absdq:0']
  ix=[names.index(n) for n in oldnames]
  oldmean=historical['preprocessor']['mean']+historical['delta_scaler']['mean']
  oldscale=historical['preprocessor']['scale']+historical['delta_scaler']['scale']
  np.testing.assert_allclose(np.asarray(pp['mean'])[ix],oldmean,atol=1e-10,rtol=1e-10)
  np.testing.assert_allclose(np.asarray(pp['scale'])[ix],oldscale,atol=1e-10,rtol=1e-10)
  np.testing.assert_allclose(pp['vector_mean'],historical['vector_scaler']['state']['mean'],atol=1e-10,rtol=1e-10)
  np.testing.assert_allclose(pp['vector_scale'],historical['vector_scaler']['state']['scale'],atol=1e-10,rtol=1e-10)
  phi,_=c.scalar_basis(te,pp);A=((phi-pp['mean'])/pp['scale'])[:,ix]
  V=(c.vector_raw(te,'state')-pp['vector_mean'])/pp['vector_scale']
  out=c.predict(te,np.column_stack([A,V]),historical['outer_fits']['state'],'offline','state')
  error=max(float(np.max(abs(np.asarray(p['probability'])-oldmap[p['trace_id']]['MD_state']['probability']))) for p in out)
  assert error<2e-7,(fi,error)
  checks.append(dict(fold=fi,identical_groups=True,identical_scalers=True,state_prediction_max_error=error))
 oldps={}
 for arm in ['MD','MDW','MD_state','MD_increment']:
  oldps[arm]=[{**p[arm],'trace_id':p['trace_id'],'group':'ProofNet:'+p['group'],'problem_id':p['problem_id'],'L':p['L'],'K':p['L'],'f':p['f'],'evaluation_fold':str(p['outer_fold'])} for p in old]
  # Nested historical prediction dictionaries may carry the unprefixed group.
  for p in oldps[arm]:p['group']='ProofNet:'+oldmap[p['trace_id']]['group']
 matched_metrics=[dict(length='with',arm=arm,**bs.metric(oldps[arm],'offline')) for arm in oldps]
 for arm in ['MD_noN','MD_noNW','MD_noN_state','MD_noN_deltaX']:
  matched_metrics.append(dict(length='without',arm=arm,**bs.metric(predictions[ctx+(arm,)],'offline')))
 interaction=[]
 A=keyed(predictions[ctx+('MD_noN_state',)]);B=keyed(predictions[ctx+('MD_noN',)])
 C=keyed(oldps['MD_state']);D=keyed(oldps['MD'])
 assert A.keys()==B.keys()==C.keys()==D.keys()
 for key in ['hit','nll']:
  for kind in ['with_length_state_gain','without_length_state_gain','gain_difference','state_change_on_removing_length','baseline_change_on_removing_length']:
   by=collections.defaultdict(list)
   for tid,a in A.items():
    b,c0,d=B[tid],C[tid],D[tid]
    assert len({p['group'] for p in [a,b,c0,d]})==1
    assert len({p['f'] for p in [a,b,c0,d]})==1
    assert len({p['evaluation_fold'] for p in [a,b,c0,d]})==1
    if key=='hit':
     after=a[key]-b[key];before=c0[key]-d[key];state_change=a[key]-c0[key];base_change=b[key]-d[key]
    else:
     after=b[key]-a[key];before=d[key]-c0[key];state_change=c0[key]-a[key];base_change=d[key]-b[key]
    val={'with_length_state_gain':before,'without_length_state_gain':after,'gain_difference':after-before,'state_change_on_removing_length':state_change,'baseline_change_on_removing_length':base_change}[kind]
    by[a['group']].append(val)
   interaction.append(dict(metric=key,comparison=kind,**bs.boot([np.mean(by[g]) for g in sorted(by)])))
 for name,rows in [('metrics',metrics),('contrasts',contrasts),('folds',folds),('fit_diagnostics',diagnostics),('matched_length_metrics',matched_metrics),('matched_length_contrasts',interaction)]:
  c.save(dest/(name+'.json'),rows);bs.table(dest/(name+'.csv'),rows)
 c.save(dest/'compatibility_checks.json',checks)
 shutil.copy2(HERE/'PROTOCOL.md',dest/'PROTOCOL.md')
 preflight=c.read(c.checked(OUT/'preflight/checks.json'))
 status=dict(new_completed_fits=len(diagnostics),planned_new_fits=44,new_cells=12,total_cells=len(metrics),reused_fits=176,failures=[c.read(p) for p in (OUT/'failures').glob('*.json')],preflight=preflight,compatibility_checks=checks,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),submission=c.read(OUT/'submission_repair.json'))
 assert status['new_completed_fits']==44 and status['total_cells']==60 and not status['failures']
 c.save(dest/'status.json',status)
 def getmetric(ctx,arm):
  return next(r for r in metrics if (r['mode'],r['train_dataset'],r['evaluation'],r['arm'])==ctx+(arm,))
 def getcontrast(ctx,arm,key):
  return next(r for r in contrasts if (r['mode'],r['train_dataset'],r['evaluation'],r['new'],r['metric'])==ctx+(arm,key))
 primary=[]
 for arm in ARMS:
  base=basearm(arm);a=getmetric(ctx,arm);b=getmetric(ctx,base);hit=getcontrast(ctx,arm,'hit');nll=getcontrast(ctx,arm,'nll')
  primary.append([arm,fmt(100*b['hit'],2),fmt(100*a['hit'],2),fmt(100*hit['delta'],2),ci(hit,100),fmt(b['nll']),fmt(a['nll']),fmt(nll['delta']),ci(nll)])
 primary_table=table(['Добавка к baseline','Hit baseline, %','Hit + X, %','Δ Hit, п.п.','95% CI Δ Hit','NLL baseline','NLL + X','Выигрыш NLL','95% CI NLL'],primary)
 interpretation=('Удаление явной длины меняет и baseline, и модель с состоянием: положительная разница приростов может возникнуть из-за ослабления baseline. Для прямой проверки ниже показаны обе абсолютные модели и парная разница разниц. Это проверка предсказательной ценности конкретного регуляризованного линейного локализатора; она не устанавливает причинную роль длины и не исключает её косвенное кодирование в X или типе тактики.')
 intro=['# Полное состояние Goedel без длины тактики: завершённое дополнение','',
 'Прежняя абляция не была недосчитана из-за очереди: все 176 запланированных fits завершились, но в плане отсутствовал X. Теперь добавлены PST_state и MD_noN_state: 44 новых внешних/frozen fits, 12 новых ячеек; вместе с прежними вариантами — 60 ячеек. Старые результаты не изменялись.','',
 '## Ответ для Goedel / ProofNet / полного доказательства','',primary_table,'',interpretation,'',
 '## Постановка','',
 'PST = позиция + средний token surprisal + тип тактики. MD_noN дополнительно содержит знаковое и абсолютное соседнее изменение surprisal. Суффикс state добавляет все 4096 координат X_t после decoder block 17 (индексация с нуля) на последнем токене текущей тактики. Это исходное полное состояние; его координаты центрируются и масштабируются только по train. Веса LLM не меняются. Ни приращение, ни единичное направление не подменяют X.','',
 'Удалён log(1+число токенов тактики) со всеми сплайн-столбцами. Offline сохраняет длину всего доказательства через t/L и признак последнего шага. Offline выбирает один первый отказ среди всех сохранённых шагов ошибочного доказательства, включая суффикс после отказа. Streaming работает с текущим префиксом до первого отказа включительно при архивных AST-границах; итоговая длина и будущие шаги не используются. Это обнаружение текущего формального отказа, не предсказание будущего до появления текущей тактики.','',
 'Сохранены прежние group splits: 5 внешних и 3 внутренних фолда, одинаковые задачи и попытки, lambda grid 0.0001/0.001/0.01/0.1/1/10, выбор по inner NLL. Координаты и сплайны fit только на train; одинаковый вес задач, внутри — попыток; в streaming внутри попытки — шагов. Новые OOF предсказания покрывают все отложенные попытки ровно один раз.','',
 '[Протокол](PROTOCOL.md) · [все 60 ячеек](metrics.csv) · [парные сравнения X](contrasts.csv) · [по фолдам](folds.csv) · [λ, размерности и сходимость](fit_diagnostics.csv).','',
 'Δ Hit/Exact = новый минус baseline; выигрыш NLL/BCE = baseline минус новый, положительное значение лучше. Интервалы — 10000 bootstrap задач по фиксированным OOF/frozen моделям, минимум 20 групп. Holm12 отдельно для NLL и Hit/Exact в новой семье из 12 сравнений; старый Holm24 не менялся. FPR и разница разниц ниже — дополнительные описательные контрасты без поправки на множественность.']
 lines=list(intro)
 for context in SETTINGS:
  mode,ds,ev=context;lines+=['','## '+label(context),'']
  sample=getmetric(context,'PST')
  lines+=['Попыток: '+str(sample['attempts'])+'; задач: '+str(sample['groups'])+'.','']
  if mode=='offline':
   rows=[]
   for arm in REPORT_ARMS:
    a=getmetric(context,arm);b=getmetric(context,basearm(arm))
    rows.append([arm,fmt(100*a['hit'],2),fmt(100*(a['hit']-b['hit']),2),fmt(a['nll'])])
   lines.append(table(['Вариант','Hit, %','Δ к своему baseline, п.п.','NLL'],rows))
  else:
   lines+=['Номинальная калибровка 10% по inner OOF: ProofNet — по verified-траекториям, Putnam — по принятым префиксам до отказа. Фактический FPR на тесте показан отдельно; на Putnam verified-попыток нет и FPR = NA.','']
   rows=[]
   for arm in REPORT_ARMS:
    a=getmetric(context,arm);b=getmetric(context,basearm(arm))
    rows.append([arm,fmt(100*a['exact@0.1'],2),fmt(100*(a['exact@0.1']-b['exact@0.1']),2)]+[fmt(None if a[k] is None else 100*a[k],2) for k in ['early@0.1','miss@0.1','false_alarm@0.1']]+[fmt(a['nll'])])
   lines.append(table(['Вариант','Exact, %','Δ, п.п.','Early, %','Miss, %','Verified FPR, %','BCE'],rows))
 lines+=['','## Интервалы для новой добавки полного состояния','']
 rows=[]
 for r in contrasts:
  scale=1 if r['metric']=='nll' else 100
  rows.append([label((r['mode'],r['train_dataset'],r['evaluation'])),r['new']+' − '+r['base'],r['metric'],fmt(None if r['delta'] is None else scale*r['delta']),ci(r,scale),fmt(r.get('holm12')),r['groups']])
 lines.append(table(['Условие','Контраст','Метрика','Δ','95% CI','p Holm12','Задач'],rows))
 lines+=['','## С длиной и без неё: совместимое сравнение с E4','',
 'Прежние −6,99 п.п. получены для MD_state−MD. MD включает позицию, surprisal, тип, длину тактики и два изменения surprisal. Поэтому его корректный аналог без длины — MD_noN, а не PST. В следующей таблице используются ровно те же попытки и внешние/внутренние разбиения; совместимость скалярных и векторных scalers и воспроизведение E4 из текущих состояний проверены на каждом из пяти фолдов.','']
 lines.append(table(['Длина','Вариант','Hit, %','NLL'],[[r['length'],r['arm'],fmt(100*r['hit'],2),fmt(r['nll'])] for r in matched_metrics]))
 explain={'with_length_state_gain':'Эффект X при сохранении длины','without_length_state_gain':'Эффект X после удаления длины','gain_difference':'Изменение эффекта X: без длины − с длиной','state_change_on_removing_length':'Изменение самой модели с X после удаления длины','baseline_change_on_removing_length':'Изменение самого baseline после удаления длины'}
 lines+=['','[Совместимые метрики](matched_length_metrics.csv) · [парные разницы и разница разниц](matched_length_contrasts.csv).','']
 lines.append(table(['Сравнение','Метрика','Δ','95% CI','Задач'],[[explain[r['comparison']],r['metric'],fmt(r['delta']*(100 if r['metric']=='hit' else 1)),ci(r,100 if r['metric']=='hit' else 1),r['groups']] for r in interaction]))
 lines+=['',interpretation,'','## ProofNet offline по внешним фолдам','']
 foldrows=[]
 for r in folds:
  if (r['mode'],r['train_dataset'],r['evaluation'])!=ctx:continue
  foldrows.append([r['fold'],r['arm'],r['new_groups'],fmt(100*r['base_hit'],2),fmt(100*r['new_hit'],2),fmt(100*(r['new_hit']-r['base_hit']),2),fmt(r['base_nll']-r['new_nll'])])
 lines.append(table(['Фолд','Вариант','Задач','Hit baseline, %','Hit + X, %','Δ Hit, п.п.','Выигрыш NLL'],foldrows))
 lines+=['','## Проверки и воспроизводимость','',
 'Техническая проверка подтвердила независимость итогового design от явной длины и при изменении test tokens, и при переобучении preprocessing; streaming инвариантен к изменению/удалению будущего. Исторический PST воспроизведён с максимальной ошибкой вероятности '+format(preflight['historical_PST_prediction_error'],'.3g')+'. E4 state воспроизведён во всех пяти фолдах, максимум отклонения '+format(max(r['state_prediction_max_error'] for r in checks),'.3g')+'. Все новые fits имеют конечный objective и максимальную компоненту градиента менее 2e-5.','',
 'Код и протокол: '+str(HERE)+'. Результаты: '+str(OUT)+'. Каждый fit содержит predictions.json, result.json, внутренние fits и manifest.json с входными SHA256, версиями, Slurm job и исходниками. [Сводная проверка совместимости](compatibility_checks.json) и [статус](status.json). Результаты старой серии читаются по проверенным хэшам и не переписывались.','',
 'Первая техническая попытка импортировала одноимённый preflight из родительской серии; защита от перезаписи остановила её. В production использован исправленный импорт по точному пути и отдельный успешный preflight. Неполные или неуспешные fits в метрики не включались.','',
 'Общие проверки make test и make test-all запускаются отдельным Slurm-заданием; их результат сохраняется в repository_checks. Они не подменяют специальные проверки данных и модели.']
 (dest/'REPORT_RU.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
 main_insert='## Полное состояние Goedel без длины тактики: досчёт 15 ноября\n\n'+primary_table+'\n\n'+interpretation+'\n\n'
 main_insert+='Прежние −6,99 п.п. относятся к MD_state−MD; сопоставимый вариант без длины — MD_noN_state−MD_noN. '
 z=next(r for r in interaction if r['comparison']=='without_length_state_gain' and r['metric']=='hit')
 z2=next(r for r in interaction if r['comparison']=='state_change_on_removing_length' and r['metric']=='hit')
 zb=next(r for r in interaction if r['comparison']=='baseline_change_on_removing_length' and r['metric']=='hit')
 main_insert+='В новом расчёте эффект X для этого baseline равен '+fmt(100*z['delta'],2)+' п.п., 95% CI '+ci(z,100)+'. Сама модель с X после удаления длины меняется на '+fmt(100*z2['delta'],2)+' п.п., baseline — на '+fmt(100*zb['delta'],2)+' п.п.\n\n'
 main_insert+='Завершены 44/44 новых fits; 12 новых ячеек, вместе с исторической абляцией 60/60. Полное доказательство и стриминг, ProofNet и Putnam, перенос и реальные FPR приведены в новом подробном разделе.\n'
 (dest/'summary_insert.md').write_text(main_insert,encoding='utf8')
 manifest(dest,dict(stage='state_no_length_complete_report',status=status))
 print('REPORT_READY',json.dumps(dict(folder=str(dest),primary=[r for r in contrasts if (r['mode'],r['train_dataset'],r['evaluation'])==ctx],matched=interaction),ensure_ascii=False),flush=True)
if __name__=='__main__':main(sys.argv[1])
