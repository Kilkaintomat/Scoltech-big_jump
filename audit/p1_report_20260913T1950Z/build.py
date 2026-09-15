from pathlib import Path
import base64, collections, csv, datetime, hashlib, html, json, math, os, re, shutil, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=Path('/beegfs/home/denis.rakhmankin/onebigjump')
OUT=Path(__file__).parent
E=OUT/'evidence'; E.mkdir(exist_ok=True)
FIG=OUT/'figures'; FIG.mkdir(exist_ok=True)
EX=OUT/'examples'; EX.mkdir(exist_ok=True)
MODELS=['deepseek','goedel','kimina']
NAMES={'deepseek':'DeepSeek','goedel':'Goedel','kimina':'Kimina'}
captured=datetime.datetime.now(datetime.timezone.utc).isoformat()
sources=[]
def capture(path,destination=None):
    p=ROOT/path if not Path(path).is_absolute() else Path(path)
    raw=p.read_bytes()
    sources.append({'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'mtime_utc':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat()})
    if destination:
        d=OUT/destination; d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(raw)
    return raw
def obj(path,destination=None): return json.loads(capture(path,destination))
def writejson(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)),encoding='utf8')
def pct(a,b):return 100*a/b if b else None
def num(x):
    if x is None:return '—'
    if isinstance(x,(float,np.floating)):
        if not np.isfinite(x):return '—'
        return ('%.5g'%x).replace('.',',')
    return str(x)
def table(headers,rows):
    def safe(x):return str(x).replace('|','/').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(map(safe,headers))+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(safe(x) for x in row)+' |' for row in rows])
def savecsv(path,rows):
    if not rows:return
    pd.DataFrame(rows).to_csv(path,index=False,encoding='utf-8-sig')
