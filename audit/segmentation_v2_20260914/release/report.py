from pathlib import Path
import json,os,html,hashlib,statistics
from transformers import AutoTokenizer
from export_observations import export
O=Path(__file__).parent;ROOT=O.parents[2]
read=lambda p:json.loads(p.read_text(encoding="utf-8"))
rows=read(O/'validation/cases-summary.json');metrics=read(O/'validation/metrics.json')
checks=read(O/'contract-checks.json');fix=read(O/'corrected-fixture.json')
assert checks["passed"] and all(fix["checks"].values())
good=[r for r in rows if r["group"]=="saved" and r.get("new_L") is not None]
bad=[{k:v for k,v in r.items() if k!="traceback"} for r in rows if r["group"]=="saved" and r.get("new_L") is None]
assert all(r["checks_passed"] for r in good)
curated_bad=[r["name"] for r in rows if r["group"]=="curated" and not r["checks_passed"]]
assert curated_bad==["replay_source_with_goal_and_comment"],curated_bad
labels=read(O/'sample.json');samples={(x["model"],x["trace_id"]):x for x in read(O/'frozen-generations-small.json')}
tokenizers={};exports=O/'exports';exports.mkdir(exist_ok=True);detail=[]
for row in good:
 r=read(O/('validation/case--'+row["name"]+'.json'))
 label=next(x for x in labels if x["model"]==row["model"] and x["trace_id"]==row["trace_id"])
 sample=samples[(row["model"],row["trace_id"])]
 if row["model"] not in tokenizers:
  protocol=read(ROOT/'runs/lean_reverification_20260913_local'/row["model"]/'main/protocol.json')
  tokenizers[row["model"]]=AutoTokenizer.from_pretrained(protocol["model_path"],local_files_only=True)
 e=export(r,sample,tokenizers[row["model"]],label["body_start"])
 (exports/(row["name"]+'.json')).write_text(json.dumps(e,ensure_ascii=False,indent=2),encoding="utf-8")
 detail.append({"name":row["name"],"category":label["category"],"old_L":row["old_L"],"new_L":row["new_L"],
  "n_states":row["n_latent_points"],"localization":row["localization_status"],"header":label["replay"]["header"],
  "points":[{"step":p["index"]+1,"text":p["text"],"label":p["trace_label"],"execution":p["execution_status"],
   "kind":p["observation_kind"],"branch":p["branch_path"],"transition":p["source_transition"],
   "local_goals_before":p.get("active_goal_ids"),"local_goals_after":p.get("next_goal_ids"),
   "root_pending_after":p.get("root_pending_after")} for p in r["points"]]})
g=metrics["groups"]["saved"];old=g["old_L_total"];new=g["new_L_total"];n=len(good);models=[]
for m in ["deepseek","goedel","kimina"]:
 rs=[r for r in good if r["model"]==m]
 models.append({"model":m,"n":len(rs),"old_total":sum(x["old_L"] for x in rs),"new_total":sum(x["new_L"] for x in rs),
 "old_mean":statistics.mean(x["old_L"] for x in rs),"new_mean":statistics.mean(x["new_L"] for x in rs),
 "new_median":statistics.median(x["new_L"] for x in rs),"latent_mean":statistics.mean(x["n_latent_points"] for x in rs),
 "p2_local_context_candidates":sum(x["p2_label_and_alignment_ready"] for x in rs)})
n_ver=sum(r["expected_ok"] for r in good);n_ref=n-n_ver
summary={"main_validation_job":metrics["job"],"report_job":os.environ["SLURM_JOB_ID"],"saved_attempted":24,
 "saved_completed":n,"saved_excluded":bad,"old_L_total":old,"new_L_total":new,"old_mean":old/n,"new_mean":new/n,
 "new_latent_mean":sum(x["n_latent_points"] for x in good)/n,"verified_completed":n_ver,"refuted_completed":n_ref,
 "p2_local_context_candidates":g["p2_label_and_alignment_ready"],"models":models,"contract_checks":checks,
 "curated_final_cases":27,"curated_initial_wrong_expectation":"initial fixture closed a=a; second fixture correctly failed with no progress; final fixture uses nontrivial polynomial normalization",
 "corrected_fixture_job":fix["job"],"production_changed":False,"generation_calls":0,"model_forward_calls":0,
 "production_ready":False,"first_validation_job":"8466498"}
