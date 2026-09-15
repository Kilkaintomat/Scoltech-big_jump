"""Render a diagnostic explanation from the completed read-only audit."""
from pathlib import Path
from collections import Counter
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from onebigjump.e1.artifacts import read_json, digest, finish, verify_manifest, write_once

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/label-yield-audit-v1"
PARENT=HERE/"result-8466260"
OUT=HERE/("explanation-"+os.environ["SLURM_JOB_ID"])
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
MODELS=("deepseek","goedel","kimina")
NAMES={"deepseek":"DeepSeek","goedel":"Goedel","kimina":"Kimina"}
LABELS={
    "verified":"Подтверждено протоколом",
    "tactic_failure":"Ошибка тактики / незакрытая цель",
    "length_stop":"Лимит длины ответа",
    "lean_limit":"Лимит проверки Lean",
    "parse_error":"Синтаксис / разбор кода",
    "native_policy":"Правило об аксиомах native_decide",
    "other":"Другие исключения",
}
COLORS=["#25947a","#d98947","#c3bdac","#729abe","#d9b55c","#9977bb","#bbbfc4"]


def group(row):
    cat=row["category"]
    if cat=="verified":return "verified"
    if cat in {"localized_tactic_failure","terminal_unsolved_goals"}:return "tactic_failure"
    if cat=="generation_truncation":return "length_stop"
    if cat=="timeout_resource":return "lean_limit"
    if cat in {"parse_error","unsupported_segmentation"}:return "parse_error"
    if cat=="sorry_invalid_proof" and row["native_policy_only"]:return "native_policy"
    return "other"