summary={'captured_utc':captured,'scope':'Report of existing P1 results. No proof generation, Lean replay, or estimator refitting in this report job. New calculations are descriptive tabulation and plotting.','models':{},'checks':[]}
all_est=[];stability=[];descriptive=[];main_compact=[];pilot_compact=[];primary={};tables={};labels={};protocols={}
for model in MODELS:
    base=Path('runs/lean_reverification_20260913_local')/model
    protocol=obj(base/'pilot/protocol.json',Path('evidence')/model/'protocol.json');protocols[model]=protocol
    metrics=obj(base/'pilot/analysis/metrics.json',Path('evidence')/model/'analysis-metrics.json')
    obj(base/'pilot/analysis/manifest.json',Path('evidence')/model/'analysis-manifest.json')
    calibration=obj(base/'pilot/measurement/calibration.json',Path('evidence')/model/'calibration.json')
    capture(base/'pilot/measurement/deviations.parquet',Path('evidence')/model/'deviations.parquet')
    df=pd.read_parquet(E/model/'deviations.parquet'); tables[model]=df
    rows=[json.loads(line) for line in capture(base/'pilot/verification/labels.jsonl',Path('evidence')/model/'pilot-labels.jsonl').splitlines() if line.strip()]
    labels[model]={r['trace_id']:r for r in rows}
    obj(base/'pilot/verification/manifest.json',Path('evidence')/model/'verification-manifest.json')
    obj(base/'inputs/input-versions.json',Path('evidence')/model/'input-versions.json')
    totals=[]
    for f in sorted((ROOT/base/'main/verification').glob('shard-*/labels.jsonl')):
        raw=capture(f); skipped=0
        for line in raw.splitlines():
            try:r=json.loads(line)
            except ValueError:skipped+=1;continue
            s={k:r.get(k) for k in ['trace_id','problem_id','temperature','attempt_index','role','task_family','category','t_star','whole_proof_ok','replay_ok','unexplained_disagreement','row_sha256','elapsed_s']}
            s.update(model=model,L=len(r.get('steps',[])),n_pre=sum(x.get('status')=='ok' and r.get('t_star') is not None and x['index']<r['t_star'] for x in r.get('steps',[])),journal=str(f.relative_to(ROOT)))
            totals.append(s)
        if skipped:summary['checks'].append({'partial_lines_skipped':skipped,'path':str(f)})
    assert len(totals)==len({x['trace_id'] for x in totals}),model
    main_compact+=totals
    for r in rows:
        pilot_compact.append({**{k:r.get(k) for k in ['trace_id','problem_id','temperature','attempt_index','role','task_family','category','t_star','whole_proof_ok','replay_ok']},'model':model,'L':len(r.get('steps',[])),'n_pre':sum(x.get('status')=='ok' and r.get('t_star') is not None and x['index']<r['t_star'] for x in r.get('steps',[]))})
    def population(rs):
        cats=collections.Counter(r['category'] for r in rs); local=[r for r in rs if r['category']=='localized_tactic_failure']
        return {'n':len(rs),'categories':dict(cats),'verified_pct':pct(cats['verified'],len(rs)),'localized_pct':pct(cats['localized_tactic_failure'],len(rs)),'eligible_pct':pct(cats['verified']+cats['localized_tactic_failure'],len(rs)),'local_with_pre':sum(r.get('t_star',0)>0 for r in local),'local_with_pre_pct':pct(sum(r.get('t_star',0)>0 for r in local),len(local)),'distinct_tasks':len({r['problem_id'] for r in rs})}
    summary['models'][model]={'main':population(totals),'pilot':population(rows),'pilot_flow':{k:v for k,v in metrics.items() if k!='cells'},'calibration':calibration,'main_analysis_available':(ROOT/base/'main/analysis/metrics.json').exists()}
    for cell in metrics['cells']:
        if cell['temperature']==protocol['primary_temperature'] and cell['layer']==protocol['primary_layer'] and cell['statistic']==protocol['primary_statistic']:primary[model]=cell
        cell_df=df[(df.temperature==cell['temperature'])&(df.layer==cell['layer'])&(df.statistic==cell['statistic'])&(df.role=='evaluation')&df.primary_eligible]
        ref=cell_df[cell_df.outcome=='refuted']
        subsets={'verified':cell_df[cell_df.outcome=='verified'],'refuted_all':ref,'pre':ref[ref.t<ref.t_star],'at':ref[ref.t==ref.t_star],'post':ref[ref.t>ref.t_star],'at_post':ref[ref.t>=ref.t_star]}
        for variant in ['P1','P1_exclude_first']:
            for group,fit in cell[variant].items():
                part=subsets[group]
                if variant=='P1_exclude_first':part=part[part.t>0]
                assert len(part)==fit['n_steps'],(model,variant,group,len(part),fit['n_steps'])
                assert int((part.z>0).sum())==fit['n_positive']
                rec={'model':model,'temperature':cell['temperature'],'layer_0based':cell['layer'],'block_1based':cell['layer']+1,'statistic':cell['statistic'],'variant':variant,'group':group,**{k:fit.get(k) for k in ['n_steps','n_positive','n_tasks','n_traces','tail_tasks','k','hill','moment','gpd','fit_status','decision']},'ci':json.dumps(fit.get('ci')),'k_method':fit.get('k_selection',{}).get('method'),'ks_k':fit.get('secondary_ks',{}).get('k'),'gpd_raw_gamma':fit.get('gpd_fit',{}).get('gamma'),'gpd_sigma':fit.get('gpd_fit',{}).get('sigma'),'gpd_threshold':fit.get('gpd_fit',{}).get('threshold'),'gpd_converged':fit.get('gpd_fit',{}).get('converged'),'fit_errors':json.dumps(fit.get('fit_errors',{}),ensure_ascii=False)}
                all_est.append(rec)
                finite=part.z.to_numpy(dtype=float);finite=finite[np.isfinite(finite)]
                stats={k:rec[k] for k in ['model','temperature','block_1based','statistic','variant','group','n_steps','n_tasks','n_traces']}
                stats.update(n_finite=len(finite),n_zero=int((finite==0).sum()))
                if len(finite):
                    stats.update(mean=float(np.mean(finite)),std_sample=float(np.std(finite,ddof=1)) if len(finite)>1 else None,minimum=float(np.min(finite)),q25=float(np.quantile(finite,.25)),median=float(np.median(finite)),q75=float(np.quantile(finite,.75)),q90=float(np.quantile(finite,.9)),q95=float(np.quantile(finite,.95)),maximum=float(np.max(finite)))
                descriptive.append(stats)
                s=fit.get('stability',{})
                for j,k in enumerate(s.get('k',[])):
                    stability.append({**{x:rec[x] for x in ['model','temperature','block_1based','statistic','variant','group']},'k':k,'hill':s['hill'][j],'moment':s['moment'][j],'bands_available':s.get('bands') is not None})
    print('READ',model,summary['models'][model]['main']['n'],flush=True)
assert len(all_est)==648,len(all_est)
savecsv(OUT/'p1_all_estimates.csv',all_est);savecsv(OUT/'p1_stability.csv',stability);savecsv(OUT/'p1_descriptive.csv',descriptive)
savecsv(OUT/'main_attempts_snapshot.csv',main_compact);savecsv(OUT/'pilot_attempts.csv',pilot_compact)
summary['checks'].append({'all_p1_groups_match_saved_step_table':True,'group_results':len(all_est),'configurations':54})
summary['primary']=primary
mdf=pd.DataFrame(main_compact)
complete={}
for model in MODELS:
    sub=mdf[mdf.model==model]; complete[model]=set()
    for pid,g in sub.groupby('problem_id'):
        if len(g)==16 and dict(g.groupby('temperature').size())=={0.6:8,1.0:8}:complete[model].add(pid)
