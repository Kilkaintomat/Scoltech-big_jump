"""Descriptive position distributions from the frozen first-error sensitivity trials."""
import csv
import datetime
import platform
import numpy as np
from stage_support import ROOT, HERE, OUT, MODELS, read, atomic, start, finish, digest
from position_histograms_render import render

STAGE = "position_histograms"

def histogram(values, bins, weights=None):
    values = np.asarray(values)
    counts = np.bincount(bins(values), weights=weights, minlength=bins.size)
    return counts

def summarize(rows, case, plan):
    n = len(rows)
    assert n > 0
    f = np.asarray([r["original_f"] for r in rows], dtype=int)
    j = np.asarray([r["original_j"] for r in rows], dtype=int)
    lengths = np.asarray([r["original_L"] for r in rows], dtype=int)
    lower = 1 if case == "later_errors_drop_first_increment" else 0
    assert np.all((f >= lower) & (f < lengths))
    assert np.all((j >= lower) & (j < lengths))
    if case != "all_errors":
        assert np.all(f > 0)
    cap = plan["absolute_individual_steps"]
    bound = plan["offset_individual_bound"]
    nbins = plan["relative_bins"]
    abs_bin = lambda v: np.minimum(v,cap)
    rel_bin = lambda v: np.minimum(np.floor(v*nbins).astype(int),nbins-1)
    offset_bin = lambda v: np.clip(v+bound+1,0,2*bound+2)
    abs_bin.size = cap+1
    rel_bin.size = nbins
    offset_bin.size = 2*bound+3
    rel_f = f/np.maximum(lengths-1,1)
    rel_j = j/np.maximum(lengths-1,1)
    data = {}
    for name, values, bins in [
        ("absolute_error",f,abs_bin),("absolute_maximum",j,abs_bin),
        ("relative_error",rel_f,rel_bin),("relative_maximum",rel_j,rel_bin),
        ("offset",j-f,offset_bin)]:
        count = histogram(values,bins)
        assert int(count.sum()) == n
        data[name] = {"counts":count.astype(int).tolist(),"percent":(100*count/n).tolist()}
    expected = {name:np.zeros(size) for name,size in
                [("absolute_uniform",abs_bin.size),("relative_uniform",rel_bin.size),("offset_uniform",offset_bin.size)]}
    for star,L in zip(f,lengths):
        candidates = np.arange(lower,L)
        weights = np.ones(len(candidates))/len(candidates)
        expected["absolute_uniform"] += histogram(candidates,abs_bin,weights)
        expected["relative_uniform"] += histogram(candidates/max(L-1,1),rel_bin,weights)
        expected["offset_uniform"] += histogram(candidates-star,offset_bin,weights)
    for name, counts in expected.items():
        assert np.isclose(counts.sum(),n)
        data[name] = {"expected_counts":counts.tolist(),"percent":(100*counts/n).tolist()}
    hits = int(np.count_nonzero(j==f))
    assert data["offset"]["counts"][bound+1] == hits
    uniform_exact = float(np.mean(1/(lengths-lower)))
    assert np.isclose(data["offset_uniform"]["percent"][bound+1],100*uniform_exact)
    return {"traces":n,"tasks":len({r["problem_id"] for r in rows}),
            "step_numbering":"Plots use 1-based original formal step numbers; saved source is zero-based.",
            "first_error_traces":int(np.count_nonzero(f==0)),
            "first_maximum_traces":int(np.count_nonzero(j==0)),
            "one_step_traces":int(np.count_nonzero(lengths==1)),
            "candidate_min_step":lower+1,
            "minimum_steps":int(lengths.min()),"maximum_steps":int(lengths.max()),
            "median_steps":float(np.median(lengths)),
            "exact_hits":hits,"exact_percent":100*hits/n,
            "uniform_exact_percent":100*uniform_exact,
            "before_percent":100*float(np.mean(j<f)),
            "after_percent":100*float(np.mean(j>f)),
            "histograms":data}

def write_csv(folder,metrics):
    path = folder/"histograms.csv"
    with path.open("w",encoding="utf-8",newline="") as file:
        writer=csv.writer(file)
        writer.writerow(["case","fold","model","kind","bin","count_or_expected_count","percent","traces","tasks"])
        for case,variants in metrics["views"].items():
            for fold,models in variants.items():
                for model,m in models.items():
                    for kind,h in m["histograms"].items():
                        if kind.startswith("absolute"):
                            bins = metrics["bins"]["absolute_labels"]
                        elif kind.startswith("relative"):
                            edges = metrics["bins"]["relative_edges"]
                            bins = [f"[{edges[i]:.2f},{edges[i+1]:.2f}{']' if i==len(edges)-2 else ')'}" for i in range(len(edges)-1)]
                        else:
                            bins = metrics["bins"]["offset_labels"]
                        counts=h.get("counts",h.get("expected_counts"))
                        for label,count,percentage in zip(bins,counts,h["percent"]):
                            writer.writerow([case,fold,model,kind,label,count,percentage,m["traces"],m["tasks"]])
    return path

