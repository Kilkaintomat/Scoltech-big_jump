"""Frozen prospective positional sensitivities; independent outputs, original primary cell preserved."""
import collections,json,os
from pathlib import Path
import numpy as np
import pandas as pd
from data import REPO,RUN as STATES,MODELS,read,atomic,digest,environment,check_source,check_manifest
HERE=REPO/"audit/segmentation_controls_20260914_v1"
QUALITY=REPO/"runs/segmentation_quality_20260914_v1"
PLAN_PATH=REPO/"audit/segmentation_quality_20260914_v1/plan.json"
ENDPOINTS=["D=-1","D=0","D=+1","window+-1"]
def trials(frame,subset):
    result=[]
    for tid,g in frame.groupby("trace_id",sort=True):
        g=g.sort_values("t");L=len(g);f=int(g.t_star.iloc[0])
        if g.t.tolist()!=list(range(L)) or not 0<=f<L:raise ValueError("noncontiguous original indices")
        if subset.startswith("error_after_first") and f==0:continue
        if subset=="both_neighbors" and not 0<f<L-1:continue
        lo=1 if subset=="error_after_first_excluding_first_increment" else 0
        z=g.z.to_numpy(float)[lo:];s=g.surprisal.to_numpy(float)[lo:]
        if not len(z) or not np.isfinite(z).all() or not np.isfinite(s).all():raise ValueError("missing paired scores")
        result.append({"trace_id":tid,"problem_id":str(g.prompt_id.iloc[0]),"task_family":str(g.task_family.iloc[0]),
          "L":L,"f":f,"lo":lo,"j":int(np.argmax(z))+lo,"s":int(np.argmax(s))+lo,
          "tied_jump":int(np.sum(z==z.max()))>1,"tied_surprisal":int(np.sum(s==s.max()))>1})
    return result
def features(rows):
    if not rows:return np.empty((0,4,4)),np.empty((0,4),bool)
    f=np.asarray([r["f"] for r in rows]);L=np.asarray([r["L"] for r in rows]);lo=np.asarray([r["lo"] for r in rows])
    offsets=np.asarray([-1,0,1]);available=(f[:,None]+offsets>=lo[:,None])&(f[:,None]+offsets<L[:,None])
    availability=np.column_stack([available,np.ones(len(rows),bool)])
    values=[]
    for key in ["j","s","lo"]:
        D=np.asarray([r[key] for r in rows])-f
        values.append(np.column_stack([D[:,None]==offsets,np.abs(D)<=1]).astype(float))
    chance=np.column_stack([available,available.sum(1)])/(L-lo)[:,None]
    # method axis: jump, same-trace surprisal, always first eligible, uniform.
    return np.stack([*values,chance],axis=1),availability
def bootstrap(rows,values,replicates=2000,min_tasks=20,seed=2026091401):
    problems=sorted({r["problem_id"] for r in rows})
    if len(problems)<min_tasks:return {"available":False,"tasks":len(problems),"reason":"fewer than minimum independent tasks","ci":None}
    ix={p:i for i,p in enumerate(problems)};totals=np.zeros((len(problems),values.shape[1]));counts=np.zeros(len(problems))
    for r,v in zip(rows,values):
        i=ix[r["problem_id"]];totals[i]+=v;counts[i]+=1
    rng=np.random.default_rng(seed);weights=rng.multinomial(len(problems),np.full(len(problems),1/len(problems)),size=replicates)
    samples=(weights@totals)/(weights@counts)[:,None]
    return {"available":True,"tasks":len(problems),"unit":"problem","replicates":replicates,"ci":np.quantile(samples,[.025,.975],axis=0).T.tolist()}