common=set.intersection(*complete.values())
cohort=mdf[mdf.problem_id.isin(common)]
summary['matched_tasks']=len(common);summary['matched_cohort']={};families=[]
for model in MODELS:
    sub=cohort[cohort.model==model];cats=sub.category.value_counts().to_dict()
    summary['matched_cohort'][model]={'n':len(sub),'categories':cats,'tasks_solved_at_least_once':sub[sub.category=='verified'].problem_id.nunique(),'verified_pct':pct(cats.get('verified',0),len(sub)),'localized_pct':pct(cats.get('localized_tactic_failure',0),len(sub)),'eligible_pct':pct(cats.get('verified',0)+cats.get('localized_tactic_failure',0),len(sub))}
    for fam,g in sub.groupby('task_family'):
        families.append({'model':model,'family':fam,'tasks':g.problem_id.nunique(),'attempts':len(g),'verified':int((g.category=='verified').sum()),'verified_pct':float((g.category=='verified').mean()*100),'localized':int((g.category=='localized_tactic_failure').sum()),'truncated':int((g.category=='generation_truncation').sum())})
savecsv(OUT/'matched_task_families.csv',families)
summary['family_statistics']=families
controls=obj('runs/expansion_20260911/calibration-summary/metrics.json','evidence/p1-controls.json')
summary['p1_controls']={k:v['P1'] for k,v in controls['scenarios'].items()}
obj('runs/expansion_20260911/calibration-summary/manifest.json','evidence/p1-controls-manifest.json')
queue=obj('runs/lean_reverification_20260913_local/queue.json','evidence/main-queue.json')
summary['queue_counts']=queue.get('counts')
summary['main_stage_status']={k:{x:v.get(x) for x in ['state','job_id','dependencies']} for k,v in queue['tasks'].items() if 'main-' in k and 'generate' not in k}
whitening={}
for model in MODELS:
    whitening[model]={}
    for variant in ['01','04']:
        path=Path('runs/controls_20260913_local/pilot')/model/('whitening-'+variant)/'metrics.json'
        if (ROOT/path).exists():whitening[model][variant]=obj(path,Path('evidence')/model/('whitening-'+variant+'.json'))
summary['secondary_whitening_controls']=whitening
examples=[('deepseek','pilot:mathd_algebra_433:T0.6:a01','deepseek_sqrt'),('kimina','pilot:numbertheory_aneqprodakp4_anmsqrtanp1eq2:T1.0:a00','kimina_sequence')]
example_summaries=[]
for model,tid,slug in examples:
    lab=labels[model][tid];path=EX/slug;path.mkdir(exist_ok=True)
    base=Path('runs/lean_reverification_20260913_local')/model
    samples=[]
    for f in sorted((ROOT/base/'pilot/generation').glob('shard-*/samples.jsonl')):
        raw=capture(f)
        for line in raw.splitlines():
            r=json.loads(line)
            if r['trace_id']==tid:samples.append(r)
    assert len(samples)==1
    sample=samples[0]
    (path/'completion.txt').write_text(sample['completion'],encoding='utf8')
    lo,hi=lab['formal_span']; original=sample['completion'][lo:hi]
    (path/'generated.lean').write_text(original,encoding='utf8')
    (path/'checked.lean').write_text('import Mathlib\nimport Aesop\n'+lab['replay']['header']+lab['body'],encoding='utf8')
    writejson(path/'label.json',lab)
    writejson(path/'generation-metadata.json',{k:v for k,v in sample.items() if k not in ['completion','prompt_token_ids','completion_token_ids','token_logprobs','completion_logprobs']})
    tf=tables[model]; prim_layer=protocols[model]['primary_layer'];arr=tf[(tf.trace_id==tid)&(tf.layer==prim_layer)]
    step_rows=[]
    for step in lab['steps']:
        i=step['index'];row={'step_1based':i+1,'step_0based':i,'region':'pre' if i<lab['t_star'] else 'at' if i==lab['t_star'] else 'post','status':step['status'],'source_line_start_0based':step['line_start'],'source_line_end_0based':step['line_end'],'tactic':step['tactic'],'lean_message':step['message']}
        ss=arr[arr.t==i]
        for stat in ['raw','whitened','innovation']:
            vals=ss[ss.statistic==stat].z.to_list(); row[stat]=vals[0] if vals else None
        row['surprisal']=float(ss.surprisal.iloc[0]) if len(ss) else None
        step_rows.append(row)
    savecsv(path/'steps.csv',step_rows)
    item={'model':model,'trace_id':tid,'slug':slug,'temperature':lab['temperature'],'role':lab['role'],'L':len(lab['steps']),'t_star_0based':lab['t_star'],'failure_step_1based':lab['t_star']+1,'n_pre':lab['t_star'],'n_post':len(lab['steps'])-lab['t_star']-1,'whole_proof_ok':lab['whole_proof_ok'],'replay_ok':lab['replay_ok'],'error':lab['steps'][lab['t_star']]['message'],'steps':step_rows,'body':lab['body'],'header':lab['replay']['header'],'original_code':original,'selection':'Chosen for concise contrasting failure mechanisms and nonempty pre; not a random sample and not evidence of localization accuracy.'}
    item['score_argmax_step_1based']={stat:max(step_rows,key=lambda x:x[stat])['step_1based'] for stat in ['raw','whitened','innovation'] if all(x[stat] is not None for x in step_rows)}
    example_summaries.append(item)
