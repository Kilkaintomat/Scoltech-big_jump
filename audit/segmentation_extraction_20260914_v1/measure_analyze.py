"""Frozen primary-cell sensitivity on new segmentation; never replaces the original run."""
import argparse,collections,concurrent.futures,gzip
from pathlib import Path
import numpy as np
import pandas as pd
from data import *
from onebigjump.e1.measurement import fit_transform,transformed_norms
from onebigjump.e1.main_analysis import analyze_cell
from onebigjump.e1.analysis import finite_json,localization
from onebigjump.experiments.dataset import validate_table,COLUMNS

def labels(export,annotation):
    obs=export["observation_rows"]
    if not obs:raise ValueError("empty semantic trace")
    if annotation["old_category"]=="verified" and annotation.get("whole_verdict_agrees"):
        if any(o["trace_label"] not in ["verified_trace","post_completion"] for o in obs):raise ValueError("inconsistent verified labels")
        return None
    if not annotation["p2_eligible"]:raise ValueError("local prefix and failure not established")
    stars=[i for i,o in enumerate(obs) if o["trace_label"]=="at"]
    if len(stars)!=1:raise ValueError("failure boundary not unique")
    star=stars[0]
    for i,o in enumerate(obs):
        expected="pre" if i<star else ("at" if i==star else "post")
        if o["trace_label"]!=expected:raise ValueError("nonabsorbing source labels")
        if any(p["trace_label"]!=expected for p in o["source_points"]):raise ValueError("ambiguous labels in merged token boundary")
    return star

def measure(model):
    check_source();config=read(RUN/"protocols"/(model+".json"));plan=read(RUN/"plan.json")
    layer=config["layers"][1];out=RUN/"measurement"/model;out.mkdir(parents=True,exist_ok=True)
    problems={r["problem_id"]:r for r in read(REPO/"runs/lean_reverification_20260913_local"/model/"inputs/problems.json")}
    selected=[];excluded=collections.Counter();manifests=[];attempts=0;seen=set()
    for task,m in plan["models"].items():
        if m!=model:continue
        folder=RUN/"shards"/f"{int(task):03d}";manifest=folder/"manifest.json"
        check_manifest(manifest);manifests.append(manifest)
        context=read(folder/"trajectories.identity.json")
        records=list(checked_rows(folder/"trajectories.jsonl",context))
        if len(records)!=plan["counts"][task]:raise ValueError("incomplete extraction")
        for row in records:
            attempts+=1;rid=row["trace_id"]
            if rid in seen:raise ValueError("duplicate trace across shards")
            seen.add(rid)
            if row["extraction_status"]!="extracted":excluded[row["extraction_status"]]+=1;continue
            annotation=row["annotation"]
            with gzip.open(row["annotation_artifact"],"rt",encoding="utf-8") as f:blob=json.load(f)
            export=blob["detail"]["export"]
            try:star=labels(export,annotation)
            except ValueError as e:excluded[str(e)]+=1;continue
            if row["sample_meta"]["role"]!=problems[row["problem_id"]]["role"]:raise ValueError("original split mismatch")
            with np.load(row["states_path"],allow_pickle=False) as z:
                states=z[f"states_{layer}"];surprisal=z["surprisal"]
            if len(states)!=len(export["observation_rows"])+1 or len(surprisal)!=len(states)-1:raise ValueError("state/label alignment")
            selected.append({"row":row,"star":star,"states":states,"surprisal":surprisal,"export":export})
    if attempts!=6672:raise ValueError("model attempt accounting mismatch")
    cal={x["row"]["problem_id"] for x in selected if x["row"]["sample_meta"]["role"]=="calibration"}
    ev={x["row"]["problem_id"] for x in selected if x["row"]["sample_meta"]["role"]=="evaluation"}
    if cal&ev:raise ValueError("calibration/evaluation leakage")
    settings=config["whitening"];diagnostics=[];table=[];outputs=[]
    for temperature in config["temperatures"]:
        group=[x for x in selected if x["row"]["sample_meta"]["temperature"]==temperature]
        calibration=[x for x in group if x["star"] is None and x["row"]["sample_meta"]["role"]=="calibration"]
        tasks=len({x["row"]["problem_id"] for x in calibration});n=sum(len(x["states"])-1 for x in calibration)
        enough=tasks>=settings["min_main_tasks"] and n>=settings["min_main_increments"]
        fit=fit_transform([x["states"] for x in calibration],settings["shrinkage"],settings["ridge"]) if enough else None
        diagnostics.append({"temperature":temperature,"layer":layer,"tasks":tasks,"increments":n,"available":enough,
                            "calibration_trace_ids":[x["row"]["trace_id"] for x in calibration],"shrinkage":settings["shrinkage"]})
        if fit is not None:
            path=out/f"transform-T{temperature}-layer{layer}.npz"
            np.savez_compressed(path,**fit);outputs.append(path)
        for x in group:
            row=x["row"];star=x["star"];L=len(x["states"])-1
            for stat,values in transformed_norms(x["states"],fit).items():
                for t,value in enumerate(values):
                    valid=star is None or t<star
                    table.append({"trace_id":row["trace_id"],"prompt_id":row["problem_id"],"model":config["model_id"],
                        "layer":layer,"statistic":stat,"t":t,"L":L,"z":float(value),"valid":valid,"t_star":star,
                        "outcome":"verified" if star is None else "refuted","surprisal":float(x["surprisal"][t]),
                        "status":"ok" if valid else ("error" if t==star else "unreached"),
                        "temperature":temperature,"task_family":problems[row["problem_id"]]["task_family"],
                        "role":row["sample_meta"]["role"],"category":row["annotation"]["old_category"],"primary_eligible":True})
    frame=pd.DataFrame(table,columns=[*COLUMNS,"status","temperature","task_family","role","category","primary_eligible"])
    if not frame.empty:validate_table(frame)
    path=out/"deviations.parquet";frame.to_parquet(path,index=False);outputs.append(path)
    atomic(out/"calibration.json",diagnostics);outputs.append(out/"calibration.json")
    metrics={"attempts":attempts,"table_traces":len(selected),"table_rows":len(frame),"exclusions":dict(excluded),
             "layer":layer,"calibration":diagnostics,"scope":"new segmentation sensitivity; original roles and parameters"}
    finish(out,metrics,[RUN/"source-manifest.json",*manifests],outputs)
    return str(path)