def describe(rows,plan):
    x,avail=features(rows);n=len(rows);points={}
    for k,endpoint in enumerate(ENDPOINTS):
        metrics=np.column_stack([x[:,0,k],x[:,1,k],x[:,2,k],x[:,3,k],x[:,0,k]-x[:,1,k],
                  x[:,0,k]-x[:,3,k],x[:,0,k]-x[:,2,k]])
        names=["jump","surprisal","always_first_eligible","uniform","jump_minus_surprisal","jump_minus_uniform","jump_minus_always_first"]
        b=bootstrap(rows,metrics,plan["bootstrap"]["replicates"],plan["bootstrap"]["min_tasks"],plan["positional_null"]["seed"])
        rate=dict(zip(names,metrics.mean(0).tolist())) if n else {key:None for key in names}
        use=avail[:,k]
        points[endpoint]={"n":n,"rates":rate,"task_bootstrap":b,"ci_metric_order":names,"offset_available_n":int(use.sum()),
            "rates_when_offset_available":dict(zip(names,metrics[use].mean(0).tolist())) if use.any() else None}
    return {"traces":n,"tasks":len({r["problem_id"] for r in rows}),"endpoints":points,
            "tied_jump_traces":sum(r["tied_jump"] for r in rows),"tied_surprisal_traces":sum(r["tied_surprisal"] for r in rows)}
def positional_null(rows,permutations=9999,min_tasks=20,seed=2026091401,adjust=False):
    # Deduplicate after subset restriction: exactly one original trace per independent task.
    chosen={}
    for row in sorted(rows,key=lambda r:r["trace_id"]):chosen.setdefault(row["problem_id"],row)
    strata=collections.defaultdict(list)
    for row in chosen.values():strata[(row["task_family"],row["L"])].append(row)
    groups=[g for _,g in sorted(strata.items()) if len(g)>=2];matched=[r for g in groups for r in g]
    out={"tasks_before_matching":len(chosen),"tasks":len(matched),"excluded_singleton_tasks":len(chosen)-len(matched),
         "strata":[{"family":g[0]["task_family"],"L":g[0]["L"],"tasks":len(g)} for g in groups],
         "selected_trace_ids":[r["trace_id"] for r in matched],
         "scope":"one trace per task, exact family and length; does not generalize automatically to excluded tasks"}
    if len(matched)<min_tasks:
        return {**out,"available":False,"reason":"fewer than minimum independent tasks after exact matching","pvalues":None}
    observed=features(matched)[0][:,0,:].mean(0);rng=np.random.default_rng(seed);null=np.zeros((permutations,4));base=np.arange(permutations)[:,None]
    for group in groups:
        f=np.asarray([r["f"] for r in group]);j=np.asarray([r["j"] for r in group])
        # Each row is an independent permutation; no changes to score positions or lengths.
        orders=np.asarray([rng.permutation(len(group)) for _ in range(permutations)])
        D=j[None,:]-f[orders]
        null[:,:3]+=(D[:,:,None]==np.asarray([-1,0,1])).sum(1)
        null[:,3]+=(np.abs(D)<=1).sum(1)
    null/=len(matched)
    # Integer-equivalent tolerance prevents floating rounding from dropping exact ties.
    p=(1+(null>=observed[None,:]-1e-12).sum(0))/(permutations+1)
    out.update(available=True,permutations=permutations,seed=seed,observed=observed.tolist(),expected=null.mean(0).tolist(),
               excess=(observed-null.mean(0)).tolist(),pvalues=dict(zip(ENDPOINTS,p.tolist())),
               adjusted_pvalues=dict(zip(ENDPOINTS,np.minimum(1,p*12).tolist())) if adjust else None,
               adjustment="Bonferroni 12: three models x four endpoints" if adjust else "none: descriptive sensitivity only",
               null_interval=np.quantile(null,[.025,.975],axis=0).T.tolist())
    return out