summary['examples']=example_summaries
summary['arithmetic_check']={'actual_a5':5*9*49*2209+4,'model_a5':4874049,'difference':4874049-(5*9*49*2209+4)}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(8,4))
x=np.arange(3);bottom=np.zeros(3)
for cat,label,color in [('verified','Принято','#25785e'),('localized_tactic_failure','Локализован отказ','#c46a32'),('other','Другие исходы','#b7bcc7')]:
    values=[]
    for m in MODELS:
        r=summary['models'][m]['main'];c=r['categories'];v=c.get(cat,0) if cat!='other' else r['n']-c.get('verified',0)-c.get('localized_tactic_failure',0)
        values.append(100*v/r['n'])
    ax.bar(x,values,bottom=bottom,label=label,color=color)
    for i,v in enumerate(values):ax.text(i,bottom[i]+v/2,'%.1f%%'%v,ha='center',va='center',color='white' if cat!='other' else '#202733')
    bottom+=values
ax.set_xticks(x,[NAMES[m] for m in MODELS]);ax.set_ylim(0,100);ax.set_ylabel('% уже обработанных ответов');ax.set_title('Основная серия: незавершённые выборки разного состава');ax.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=3);fig.tight_layout();fig.savefig(FIG/'main_outcomes.png',dpi=180,bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4))
gs=['verified','pre','at','post'];xx=np.arange(4)
for j,m in enumerate(MODELS):
    vals=[primary[m]['P1'][g]['n_steps'] for g in gs]
    ax.bar(xx+(j-1)*.24,vals,width=.24,label=NAMES[m])
ax.set_xticks(xx,['Принятые','До отказа','На отказе','После отказа']);ax.set_ylabel('Число шагов');ax.set_title('P1: основная настройка пилота, T=0,6, whitening');ax.legend();fig.tight_layout();fig.savefig(FIG/'primary_counts.png',dpi=180);plt.close(fig)
s=primary['kimina']['P1']['refuted_all']['stability']
fig,axes=plt.subplots(1,2,figsize=(9,3.5))
for ax,est,label in zip(axes,['hill','moment'],['Hill','Моментная оценка']):
    ax.plot(s['k'],s[est],marker='o');ax.axhline(0,color='#888',lw=1);ax.set_xlabel('k — число верхних наблюдений');ax.set_ylabel('Оценка γ');ax.set_title(label)
fig.suptitle('Kimina: 54 шага / 3 задачи. Интервалов неопределённости нет.');fig.tight_layout();fig.savefig(FIG/'primary_stability.png',dpi=180);plt.close(fig)
fig,axes=plt.subplots(3,2,figsize=(10,8))
for col,ex in enumerate(example_summaries):
    for row,stat in enumerate(['raw','whitened','innovation']):
        ax=axes[row,col];rs=ex['steps'];x=[r['step_1based'] for r in rs];y=[r[stat] for r in rs];err=ex['failure_step_1based']
        ax.plot(x,y,'o-',ms=4);ax.axvline(err,color='#b34835',ls='--');ax.axvspan(err+.1,max(x)+.2,color='#b7bcc7',alpha=.2);ax.set_ylabel(stat);ax.set_xticks(x);ax.set_xlabel('Шаг (нумерация с 1)')
        if row==0:ax.set_title(NAMES[ex['model']]+'; T='+str(ex['temperature'])+'; отказ на шаге '+str(err))
fig.suptitle('Два выбранных примера; линия — первый отказ Lean, серое — unreached');fig.tight_layout();fig.savefig(FIG/'example_trajectories.png',dpi=180);plt.close(fig)
writejson(OUT/'summary.json',summary)
print('DATA_READY',json.dumps({'main':{m:summary['models'][m]['main'] for m in MODELS},'matched_tasks':len(common),'matched_cohort':summary['matched_cohort'],'example_argmax':[{k:e[k] for k in ['model','failure_step_1based','score_argmax_step_1based']} for e in example_summaries],'all_estimates':len(all_est),'nonempty_fits':sum(x['hill'] is not None for x in all_est)},ensure_ascii=False),flush=True)
writejson(OUT/'sources.json',sources)

