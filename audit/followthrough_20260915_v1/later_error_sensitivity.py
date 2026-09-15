"""Requested post-hoc first-error/first-increment sensitivity on frozen saved scores."""
import collections
import itertools
import math
import numpy as np
import pandas as pd
from stage_support import ROOT, HERE, OUT, MODELS, read, atomic, start, finish, digest
from analysis_math import exact_position, exact_distribution

STAGE = "later_error_sensitivity"
CASES = ("all_errors", "later_errors", "later_errors_drop_first_increment")

def trace_record(g, lower, families):
    g = g.sort_values("t")
    t = g.t.to_numpy(dtype=int)
    assert np.array_equal(t, np.arange(len(g)))
    assert g.t_star.nunique() == 1
    star = float(g.t_star.iloc[0])
    assert np.isfinite(star) and int(star) == star and 0 <= star < len(g)
    star = int(star)
    assert star >= lower
    z = g.z_shrinkage_0_1.to_numpy(dtype=float)[lower:]
    sp = g.surprisal.to_numpy(dtype=float)[lower:]
    assert len(z) > 0 and np.isfinite(z).all() and np.isfinite(sp).all()
    j = int(np.argmax(z)) + lower
    s = int(np.argmax(sp)) + lower
    pid = str(g.prompt_id.iloc[0])
    return {
        "trace_id": str(g.trace_id.iloc[0]), "problem_id": pid,
        "task_family": families[pid], "L": len(z), "original_L": len(g),
        "f": star-lower, "j": j-lower, "s": s-lower,
        "original_f": star, "original_j": j, "original_s": s,
        "jump_hit": int(j == star), "surprisal_hit": int(s == star),
        "uniform_chance": 1/len(z), "max_at_original_first": int(j == 0),
        "jump_tie": int(np.count_nonzero(z == z.max()) > 1),
        "surprisal_tie": int(np.count_nonzero(sp == sp.max()) > 1),
    }

def summarize(rows, representative_ids, plan):
    if not rows:
        return {"traces": 0, "tasks": 0}
    df = pd.DataFrame(rows)
    names = ["jump_hit", "surprisal_hit", "uniform_chance"]
    group = df.groupby("problem_id", sort=True)[names].mean()
    matrix = group.to_numpy()
    matrix = np.column_stack([matrix, matrix[:,0]-matrix[:,1], matrix[:,0]-matrix[:,2]])
    fields = names + ["jump_minus_surprisal", "jump_minus_uniform"]
    intervals = None
    if len(matrix) >= plan["minimum_bootstrap_tasks"]:
        rng = np.random.default_rng(plan["bootstrap_seed"])
        sampled = []
        for lo in range(0, plan["bootstrap_replicates"], 500):
            ix = rng.integers(len(matrix), size=(min(500, plan["bootstrap_replicates"]-lo), len(matrix)))
            sampled.append(matrix[ix].mean(axis=1))
        samples = np.concatenate(sampled)
        intervals = {name: np.quantile(samples[:,i], [.025,.975]).tolist() for i,name in enumerate(fields)}
    representatives = [r for r in rows if r["trace_id"] in representative_ids]
    position = exact_position(representatives)
    position["method"] = "Exact integer permutation distribution within task_family by exact candidate length; one lexicographically first trace per task chosen before exclusions."
    position["representatives_before_matching"] = len(representatives)
    position["at_least_20_matched_tasks"] = position["matched_groups"] >= 20
    return {
        "traces": len(rows), "tasks": len(group),
        "jump_hits": int(df.jump_hit.sum()), "jump_rate": float(df.jump_hit.mean()),
        "surprisal_hits": int(df.surprisal_hit.sum()), "surprisal_rate": float(df.surprisal_hit.mean()),
        "uniform_chance": float(df.uniform_chance.mean()),
        "equal_task": dict(zip(fields, matrix.mean(axis=0).tolist())),
        "ci95_equal_task_fixed_transform": intervals,
        "median_candidate_steps": float(df.L.median()),
        "mean_candidate_steps": float(df.L.mean()),
        "jump_tied_traces": int(df.jump_tie.sum()), "surprisal_tied_traces": int(df.surprisal_tie.sum()),
        "max_at_original_first_count": int(df.max_at_original_first.sum()),
        "exact_position_control": position,
    }