def report(metrics):
    p=metrics["config"]
    lines=[
        "# Позиция первой ошибки и максимального скачка",
        "",
        "[Все графики в PDF](position_histograms_all.pdf). Отдельные PNG: [DeepSeek](deepseek.png), [Goedel](goedel.png), [Kimina](kimina.png).",
        "",
        "Для каждой модели сопоставлены одни и те же проверочные трассы с надёжно локализованной первой ошибкой. Основные рисунки используют калибровку fold0; в PDF обе заранее заданные калибровки и все три условия исключения.",
        "",
        "Синий столбец — первая ошибка Lean; оранжевый — максимум whitened-скачка. Высоты — проценты попыток, а не проценты всех шагов. Повторные попытки одной задачи имеют отдельный вес; графики описательные, доверительные интервалы здесь не строятся.",
        "",
        "Слева — исходный номер формального шага. В центре — относительная позиция: (номер шага − 1)/(длина − 1), от первого до последнего шага. Для одношаговой трассы позиция условно равна 0. Справа — парное смещение D = номер максимума − номер первой ошибки: отрицательное до ошибки, ноль в ошибке, положительное после неё.",
        "",
        "Серый пунктир — ожидаемое распределение при равномерном выборе допустимого шага отдельно в каждой той же трассе. Оно учитывает длину и исключение первого приращения, но не является контролем общей склонности модели выбирать определённые позиции.",
        "",
        "В абсолютном распределении отдельно показаны шаги "+str(p["absolute_individual_steps"])+
        " и раньше; последний столбец объединяет более поздние шаги. На графике D крайние столбцы объединяют смещения за пределами ±"+
        str(p["offset_individual_bound"])+". Все хвосты включены, сумма каждого распределения равна 100%.",
        "",
        "В PDF страницы сначала показывают основную калибровку для всех ошибок, затем для ошибок позже первого шага, затем то же с удалением первого приращения. После них повторены эти условия для второй калибровки.",
        "",
        "| Модель | Попыток | Задач | Максимум до ошибки | В ошибке | После ошибки |",
        "|---|---:|---:|---:|---:|---:|"
    ]
    for model,m in metrics["views"]["all_errors"]["0"].items():
        lines.append(f"| {p['display_names'][model]} | {m['traces']} | {m['tasks']} | {m['before_percent']:.1f}% | {m['exact_percent']:.1f}% | {m['after_percent']:.1f}% |")
    lines+=["",
        "Первый шаг здесь находится внутри формального доказательства Lean. Начало первого приращения привязано к входу в него; часть ответа с неформальным рассуждением не является отдельным размеченным шагом.",
        "",
        "Скрытые состояния после первой ошибки доступны из полной генерации. Однако эти шаги имеют поглощающую метку unreached: Lean не подтвердил их отдельную корректность.",
        "",
        "Сходство двух отдельных распределений само по себе не доказывает, что максимум совпадает с ошибкой внутри конкретной попытки. Правый график показывает совпадения в парах; для вывода о связи сверх типичных позиций нужен отдельный позиционный контроль из предыдущего отчёта.",
        "",
        "Точные частоты и ожидаемые значения сохранены в histograms.csv и metrics.json. Все рисунки отрисованы из metrics.json, а manifest.json содержит конфигурацию, сведения о git и окружении, хэши исходных данных, кода и готовых файлов."
    ]
    return "\n".join(lines)+"\n"

def main():
    plan=start(STAGE)
    source=OUT/"later_error_sensitivity"
    provenance_path=source/"manifest.json"
    provenance=read(provenance_path)
    metrics_path=source/"metrics.json"
    assert digest(metrics_path)==provenance["outputs"][str(metrics_path)]
    prior=read(metrics_path)
    inputs=[provenance_path,metrics_path]
    views={case:{str(fold):{} for fold in plan["folds"]} for case in plan["cases"]}
    for model in MODELS:
        for fold in plan["folds"]:
            path=source/f"{model}-fold{fold}-trials.json"
            assert digest(path)==provenance["outputs"][str(path)]
            inputs.append(path)
            trials=read(path)
            for case in plan["cases"]:
                m=summarize(trials[case],case,plan)
                old=prior["models"][model][str(fold)]["cases"][case]
                assert m["exact_hits"]==old["jump_hits"] and m["traces"]==old["traces"] and m["tasks"]==old["tasks"]
                views[case][str(fold)][model]=m
    cap=plan["absolute_individual_steps"];bound=plan["offset_individual_bound"]
    metrics={"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "config":plan,"views":views,
             "bins":{"absolute_labels":[str(i) for i in range(1,cap+1)]+[f"{cap+1}+"],
                     "relative_edges":np.linspace(0,1,plan["relative_bins"]+1).tolist(),
                     "offset_labels":[f"≤−{bound+1}"]+[str(i) for i in range(-bound,bound+1)]+[f"≥{bound+1}"]},
             "checks":{"all_counts_sum_to_population":True,"all_uniform_expectations_sum_to_population":True,
                       "exact_hit_counts_match_previous_run":True,"original_position_bounds":True,
                       "source_hashes_match":True},
             "generation_calls":0,"model_forward_calls":0,"new_lean_calls":0,
             "hardware":{"machine":platform.machine(),"processor":platform.processor()}}
    folder=OUT/STAGE;folder.mkdir(parents=True,exist_ok=True)
    # Persist numerical metrics before plotting; renderer reads this exact file.
    atomic(folder/"metrics.json",metrics)
    outputs=render(folder/"metrics.json",folder)
    outputs.append(write_csv(folder,read(folder/"metrics.json")))
    rp=folder/"README_RU.md";rp.write_text(report(read(folder/"metrics.json")),encoding="utf-8");outputs.append(rp)
    finish(STAGE,read(folder/"metrics.json"),inputs,outputs)
    for model,m in views["all_errors"]["0"].items():
        print(model,"traces",m["traces"],"first error",m["first_error_traces"],"first max",m["first_maximum_traces"],
              "before",round(m["before_percent"],2),"at",round(m["exact_percent"],2),"after",round(m["after_percent"],2),flush=True)
    print("POSITION HISTOGRAMS COMPLETE",flush=True)

if __name__=="__main__":
    main()