def main():
    verify_manifest(PARENT/"manifest.json")
    meta=read_json(PARENT/"metrics.json")
    allrows=read_json(PARENT/"audited-row-summary.json")
    tasks=set(read_json(PARENT/"matched-task-ids.json"))
    matched={m:[r for r in rr if r["problem_id"] in tasks] for m,rr in allrows.items()}
    counts={m:dict(Counter(group(r) for r in rr)) for m,rr in matched.items()}
    n={m:len(rr) for m,rr in matched.items()}
    assert len(set(n.values()))==1
    ratios={m:{k:counts[m].get(k,0)/n[m] for k in LABELS} for m in MODELS}
    for m in MODELS:assert sum(counts[m].values())==n[m]
    current_total=sum(s["attempts"] for s in meta["accepted"].values())
    current_verified=sum(s["verified"] for s in meta["accepted"].values())
    changed=sum(v for d in meta["transitions"].values() for k,v in d.items() if k.split(" -> ")[0]!=k.split(" -> ")[1])
    metrics=dict(source_snapshot_utc=meta["started_utc"],matched_task_count=len(tasks),counts=counts,fractions=ratios,
        accepted_total=current_total,verified_total=current_verified,corrected_category_changes=changed,
        matched_solved_fractions={m:meta["matched"][m]["tasks_with_at_least_one_verified"]/len(tasks) for m in MODELS},
        native_policy_condition="sorry_invalid_proof AND whole/replay accepted AND no literal hole AND only native-named unexpected axioms",
        native_policy_provenance_validated=False,primary_labels_modified=False,
        historical_totals=meta["historical_totals"])
    OUT.mkdir()
    fig,ax=plt.subplots(figsize=(12,5.4))
    left=[0.,0.,0.]
    for key,color in zip(LABELS,COLORS):
        widths=[100*ratios[m][key] for m in MODELS]
        ax.barh(range(3),widths,left=left,label=LABELS[key],color=color,height=.57)
        for i,w in enumerate(widths):
            if w>=2.8:ax.text(left[i]+w/2,i,f"{w:.1f}%",ha="center",va="center",fontsize=10,
                color="white" if key=="verified" else "#20252b",fontweight="bold" if key=="verified" else "normal")
        left=[a+b for a,b in zip(left,widths)]
    ax.set_yticks(range(3),[NAMES[m] for m in MODELS],fontsize=12)
    ax.invert_yaxis();ax.set_xlim(0,100);ax.set_xticks([0,25,50,75,100])
    ax.set_xlabel("Доля всех попыток на одинаковых полностью проверенных задачах, %")
    ax.set_title(f"Исходы проверки: {len(tasks)} одинаковые задачи, по {n[MODELS[0]]:,} попытки на модель".replace(","," "),fontsize=14,pad=18)
    ax.spines[["top","right","left"]].set_visible(False)
    ax.legend(loc="upper center",bbox_to_anchor=(.5,-.23),ncol=2,frameon=False,fontsize=10)
    fig.subplots_adjust(bottom=.35,left=.1,right=.985,top=.82)
    fig.text(.1,.015,"Промежуточный срез. Принятая запись обработки не означает верное доказательство.",fontsize=10,color="#525b64")
    image=OUT/"outcomes.png";vector=OUT/"outcomes.svg"
    fig.savefig(image,dpi=160);fig.savefig(vector);plt.close(fig)
    metric=write_once(OUT/"metrics.json",metrics)
    text=["# Почему проценты выглядят маленькими","",
        "Срез исходных данных: "+meta["started_utc"]+". Числа получены заданием Slurm 8466260 с проверкой manifest, хешей строк, соответствия генерациям и поглощающих меток.","",
        "## Что означают слова","",
        "На исходном рисунке «принятые доказательства» — категория verified: подтверждено по действующему протоколу. "
        "«Обработано» — число ответов, для которых уже записан исход. В последующем отчёте «принятые ответы» означает записи с проверенным происхождением и метками, включая ошибочные доказательства. Это разные показатели; прежняя формулировка была неоднозначной.","",
        "## Проверка рисунка","",
        "Все показанные модельные счётчики воспроизводятся по префиксам исходных журналов. Для некоторых моделей возможны несколько префиксов с теми же счётчиками; точное время и единственный набор строк исторического снимка не восстановлены.","",
        f'Всего сгенерировано {sum(g["attempts"] for g in meta["generated"].values()):,} ответов: три модели, 417 задач, две температуры, восемь попыток. На рисунке проверено {meta["historical_totals"]["processed"]:,}, подтверждено {meta["historical_totals"]["verified"]:,}.'.replace(","," "),
        f'Доля обработанных: {meta["historical_totals"]["processed_fraction"]:.2%}. Доля verified среди обработанных: {meta["historical_totals"]["verified_per_processed"]:.2%}.',
        f'Отношение verified ко всем сгенерированным равно {meta["historical_totals"]["verified_per_all_generated"]:.2%}, но оно смешивает качество с незавершённостью проверки: {meta["historical_totals"]["not_yet_processed_at_claim"]:,} исходов тогда ещё не были известны.'.replace(","," "),"",
        "## Текущий сопоставимый срез","",
        f'Проверенные завершённые порции содержат {current_total:,} записей, из которых {current_verified:,} имеют категорию verified. Для сравнения моделей ниже взяты только {len(tasks)} одинаковые задачи с полным набором попыток.'.replace(","," "),"",
        "| Модель | verified / попытки | Доля | Решено хотя бы одной из 16 попыток |","|---|---:|---:|---:|"]
    for m in MODELS:
        s=meta["matched"][m]
        text.append(f'| {NAMES[m]} | {s["verified"]} / {s["attempts"]} | {s["verified_fraction"]:.2%} | {s["tasks_with_at_least_one_verified"]} / {len(tasks)} = {metrics["matched_solved_fractions"][m]:.2%} |')
    text+=["","Это описательные показатели частичной выборки, не окончательный рейтинг и не оценка независимых вероятностей отдельных попыток. Половина попыток сделана при каждой температуре.","",
        "![Исходы проверки](outcomes.png)","",
        "| Причина | DeepSeek | Goedel | Kimina |","|---|---:|---:|---:|"]
    for key,label in LABELS.items():
        text.append("| "+label+" | "+" | ".join(f'{counts[m].get(key,0)} ({ratios[m][key]:.2%})' for m in MODELS)+" |")
    text+=["","## Что объясняет потери","",
        "1. **Сложность задач различается.** miniF2F содержит учебные задачи и соревнования AMC/AIME/IMO. [Описание разработчиков](https://github.com/openai/miniF2F). На нашем одинаковом срезе:" ,"",
        "| Семейство | Задач | DeepSeek: verified | Goedel: verified | Kimina: verified |","|---|---:|---:|---:|---:|"]
    for family in ["mathd_algebra","mathd_numbertheory","aime","imo"]:
        groups=[meta["matched_groups"][m]["task_family"][family] for m in MODELS]
        text.append("| "+family+" | "+str(groups[0]["tasks"])+" | "+" | ".join(f'{s["verified_fraction"]:.2%}' for s in groups)+" |")
    text+=["",
        "Это подтверждает различие сложности в текущем режиме, но не отделяет чистую математическую сложность от совместимости библиотек и бюджетов.","",
        "2. **Обрывы по длине существенны.** Общий лимит генерации — 8192 новых токена. По всей сохранённой генерации:"]
    for m,g in meta["generated"].items():
        text.append(f'- {NAMES[m]}: {g["finishes"]["length"]} / {g["attempts"]} = {g["length_stop_fraction"]:.2%}.')
    text+=["",
        "Из этих данных нельзя обещать, что более длинная генерация сделает все оборванные ответы верными. В примере Goedel указан бюджет 32768 токенов; тот же источник использует Lean 4.9 и публикует Pass@32, поэтому прямое сравнение с нашим режимом некорректно. [Карточка Goedel](https://huggingface.co/Goedel-LM/Goedel-Prover-V2-8B).","",
        "3. **Правило об аксиомах заметно влияет на Kimina.**"]
    for m in MODELS:
        native=counts[m].get("native_policy",0)
        if native:text.append(f'{NAMES[m]}: {native} ответов ({ratios[m]["native_policy"]:.2%} всех попыток) прошли whole/replay, но исключены фиксированной политикой аксиом. '
            "Они не содержат буквальных sorry/admit; неразрешённые зависимости имеют имена native_decide. "
            "Это диагностическая классификация по записанной информации, а не повторная проверка происхождения каждой такой аксиомы.")
    text+=["В новых версиях Lean native_decide создаёт отдельную аксиому для каждого вычисления; это отличается от доверия только ядру. "
        "[Официальное описание](https://lean-lang.org/doc/reference/latest/ValidatingProofs/). Эти случаи требуют отдельной категории и проверки; автоматически добавлять их к verified нельзя.","",
        "4. **Ошибки формального кода и совместимость также важны.** В сообщениях встречаются неизвестные имена лемм и тактик, незакрытые цели и лишние тактики после закрытия цели. "
        "По одному тексту ошибки нельзя доказать, что причиной является именно версия Mathlib. Более новая Lean/Mathlib по сравнению с опубликованной конфигурацией модели — отдельная проверяемая гипотеза.",
        f'Исправление ранее обнаруженных ошибок сегментации изменило категории {changed} записей в этом срезе; это не объясняет основную массу неуспешных исходов.',"",
        "## Что делать дальше","",
        "- Завершить текущую проверку и публиковать отдельно прогресс, долю верных попыток и долю решённых задач.",
        "- Отдельно проверить native_decide и совместимость Lean/Mathlib на заранее фиксированных сохранённых примерах, сохраняя основную политику и метки.",
        "- Оценивать необходимость большего бюджета генерации на отдельном диагностическом запуске; текущие оборванные ответы не считать автоматически неверными математически.",
        "- Сохранять исходную выборку; показывать результаты по семействам сложности. Для исследования нужны и верные, и ошибочные трассы; увеличение процента успеха само по себе не является научной целью.","",
        "Полный пересчёт, исходные категории, примеры ошибок и реквизиты воспроизводимости находятся в ../result-8466260/. Основные эксперименты продолжаются; в этой проверке их данные и протоколы не менялись."]
    report=OUT/"REPORT.md";report.write_text("\n".join(text)+"\n",encoding="utf-8")
    finish(OUT,stage="label-yield-diagnostic-explanation",context=dict(parent=digest(PARENT/"manifest.json")),
        inputs=[SOURCE,PARENT/"manifest.json",Path(__file__),HERE/"explain.sbatch"],
        outputs=[metric,report,image,vector],metrics=metrics)
    print("EXPLANATION_COMPLETE",OUT,flush=True)


if __name__=="__main__":main()