def checks():
    # Independent enumeration validates the exact positional null, including ties.
    example = [{"j":0,"f":0},{"j":1,"f":1},{"j":0,"f":2},{"j":2,"f":0}]
    counts = collections.Counter(sum(example[i]["j"] == example[c]["f"] for i,c in enumerate(p))
                                 for p in itertools.permutations(range(len(example))))
    assert np.allclose(exact_distribution(example),
                       [counts[k]/math.factorial(len(example)) for k in range(len(example)+1)])
    # Removing the first candidate must retain original step coordinates and not use the error as a new start.
    df = pd.DataFrame({"trace_id":["example"]*4, "prompt_id":["task"]*4,
                       "t":range(4), "t_star":[2]*4,
                       "z_shrinkage_0_1":[10., 1., 8., 3.], "surprisal":[4.,5.,2.,1.]})
    a = trace_record(df, 0, {"task":"family"})
    b = trace_record(df, 1, {"task":"family"})
    assert (a["original_j"], a["jump_hit"]) == (0, 0)
    assert (b["original_j"], b["f"], b["j"], b["jump_hit"], b["L"]) == (2, 1, 1, 1, 3)
    return {"exact_null_independent_enumeration": True, "candidate_index_boundary_check": True}

def render(metrics):
    pct = lambda x: "—" if x is None else f"{100*x:.1f}%"
    lines = [
        "# Исключение ранних ошибок: пересчёт по сохранённым данным",
        "",
        "Это дополнительный исследовательский анализ прежней выборки, выполненный по запросу пользователя. Он не меняет протокол будущей проверки P2.",
        "",
        "Использованы очищенная Kimina, подробная сегментация Lean, температура 0,6, заранее выбранные средние слои, начало приращений у входа в формальное доказательство и shrinkage 0,1. Две перестановки калибровочных частей показаны обе. Преобразование не переобучалось под исключения.",
        "",
        "Первая ошибка имеет индекс 0 в данных и номер 1 в тексте. Это первый формальный шаг Lean, а не текст рассуждения перед Lean. После первой ошибки следующие шаги имеют статус unreached; их скрытые состояния доступны из генерации, но корректность этих шагов отдельно не подтверждена.",
        "",
        "В таблице доли взвешены по попыткам. «Случайно» — среднее 1/L по тем же попыткам и допустимым позициям. Это простой ориентир, а не контроль типичных позиций.",
        "",
        "| Модель | Калибровка | Условие | Попыток / задач | Максимум на первой ошибке | Surprisal | Случайно |",
        "|---|---|---|---|---|---|---|",
    ]
    labels = {"all_errors":"Все локализованные ошибки", "later_errors":"Ошибка позже первого шага",
              "later_errors_drop_first_increment":"То же + убрать первое приращение"}
    for model, variants in metrics["models"].items():
        for fold, item in variants.items():
            for case in CASES:
                r = item["cases"][case]
                lines.append(f"| {model} | {fold} | {labels[case]} | {r['traces']} / {r['tasks']} | {pct(r.get('jump_rate'))} | {pct(r.get('surprisal_rate'))} | {pct(r.get('uniform_chance'))} |")
    lines += ["", "Позиционный контроль использует по одной попытке на задачу, выбранной до исключения ранних ошибок; метки ошибок переставляются только между задачами одинакового семейства и точной длины. Задачи без пары исключаются только из этого контроля. Поэтому его знаменатель отличается от основной таблицы.", "",
        "| Модель | Калибровка | Условие | Сопоставимых задач | Попадание | Позиционное ожидание | p, одностороннее, номинальное |",
        "|---|---|---|---|---|---|---|"]
    for model, variants in metrics["models"].items():
        for fold,item in variants.items():
            for case in CASES:
                p = item["cases"][case].get("exact_position_control", {})
                value = p.get("p_one_sided")
                pv = "—" if value is None else f"{value:.6g}"
                lines.append(f"| {model} | {fold} | {labels[case]} | {p.get('matched_groups',0)} | {pct(p.get('rate'))} | {pct(p.get('null_mean'))} | {pv} |")
    lines += ["", "Эти p-значения и 95%-интервалы в metrics.json номинальные: они не учитывают всю историю поисковых сравнений. Калибровочные варианты и условия зависимы; это не независимые воспроизведения. Интервалы считают задачи единицами повторной выборки и фиксируют уже обученное преобразование.",
              "", "Условие «ошибка позже первого шага» известно только после Lean-проверки. Поэтому высокая точность на этой подвыборке сама по себе не означает такую же точность на любом новом ответе.",
              "", "Удаление первого приращения сокращает число кандидатов и повышает случайный ориентир. Знаменатель всегда пересчитан. Поиск максимума не начинается в известной точке ошибки; все оставшиеся позиции, включая unreached, участвуют.",
              "", "Конфигурация, хэши исходных parquet, метаданных и скриптов, git commit, признак dirty и окружение сохранены рядом в manifest.json. Индивидуальные результаты доступны в файлах trials.json."]
    return "\n".join(lines)+"\n"