def main():
    if "SLURM_JOB_ID" not in os.environ:raise RuntimeError("Slurm allocation required")
    check_source();plan=read(PLAN_PATH);source=read(HERE/"source-manifest.json")
    for name,h in source["files"].items():
        if digest(name)!=h:raise ValueError("followup source changed")
    if plan["fixed_offsets"]!=[-1,0,1] or plan["window_radius"]!=1:raise ValueError("endpoint mismatch")
    check_manifest(QUALITY/"manifest.json")
    if read(QUALITY/"metrics.json")["gpu_adapter_blockers"]:raise RuntimeError("quality audit blockers")
    out=REPO/"runs/segmentation_controls_20260914_v1"/("controls-"+os.environ["SLURM_JOB_ID"])
    out.mkdir(parents=True,exist_ok=False);outputs=[];inputs=[PLAN_PATH,HERE/"source-manifest.json",QUALITY/"manifest.json"]
    results={}
    for model in MODELS:
        m=STATES/"measurement"/model/"manifest.json";check_manifest(m);inputs.append(m)
        path=STATES/"measurement"/model/"deviations.parquet";table=pd.read_parquet(path);inputs.append(path)
        cell=plan["primary_cells"][model]
        frame=table[(table.role=="evaluation")&(table.outcome=="refuted")&(table.temperature==cell["temperature"])&
              (table.layer==cell["layer"])&(table.statistic==cell["statistic"])]
        expected=read(QUALITY/model/"metrics.json")["by_role_temperature"]["evaluation:T0.6"]["p2_accepted"]
        if frame.trace_id.nunique()!=expected:raise ValueError("CPU audit and measured P2 population disagree")
        group={}
        for subset in plan["subsets"]:
            rows=trials(frame,subset)
            group[subset]=describe(rows,plan)
            p=plan["positional_null"]
            group[subset]["positional_null"]=positional_null(rows,p["permutations"],p["min_tasks"],p["seed"],adjust=subset=="all")
            trial_path=out/(model+"-"+subset+"-trials.json");atomic(trial_path,rows);outputs.append(trial_path)
        results[model]=group;print("CONTROLS",model,group["all"]["traces"],flush=True)
    metrics={"models":results,"scope":plan["scope"],"new_whole_proof_certificates":False,"generation_calls":0,"model_forward_calls":0}
    atomic(out/"metrics.json",metrics);outputs.append(out/"metrics.json")
    lines=["# Локализация: заранее зафиксированные проверки смещений","",
           "Новая сегментация, исходные модели и задачи. Это проверка чувствительности после исходного эксперимента.",
           "Основная ячейка: оценочные задачи, T=0.6, средний слой, whitening. Смещения не подбирались по новым активациям.",
           "D = позиция максимума минус позиция первой ошибки. Недоступные соседи не обрезаются и не переносятся.",
           "Интервалы парные, с пересэмплированием задач; условны на уже оценённом преобразовании.","",
           "| Модель | Трасс | Задач | Задач позиционного контроля | D=0 | D=+1 | Окно ±1 | Surprisal D=0 |","|---|---:|---:|---:|---:|---:|---:|---:|"]
    for model,g in results.items():
        a=g["all"];p=a["endpoints"];fmt=lambda x:f"{100*x:.1f}%" if x is not None else "NA"
        lines.append(f"| {model} | {a['traces']} | {a['tasks']} | {a['positional_null']['tasks']} | {fmt(p['D=0']['rates']['jump'])} | {fmt(p['D=+1']['rates']['jump'])} | {fmt(p['window+-1']['rates']['jump'])} | {fmt(p['D=0']['rates']['surprisal'])} |")
    lines+=["","Полные знаменатели, интервалы, p-значения и охват для каждого из четырёх срезов сохранены в metrics.json.",
        "Значимость выше случайного равномерного уровня сама по себе не доказывает связь внутри доказательства. Сравнение с позиционным нулём использует совпадающие длину и семейство задачи; вывод относится к этой подвыборке."]
    report=out/"REPORT_RU.md";report.write_text("\n\n".join(lines)+"\n",encoding="utf-8");outputs.append(report)
    atomic(out/"manifest.json",{"config":plan,"source_control":read(STATES/"source-manifest.json")["source_control"],
       "environment":environment(),"inputs":{str(p):digest(p) for p in inputs},"outputs":{str(p):digest(p) for p in outputs}})
    print("CONTROLS DONE",str(out),flush=True)
if __name__=="__main__":main()