def analyze(model):
    path=measure(model);config=read(RUN/"protocols"/(model+".json"));layer=config["layers"][1]
    out=RUN/"analysis"/model;out.mkdir(parents=True,exist_ok=True)
    result=analyze_cell((path,config,0.6,layer,"whitened"))
    result["scope"]="sensitivity to a new source segmentation; original primary analysis remains separate"
    result["new_whole_proof_certificates"]=False
    result["semantic_evidence"]="original whole verdict plus independent local prefix/failure checks"
    atomic(out/"primary-cell.json",result)
    # Positional diagnostics stay descriptive; no searching for the largest offset.
    table=pd.read_parquet(path)
    frame=table[(table["temperature"]==0.6)&(table["layer"]==layer)&(table["statistic"]=="whitened")&(table["role"]=="evaluation")]
    diagnostic={"raw":localization(table[(table["temperature"]==0.6)&(table["statistic"]=="raw")&(table["role"]=="evaluation")],config)}
    trials=[]
    for tid,g in frame[frame["outcome"]=="refuted"].groupby("trace_id"):
        g=g.sort_values("t");L=len(g);f=int(g["t_star"].iloc[0]);j=int(np.argmax(g["z"].to_numpy()))
        trials.append({"trace_id":tid,"problem_id":g["prompt_id"].iloc[0],"L":L,"first_error":f,"max_jump":j,
                       "D":j-f,"available_left":f>0,"available_right":f<L-1,
                       "window_chance":(min(L-1,f+1)-max(0,f-1)+1)/L})
    diagnostic["offsets"]={"n":len(trials),"counts":dict(collections.Counter(str(r["D"]) for r in trials)),
                         "denominator":"all eligible traces; impossible offsets count as misses; no clipping or wraparound",
                         "both_neighbors_n":sum(r["available_left"] and r["available_right"] for r in trials),
                         "inference":"descriptive; no evidence of within-trace coupling claimed without a positional null"}
    after=[]
    for tid,g in frame.groupby("trace_id"):
        g=g.sort_values("t");star=g["t_star"].iloc[0]
        if len(g)<2 or (pd.notna(star) and star==0):continue
        g=g[g["t"]>0].copy();g["t"]-=1;g["L"]-=1
        if pd.notna(star):g["t_star"]-=1
        after.append(g)
    diagnostic["exclude_first_then_later_errors"]=localization(pd.concat(after,ignore_index=True) if after else frame.iloc[:0],config)
    atomic(out/"positional-diagnostics.json",finite_json(diagnostic))
    pd.DataFrame(trials).to_csv(out/"offset-traces.csv",index=False)
    metrics={"model":model,"decision":result["decision"],"available":result["available"],
             "P2":{k:v for k,v in result["P2"].items() if k in ["n_traces","n_tasks","chance","jump","surprisal","paired_difference"]}}
    finish(out,metrics,[RUN/"measurement"/model/"manifest.json"],[out/"primary-cell.json",out/"positional-diagnostics.json",out/"offset-traces.csv"])
    return metrics

def main():
    check_source()
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        metrics=list(pool.map(analyze,MODELS))
    atomic(RUN/"analysis-summary.json",metrics)
    lines=["# Повторный анализ с новой сегментацией","",
           "Это проверка чувствительности к разбиению исходных ответов на шаги. Исходный основной эксперимент сохранён отдельно.",
           "Сохраняются прежние задачи, разделение по задачам, температура, средний слой и параметры статистики.",
           "Результаты сами по себе не доказывают гипотезу: необходима интерпретация с учётом позиционных эффектов и ограничений разметки.","",
           "| Модель | Трасс P2 | Задач P2 | Максимум на ошибке | Surprisal | Случайный уровень |",
           "|---|---:|---:|---:|---:|---:|"]
    for m in metrics:
        p=m["P2"]
        lines.append("| "+m["model"]+" | "+str(p.get("n_traces"))+" | "+str(p.get("n_tasks"))+" | "+str(p.get("jump"))+" | "+str(p.get("surprisal"))+" | "+str(p.get("chance"))+" |")
    report=RUN/"REPORT_RU.md";report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    finish(RUN/"final",{"all_models_complete":True,"models":metrics},[RUN/"analysis"/m/"manifest.json" for m in MODELS],[RUN/"analysis-summary.json",report])
if __name__=="__main__":main()