def main():
    plan = start(STAGE)
    passed = checks()
    folder = OUT/STAGE
    folder.mkdir(parents=True, exist_ok=True)
    source_manifest = OUT/"calibration/manifest.json"
    provenance = read(source_manifest)
    inputs = [source_manifest]
    outputs = []
    result = {}
    for model in MODELS:
        problem_path = ROOT/"runs/lean_reverification_20260913_local"/model/"inputs/problems.json"
        problems = read(problem_path)
        families = {str(p["problem_id"]):p["task_family"] for p in problems}
        inputs.append(problem_path)
        result[model] = {}
        for fold in plan["folds"]:
            path = OUT/"calibration"/f"{model}-formal_entry-fold{fold}-scores.parquet"
            assert digest(path) == provenance["outputs"][str(path)]
            inputs.append(path)
            df = pd.read_parquet(path).rename(columns={"z_shrinkage_0.1":"z_shrinkage_0_1"})
            df = df[(df.role == "evaluation") & (df.outcome != "verified")]
            groups = list(df.groupby("trace_id", sort=True))
            all_rows = [trace_record(g,0,families) for _,g in groups]
            one = {}
            for r in all_rows:
                one.setdefault(r["problem_id"], r["trace_id"])
            representatives = set(one.values())
            later = [r for r in all_rows if r["original_f"] > 0]
            dropped = [trace_record(g,1,families) for _,g in groups if int(g.t_star.iloc[0]) > 0]
            assert [r["trace_id"] for r in later] == [r["trace_id"] for r in dropped]
            assert all(a["original_f"] == b["original_f"] and a["original_L"] == b["original_L"]
                       for a,b in zip(later,dropped))
            changed = sum(a["original_j"] != b["original_j"] for a,b in zip(later,dropped))
            assert changed == sum(a["max_at_original_first"] for a in later)
            cases = dict(zip(CASES, [all_rows, later, dropped]))
            record = {"excluded_first_error_traces": len(all_rows)-len(later),
                      "first_error_fraction": (len(all_rows)-len(later))/len(all_rows),
                      "representative_selection": "lexicographically first eligible trace per original task, before exclusions",
                      "jump_argmax_changed_by_dropping_first": changed,
                      "cases": {case:summarize(rows,representatives,plan) for case,rows in cases.items()}}
            result[model][str(fold)] = record
            trial_path = folder/f"{model}-fold{fold}-trials.json"
            atomic(trial_path, cases)
            outputs.append(trial_path)
            print(model, fold, json_compact(record), flush=True)
    metrics = {"models":result, "checks":passed,
               "scope":"Requested post-hoc sensitivity; not a new confirmation; fixed transforms, all listed conditions reported.",
               "bootstrap_unit":"original problem, equal weight after averaging its eligible attempts",
               "generation_calls":0, "model_forward_calls":0, "new_lean_calls":0}
    report = folder/"REPORT_RU.md"
    report.write_text(render(metrics), encoding="utf-8")
    outputs.append(report)
    finish(STAGE, metrics, inputs, outputs)
    print("LATER ERROR SENSITIVITY COMPLETE", flush=True)

def json_compact(record):
    import json
    return json.dumps({k:{"n":v["traces"],"jump":v.get("jump_rate"),"surprisal":v.get("surprisal_rate"),"uniform":v.get("uniform_chance")} for k,v in record["cases"].items()})

if __name__ == "__main__":
    main()