(O/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
(O/'examples.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding="utf-8")
table="| Модель | Разобрано из 8 | Старых блоков | Новых блоков | Среднее старое → новое | Среднее точек с начальной |\n|---|---:|---:|---:|---:|---:|\n"
for r in models:
 table+=f'| {r["model"]} | {r["n"]} | {r["old_total"]} | {r["new_total"]} | {r["old_mean"]:.2f} → {r["new_mean"]:.2f} | {r["latent_mean"]:.2f} |\n'
report=f"""Сегментатор v2: сохранённые ответы, дерево Lean и новые точки наблюдения

14 сентября 2026. Вычисления и проверки выполнены на Жоресе через Slurm. Новых ответов LLM: 0. Проходов по весам моделей: 0. Массовых запусков: 0.

РЕЗУЛЬТАТ

Реализованы границы по AST (синтаксическому дереву Lean), разметка по InfoTree (дереву информации об исполнении), привязка к исходным токенам, пути ветвей и экспорт для последующего извлечения состояний. Исходный код доказательств не переписывается. Производственный конвейер не изменён.

ПОЧЕМУ ПРОМПТЫ РАЗНЫЕ

DeepSeek и Goedel получают одну смысловую инструкцию: дополнить Lean-код и сначала составить подробный план. Kimina получает собственный system prompt и инструкцию решить задачу step by step. Chat template — кодирование ролей и специальных токенов — должен соответствовать конкретной модели. Смысловые различия инструкций являются выбором эксперимента и не технической необходимостью.

Нынешнее сравнение измеряет конфигурацию модель + промпт. При сравнении успешных и ошибочных трасс одной модели этот фактор фиксирован; при сравнении разных моделей он смешан с эффектом весов. Корпус сохраняет ценность, но не доказывает преимущество одних весов при одинаковой инструкции. Для будущего контроля нужен общий смысловой текст с родной чат-обёрткой каждой модели; это отдельный эксперимент, не условие пересегментации данных.

Официальные примеры с запросом плана:
https://huggingface.co/deepseek-ai/DeepSeek-Prover-V2-7B
https://huggingface.co/Goedel-LM/Goedel-Prover-V2-8B

ЧТО ПОВТОРЯТЬ

| Этап | Нужно повторять? |
|---|---|
| Генерация | Нет: тот же ответ, prompt IDs и completion IDs. |
| Итоговый сертификат правильности | Можно переиспользовать при том же исходнике, утверждении, импортах, версиях Lean/Mathlib и проверяемой целостности сертификата. |
| Мелкие контексты Lean | Да, если не сохранены. Прототип снова элаборирует исходный файл ради InfoTree и снимков. |
| Внутренние состояния на новых границах | Да, если позиций нет в кеше. Сейчас сохранены только выбранные старые границы. Нужен forward по прежним IDs, без сэмплирования. |
| Нормировка и статистика | Пересчитать для новой сегментации с фиксированными правилами и калибровкой. |

Новые векторы нельзя получить интерполяцией старых. Исходные токены обозначим z₁,…,zₙ, слой l, границы k₀<…<k_T. Тогда h_t=h⁽ˡ⁾(z₁,…,z_{{k_t}}), Δ_t=h_t−h_{{t−1}}. Новая сетка k_t меняет приращения, даже если текст и веса прежние.

ПРАВИЛО СЕГМЕНТАЦИИ

Сначала, без результатов Lean, фиксируются границы по AST. Углубляемся в have/let/by, bullet, case, cases/induction и строки calc. Поиск и комбинаторы first/try/all_goals/<;> сохраняются атомарными на выбранном уровне: один исходный фрагмент может исполняться многократно на разных целях. Внутренние события остаются метаданными, а не искусственно размноженными точками LLM. Термы calc дают границы наблюдения, но не всегда собственный снимок тактики.

У блока сохранены исходные символьные/байтовые границы, родитель, области видимости, конкретная ветвь cases, локальные цели и незавершённые части корневого доказательства. Линейный текст — ось состояний LLM. Дерево целей — отдельная структура Lean. Соседние ветви различаются; переход между ними не считается продолжением одной локальной цели.

ИСПРАВЛЕНИЯ

1. REPL передавал корневые цели неверно: локальная переменная затенялась, дочерние узлы получали прежний пустой список. В изолированном наблюдателе корень передаётся потомкам. Закрытие вложенной цели больше не равно завершению теоремы.
2. Для локального воспроизведения используется точный фрагмент AST. Форматированный текст REPL разбивал ring_nf at h₄ ⊢ и вызывал ложную синтаксическую ошибку.
3. Добавлены снимки атомарных <;> и скобочных комбинаторов. Их отсутствие мешало воспроизвести ошибку на выбранной границе.
4. Различаются закрытие локальной цели, закрытие корня, смена ветви, пустой локальный контекст и текст после завершения. Ошибка после закрытия корня остаётся ошибкой.
5. Точка с токеном, захватывающим следующий код, исключается явно. Завершающие пробелы внутри токена допускаются с отдельной меткой. Пропуски и совпавшие токеновые позиции не скрываются.

ЧИСЛА

Выборка фиксирована прежним прототипом: 24 сохранённых ответа, по 8 на модель; это диагностическая выборка, не случайная оценка всего корпуса. Полностью обработано {n}/24. На всех {n} совпал прежний исход проверки доказательства. Остальные случаи не включены в средние.

{table}

На сопоставимой обработанной выборке: {old} → {new} блоков; в среднем {old/n:.2f} → {new/n:.2f}. Точек с начальной точкой в среднем {summary["new_latent_mean"]:.2f}. Это увеличение плотности наблюдений, а не числа независимых доказательств.

Привязано {g["n_aligned"]} конечных точек к исходным токенам: {g["n_exact"]} точно, {g["n_whitespace"]} с завершающими пробелами; исключений из-за захвата следующего кода {g["n_crossing_code"]}. Синтетическая проверка специально проверяет и отвергает такой захват. Команд после закрытия корня: {g["n_post_completion"]}.

Независимые воспроизведения локальных снимков: {json.dumps(g["replay_status_counts"],ensure_ascii=False)}. Ошибка снимка не переопределяет сертификат доказательства. Остались снимки без служебных констант _proof_1/_simp_1, созданных при исходной элаборации. Проверка ядра сохранена: эти случаи не превращены в успех.

Полностью разобраны {n_ver} принятых и {n_ref} отвергнутых ответов. У {g["p2_label_and_alignment_ready"]} отвергнутых воспроизведены локальные контексты префикса и ошибочная тактика, граница ошибки найдена в токенах. Это кандидаты для мелкой разметки P2, НЕ сертификат последовательного запуска всех мелких подстрок из одной начальной цели. Production_ready=false.

Контрольные конструкции: 27 случаев после исправления одного неверного ожидания теста. В исходном примере ring_nf уже закрывал a=a, поэтому rfl закономерно ошибался. Промежуточный тест a=b тоже был некорректен: ring_nf сообщал об отсутствии прогресса. Финальный тест использует нетривиальное приведение многочлена и nlinarith; все промежуточные результаты сохранены. Дополнительные проверки контрактов: {checks["n_checks"]}/{checks["n_checks"]}, все прошли.

НЕПОКРЫТЫЕ СЛУЧАИ
"""
for b in bad:report+=f'\n- {b["name"]}: {b.get("exception",b.get("parse_error_kind","unknown"))}.'
report+="""

Тайм-ауты не считаются опровержением доказательства. Крупные interval_cases создают большие деревья исполнения; наблюдатель экспортирует больше контекстов, чем требуется. Отделить стоимость элаборации от экспорта без отдельного профилирования нельзя. Нужен ограниченный сбор выбранных диапазонов.

МЕТКИ И СТАТИСТИЧЕСКИЙ СМЫСЛ

pre — исходный текст до границы первой ошибки, at — воспроизведённая ошибка, post — последующий текст ответа. Lean может исполнять дальнейший текст при восстановлении после ошибки; это не отменяет поглощения. Термы calc без снимка получают diagnostic_only. Участки с sorry, неоднозначными контекстами или неполным префиксом не получают готового сертификата.

Начальная точка сейчас — последний токен промпта. Первое приращение включает неформальный план и заголовок сгенерированной теоремы. Экспорт сохраняет это определение и дополнительно предоставляет позицию перед телом Lean: optional_formal_entry_baseline. Это отдельный вариант анализа; смешивать определения нельзя.

Рекомендация: мелкие семантические границы с сохранением дерева; прежняя грубая сетка — проверка устойчивости. Не просить переписывать уже полученные доказательства в линейную форму: это изменит данные и не устранит ветвление целей. Каждый токен не является завершённым действием Lean. Многократное исполнение одного <;> не создаёт новых позиций текста LLM.

При анализе отмечать обычные шаги, смену ветви, закрытие области и текст после завершения. Учитывать число токенов между границами. Не считать точки одной трассы независимыми: неопределённость оценивается с группировкой по задаче/траектории. Правило отсечения, нормировка и сетка фиксируются до сравнения хвостов.

ГОТОВНОСТЬ

Для массового использования остались: ограниченный экспорт InfoTree; безопасное восстановление вспомогательных деклараций в снимках без доступа к будущему решению; интеграция нового формата с доверенным сертификатом; контроль GPU-извлечения новых позиций. Новый прототип работает на малой выборке; массовая разметка и перерасчёт P1/P2 не запускались.

ФАЙЛЫ

segmenter.py — AST; segmenter_v2.py — состояния, ветви, токены и CLI одного доказательства; export_observations.py — экспорт из кеша без Lean; build_observer.py и repl/REPL — изолированное исправление Lean. Результаты: validation/, contract-checks.json, corrected-fixture.json, examples.json, exports/.

ProofState принадлежит одной живой сессии REPL: сохранённый номер не является переносимым снимком. Идентификаторы целей сравниваются только внутри одной элаборации.

CLI в подготовленной среде Жореса:
python segmenter_v2.py input.json --output result.json --replay-limit 100 --tokenizer /local/model/tokenizer
В input.json: header, body, trace_id, sample с исходными IDs, body_start. Один объект, не большой batch. Прилагаются Slurm-скрипты. Патчи относятся к Lean 4.34.0-rc2 и замороженным исходникам проекта. Production REPL не подменялся.
"""
(O/"REPORT_RU.md").write_text(report,encoding="utf-8")
parts=['<!doctype html><html lang="ru"><meta charset="utf-8"><title>Сегментатор v2</title><style>body{max-width:1050px;margin:36px auto;padding:0 20px;font:17px/1.55 system-ui;color:#172132;background:#fafafa}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef1f5;padding:16px;border-radius:8px}details{margin:12px 0;padding:12px;border:1px solid #d1d7df;border-radius:8px}summary{cursor:pointer;font-weight:650}.pre{border-left:5px solid #31795b}.at{border-left:5px solid #b8463e}.post{opacity:.7}</style><body><h1>Сегментатор v2: проверка</h1>']
for para in report.split("\n\n"):
 parts.append("<pre>"+html.escape(para)+"</pre>" if para.startswith("|") else "<p>"+html.escape(para).replace("\n","<br>")+"</p>")
parts.append('<p><b>Примеры: исходный текст, ветви и метки</b></p>')
for d in detail:
 parts.append('<details><summary>'+html.escape(d["name"]+f' · {d["category"]} · {d["old_L"]} → {d["new_L"]} блоков · '+d["localization"])+'</summary><pre>'+html.escape(d["header"])+'</pre>')
 for p in d["points"]:
  label=p["label"];cls="at" if label in ["at","at_candidate"] else label
  parts.append('<div class="'+html.escape(cls)+'"><p>'+html.escape(f'Шаг {p["step"]} · {label} · ветвь {p["branch"]} · {p["execution"]}')+'</p><pre>'+html.escape(p["text"])+'</pre></div>')
 parts.append('</details>')
parts.append('</body></html>')
(O/"REPORT_RU.html").write_text("\n".join(parts),encoding="utf-8")
manifest={}
for p in O.rglob("*"):
 if p.is_file() and '.lake' not in p.parts and p.name not in ["repl-observer","artifact-manifest.json"] and not p.name.endswith(".log"):
  manifest[str(p.relative_to(O))]=hashlib.sha256(p.read_bytes()).hexdigest()
(O/'artifact-manifest.json').write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=True),flush=True)
