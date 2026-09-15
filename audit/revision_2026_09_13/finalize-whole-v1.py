from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,os,shutil,hashlib
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,verify_manifest
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
audit=base/"audit/revision_2026_09_13"
checkpoint=audit/"reviews/whole-project-selection-v2"
out=audit/"reviews/whole-project-final-v1"
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
d=read_json(checkpoint/"metrics.json")
log=(checkpoint/"job-8466129.log").read_text(encoding="utf-8")
assert "COLLECTION_COMPLETE" in log
assert d["p3_selection_integrity"]["mismatches"]==0
assert d["source_sha256"]==digest(source)
out.mkdir(exist_ok=False)
for folder in ("artifacts","source","inputs","code"):
    shutil.copytree(checkpoint/folder,out/folder)
shutil.copy2(Path(__file__),out/"code/finalize.py")
shutil.copy2(checkpoint/"job-8466129.log",out/"inputs/collector-log.txt")
artifacts=[];checks=[]
for copied in sorted((out/"artifacts").rglob("*")):
    if not copied.is_file():continue
    relative=copied.relative_to(out/"artifacts")
    original=base/relative
    assert original.is_file(),str(original)
    actual=digest(copied)
    assert digest(original)==actual,str(original)
    artifacts.append({"remote":str(original),"relative":str(copied.relative_to(out)),"sha256":actual})
    checks.append({"path":str(original),"sha256":actual})
print("COPIED_EVIDENCE_CHECKED",len(checks),flush=True)
receipt=write_once(checkpoint/"collection-lineage-checks.json",{
 "collection_job":"8466129","validation_job":os.environ["SLURM_JOB_ID"],
 "collection_code_sha256":digest(checkpoint/"code/report.py"),"collection_metrics_sha256":digest(checkpoint/"metrics.json"),
 "completed_collection_marker":True,"collection_failed_later_in_report_rendering":True,
 "render_failure":"soft selection has no oracle comparison; missing diagnostic cell",
 "copied_artifacts_rechecked":checks,"copied_artifact_mismatches":0,
 "recursive_upstream_validation":"performed by completed collector before metrics checkpoint; see frozen collector code and log",
 "new_finalization_does_not_repeat_expensive_completed_experiments":True})
# Attest the completed numerical checkpoint under this validating run; the earlier rendering failure is retained.
collection_manifest=finish(checkpoint,stage="validated-completed-collector-checkpoint",
 context={"collection_job":"8466129","validation_job":os.environ["SLURM_JOB_ID"],"source":digest(source)},
 inputs=[source,checkpoint/"code/report.py",receipt,Path(__file__)],
 outputs=[checkpoint/"metrics.json",checkpoint/"selection-integrity.json",checkpoint/"job-8466129.log"],
 metrics={"collector_complete":True,"render_complete":False,"copied_artifacts_verified":len(checks),
          "p3_integrity":d["p3_selection_integrity"]})
shutil.copy2(collection_manifest,out/"inputs/collector-manifest.json")
shutil.copy2(receipt,out/"inputs/collection-lineage-checks.json")
shutil.copy2(checkpoint/"selection-integrity.json",out/"selection-integrity.json")
outdent_root=audit/"segmentation-outdent-v1/result"
verify_manifest(outdent_root/"manifest.json")
outdent=read_json(outdent_root/"metrics.json")
for p in sorted((audit/"segmentation-outdent-v1").rglob("*")):
    if not p.is_file():continue
    target=out/"artifacts"/p.relative_to(base)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    artifacts.append({"remote":str(p),"relative":str(target.relative_to(out)),"sha256":digest(p)})
queues=d["queues"];main=d["main"];main_shards=d["main_completed_shards"]
validation=d["runtime_validation"];compiler_review=d["compiler_review"];pilot_attestation=d["pilot_attestation"]
ded_review=d["deduction_v2_review"];deduction_exact=d["deduction_v3"];ded_v2_counts=d["deduction_v2_counts"]
pilot_controls=d["pilot_controls"];pilot_lineage=d["pilot_control_lineage"];controls=d["main_controls"]
p4=d["p4"];p4_summary=d["p4_summary"];selection=d["p3_selection"];selection_protocol=selection["config"]
selection_audit=d["p3_selection_integrity"];selection_preflight=d["p3_selection_preflight"]
p3_candidate=d["p3_constrained"];p3=d["historical_p3"];started=d["started_utc"]
for model,summary in main_shards.items():
    passed=0;passed_labels=0
    for shard in summary["completed_shards"]:
        path=base/"runs/lean_reverification_20260913_local"/model/"main/verification"/shard["shard"]/"manifest.json"
        info=read_json(path)["metrics"]
        shard["unexplained_disagreements"]=info["unexplained_disagreements"]
        shard["gate_passed"]=info["unexplained_disagreements"]==0
        if shard["gate_passed"]:passed+=1;passed_labels+=shard["attempts"]
    summary["gate_passed_shards"]=passed;summary["gate_passed_labels"]=passed_labels
    summary["scope"]="archived shard manifests include a failed semantic gate; archive completeness is not analysis eligibility"
snapshot=audit/"finalize-whole-inputs-v1"
current_queues={}
for p in sorted(snapshot.glob("*-queue.json")):
    q=read_json(p);shutil.copy2(p,out/"inputs"/("latest-"+p.name))
    current_queues[p.name.removesuffix("-queue.json")]={
      "counts":dict(Counter(t["state"] for t in q["tasks"].values())),
      "failures":{k:t for k,t in q["tasks"].items() if t["state"] in ("FAILED","BLOCKED")},
      "last_poll_utc":q.get("last_poll_utc")}
for name in ("squeue.txt","capture.json","sacct.txt","tmux.txt"):
    shutil.copy2(snapshot/name,out/"inputs"/("latest-"+name))
inputs=[source,collection_manifest,outdent_root/"manifest.json",Path(__file__)]
print("READY_TO_RENDER",flush=True)


finished=datetime.now(timezone.utc).isoformat()
metrics={"started_utc":started,"finished_utc":finished,"source":str(source),"source_sha256":digest(source),
 "queues":queues,"main":main,"main_completed_shards":main_shards,"runtime_validation":validation,
 "compiler_review":compiler_review,"pilot_attestation":pilot_attestation,
 "deduction_v2_review":ded_review,"deduction_v3":deduction_exact,
 "pilot_controls":pilot_controls,"pilot_control_lineage":pilot_lineage,"main_controls":controls,
 "p4":p4,"p4_summary":p4_summary,"deduction_v2_counts":ded_v2_counts,"p3_selection":selection,"p3_selection_integrity":selection_audit,
 "p3_selection_preflight":selection_preflight,"p3_constrained":p3_candidate,"historical_p3":p3,
 "primary_method_changed":False,
 "scope":"current programme and selected historical evidence; not a new execution of every draft experiment"}
metrics.update(main_blocker=outdent,latest_queues=current_queues)
write_once(out/"metrics.json",metrics)
lines=[]
def para(s): lines.extend([s,""])
def table(headers,data):
    lines.extend(["| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |"])
    for row in data: lines.append("| "+" | ".join(str(v).replace("|","/").replace("\n"," ") for v in row)+" |")
    lines.append("")
def num(v):
    if v is None:return "NA"
    if isinstance(v,float):return f"{v:.5g}"
    return str(v)
def prop(p):
    return f'{p["successes"]}/{p["datasets"]} ({100*p["fraction"]:.2f}%)' if p["fraction"] is not None else "NA"
def ci(v):return "["+", ".join(num(x) for x in v)+"]" if v is not None else "NA"
def link(path,label):
    return "["+label+"](artifacts/"+str(Path(path).relative_to(base))+")"
primary=selection_protocol["primary_candidate"]
under=[name for name,v in selection["primary_family_monte_carlo"].items() if v["undercoverage_detected"]]
para("# One Big Jump: общая ревизия и проверка порога P3")
para("Срез на Жоресе: "+started+" — "+finished+". Все числа автоматически прочитаны из артефактов серверных запусков. Slurm job отчёта: "+os.environ.get("SLURM_JOB_ID","unknown")+". Время — UTC; Москва UTC+3.")
para("## Главный вывод")
para("**Новый текущий блокер: "+outdent["failed_shard"]+" (job "+outdent["failed_job"]+").** Шард сохранил "+
 str(outdent["archived_shard_attempts"])+" меток, но содержит "+str(outdent["archived_disagreements"])+
 " необъяснённое whole-proof/replay расхождение и не прошёл gate. Поэтому наличие его manifest не означает готовности downstream анализа. Этот дефект теперь первый приоритет.")

para("Измерительный контур стал надёжнее, но основные научные предсказания пока нельзя объявить подтверждёнными. Генерация сохранена; исправленная проверка Lean продолжается. P4 воспроизвёл обучение без подтверждённого перехода хвостового индекса. Дедукционные пилоты не прошли допуск по формату. Новая проверка P3 отделяет проблемы оптимизации от порога, отбора и малого объёма калибровки.")
para("Новая независимая проверка завершена: "+str(selection["parent_datasets"])+" родительских наборов и "+str(selection["analysis_conditions"])+" условий по объёму calibration. Кандидат зафиксирован заранее: "+primary+". "+("Семейная проверка Monte Carlo обнаружила недопокрытие: "+", ".join(under)+"." if under else "Семейная проверка Monte Carlo не обнаружила недопокрытия в четырёх точных hard-сценариях; это не доказательство номинального покрытия на реальных данных.")+" Основной метод не заменён.")
para("Для дальнейшей работы: [план](NEXT_PLAN.md), [задание другому GPT](FOR_REVIEWING_GPT.md), [метрики](metrics.json), [все ячейки P3](P3_ALL_CELLS.md), [независимая сверка интервалов](selection-integrity.json).")
para("## Границы ревизии")
para("Проверены текущие очереди, завершённые main-шарды, валидация Lean и смысл native-policy исключений, оба пилота дедукции, происхождение пилотных контролей, все парные P4, новый и предыдущий P3. Хеши проверяются рекурсивно на сервере. Полные веса и активации остаются на сервере. Это не новый прогон всех исторических симуляций и всех экспериментов draft.")
table(["Ветка","Вычислительное состояние","Научное состояние"],[
["Основная Lean","Генерация сохранена; проверка/последующие стадии выполняются","Полные P1/P2/P3 ещё не готовы"],
["P3 optimizer","Численные проверки и независимая валидация завершены","Ремонт optimizer сам по себе не устраняет недопокрытие"],
["P3 threshold/selection","Новая фиксированная проверка завершена","Ограничения и все сценарии ниже"],
["Whitening/позиция","Пилотная сетка завершена; main ждёт измерений","Чувствительность к calibration и первому шагу"],
["P4","Парные real/null завершены","Обучение есть; ожидаемый переход xi не показан"],
["Дедукция/P5","Два development-пилота не прошли gate","Main закрыт; P5 пока не тестируется"],
["Программа draft","Реализована частично","Нельзя заявлять полную репликацию"]])
para("## Основная кампания")
table(["Модель","Сохранено генераций","Задач","Шардов с manifest","Архивных меток шардов","Строк в текущих журналах"],
 [[m,v["saved_attempts"],v["distinct_tasks"],len(main_shards[m]["completed_shards"]),main_shards[m]["final_labels"],sum(p["complete_records"] for p in v["verification_progress"])] for m,v in main.items()])
para("Всего сохранено "+str(sum(v["saved_attempts"] for v in main.values()))+" попыток. Архивные метки шардов с manifest (включая шард с непройденным gate) сверены по request_sha256=identity исходных попыток; посторонних ID, дублей и нарушений absorption не найдено. Исходные токены не перегенерировались. Это проверка целостности и формальных инвариантов, не ручное доказательство правильности каждой метки.")
table(["Очередь","Состояния","Последний опрос UTC"],[[k,json.dumps(v["counts"]),v["last_poll_utc"]] for k,v in queues.items()])
table(["Модель","Стадия","Итоговый manifest доступен"],[[m,s,bool(main[m]["main"][s])] for m in main for s in ("verification","extraction","measurement","analysis")])
para("Захваченный squeue:")
para("~~~text\n"+(out/"inputs/squeue.txt").read_text(encoding="utf-8").strip()+"\n~~~")
para("COMPLETED в графе задач включает сохранённые входы и зависимости; это не процент научной готовности. Частичные журналы не заменяют итоговый gather. Отдельная старая очередь относится к истории прежнего инцидента. В текущем v7 есть собственный отказ Kimina, разобранный ниже.")
table(["Модель","Категория архивных меток","Число"],[[m,k,n] for m,v in main_shards.items() for k,n in v["categories"].items()])
para("## Новый блокер Kimina и проверка исправления")
para("Сохранённый случай: "+outdent["trace_id"]+". В _finalise удалялось фиксированное число символов, а не только пробелы; у строки с меньшим отступом оператор <;> превращался в >. Диагностика выполнялась на тех же исходных токенах в свежих REPL-сессиях.")
table(["Режим","Whole proof","Replay","Категория"],[[r["method"],r["whole_proof_ok"],r["replay_ok"],r["category"]] for r in outdent["fresh_summary"]])
para("Изолированный кандидат прошёл ограниченную проверку: "+str(outdent["candidate_passed_bounded_review"])+
 "; сохранение токенов "+str(outdent["token_preservation_passed"])+"/"+str(outdent["token_preservation_cases"])+
 "; прежние регрессии "+str(outdent["previous_regression_matches"])+"/"+str(outdent["previous_regression_cases"])+
 ". Это не полный допуск новой production-версии. Основные метки, очередь и guard не переписаны.")
table(["Модель","Шарды с архивным manifest","Из них gate passed","Архивные метки","Метки gate-passed шардов"],
 [[m,len(v["completed_shards"]),v["gate_passed_shards"],v["final_labels"],v["gate_passed_labels"]] for m,v in main_shards.items()])
para("Более свежий срез очередей перед финализацией:")
table(["Очередь","Состояния","Последний опрос UTC"],[[k,json.dumps(v["counts"]),v["last_poll_utc"]] for k,v in current_queues.items()])
para("Продолжить: оформить узкое исправление в новом snapshot, выполнить полный набор тестов и live-gate, затем восстановить зависимую ветку в новой recovery lineage с прежними генерациями. Нельзя просто заменить FAILED на COMPLETED или удалить несогласованную трассу. Продолжающиеся основные задачи сохраняют свои результаты.")
para("## Lean: надёжность и исключения")
para("Авторитетный snapshot: "+str(source.parent)+". SHA256 source-manifest: "+digest(source)+". Git commit и dirty state записаны в manifests. Точная версия задаётся замороженными хешами, а не только commit.")
table(["Полная валидация","Результат"],[[k,v] for k,v in validation["test_counts"].items()])
para("Полный набор включал live Lean и GPT-2. Дополнительно проверены реальные доказательства, scopes без переноса константы-ответа, proofStatus, очистка процессов, отделение I/O от математических ошибок и полный toolchain на диске узла. Успех этих проверок не означает, что первопричина сетевого I/O установлена.")
ar=pilot_attestation["data"];cr=compiler_review["data"]
para("Содержательный разбор фиксированного gate-пакета: "+str(ar["reviewed_examples"])+" примеров, "+str(ar["compilations"])+" компиляций; инфраструктурных ошибок "+str(cr["infrastructure_errors"])+", нарушений absorption "+str(cr["absorbing_violations"])+". Это ревью ассистентом, не человеческая подпись и не случайная выборка main. "+link(audit/"8466083-review-attestation/case-review.json","Пояснения по каждому случаю")+".")
table(["Модель","Native-policy-only исключения","Меток в проверенных main-шардах"],[[m,v["native_policy_only"],v["final_labels"]] for m,v in main_shards.items()])
para("Native-policy-only: whole proof и replay прошли, буквальных formal sorry/admit нет, но фиксированная allowlist не разрешает вспомогательную аксиому native_decide, которую создаёт pinned Lean. Это нельзя называть математической ошибкой модели. Основные метки сохранены. Native-inclusive анализ потребует отдельного режима доверия, проверки происхождения аксиом и нового manifest; регулярная allowlist только по имени недостаточна.")
para("## P3: от численной ошибки к порогу и отбору")
para("Предыдущая диагностика выявила неустойчивость старого fit около границы параметров. Ограниченный кандидат ищет внутренние stationary maxima при gamma > -1 и сравнивает их с uniform boundary. Победа границы остаётся недоступной оценкой, а внутренние отрицательные gamma сохраняются.")
para("Численный preflight: "+str(p3_candidate["preflight"]["cases"])+" случаев; проверено на плотной сетке "+str(p3_candidate["fresh_point_checks"])+" точек, расхождений "+str(p3_candidate["fresh_point_mismatches"])+". Предыдущая независимая validation: "+str(p3_candidate["validation"]["datasets"])+" наборов. "+link(audit/"reviews/p3-constrained-validation-v3/REPORT.md","Полный предыдущий отчёт")+".")
para("Если ошибки отбираются только выше c, fit excess Z−tau при tau<c использует неверную нижнюю границу. При корректном u>=c условная GPD сохраняет gamma, а scale меняется как sigma+gamma*u. Эта идентичность проверена до новой генерации. [Первичная работа о threshold exceedances](https://academic.oup.com/jrsssb/article/52/3/393/7027838).")
table(["Параметр нового протокола","Значение"],[
["Seed",selection_protocol["seed"]],["Наборов на сценарий",selection_protocol["datasets_per_scenario"]],
["Calibration задач",selection_protocol["calibration_budgets"]],["Evaluation задач",selection_protocol["evaluation_tasks"]],
["Support-pilot задач",selection_protocol["support_tasks"]],["Calibration шагов/задачу",selection_protocol["steps_per_calibration_task"]],
["Failure значений/задачу",selection_protocol["failures_per_task"]],["q",selection_protocol["q"]],
["Bootstrap",selection_protocol["statistics"]["bootstrap"]],["Минимум задач",selection_protocol["statistics"]["min_tasks"]],
["Primary candidate",primary]])
table(["Метод","Правило и данные"],[
["original","tau из calibration; fit на evaluation"],
["observed_minimum","max(tau,min evaluation failure): выбор нижней границы на той же выборке"],
["independent_floor","max(tau,min support-pilot failure): отдельная выборка для границы, fit на evaluation"],
["oracle_correct_selection","max(tau,true c): диагностическое недоступное на реальных данных знание"],
["pooled_original","tau из calibration; fit на evaluation+pilot: тот же общий failure-бюджет, что у independent_floor"]])
para("Calibration двух объёмов вложена. Потоки calibration/evaluation/support независимы; bootstrap пересэмплирует задачи во всех группах и пересчитывает порог. Optimizer совпадает с ранее замороженным байт-в-байт. Все методы и percentile/basic сохранены. SeedSequence и роли потоков указаны в протоколе. [Документация NumPy](https://numpy.org/doc/stable/reference/random/bit_generators/generated/numpy.random.SeedSequence.html).")
para("Hard-сценарии включают положительную форму с двумя границами отбора, exponential и bounded null. Soft stress использует плавную вероятность отбора с ненулевым фоном: конечная выбранная выборка не имеет точного GPD-распределения. Её результаты — восстановление parent/asymptotic target при ошибке спецификации, а не точное coverage GPD. Oracle там неприменим.")
para("### Результаты percentile: все методы и бюджеты")
table(["Сценарий","Calibration","Метод","Доступность","Покрытие доступных","Попадание / все","Bias","Width"],
 [[name,budget,method,prop(c["availability"]),prop(c["coverage_conditional"]),prop(c["coverage_counting_unavailable_as_failure"]),
   num(c["mean_point_bias"]),num(c["mean_width"])]
  for name,s in selection["scenarios"].items() for budget in selection_protocol["calibration_budgets"] for method in selection_protocol["methods"]
  for c in [s["cells"][budget+"/"+method+"/percentile"]] if c["applicable"]])
para("«Попадание / все» считает отсутствие интервала неуспехом процедуры. Это не условное покрытие. Все basic, Monte Carlo CI, направления промахов и причины недоступности — в P3_ALL_CELLS.md.")
para("### Зафиксированный кандидат: неопределённость Monte Carlo")
table(["Hard-сценарий","Покрытие","Семейные MC bounds","Недопокрытие обнаружено"],
 [[name,prop(selection["scenarios"][name]["cells"][primary]["coverage_conditional"]),ci(d["mc_family_95_bounds"]),d["undercoverage_detected"]]
 for name,d in selection["primary_family_monte_carlo"].items()])
para("Семейные bounds учитывают четыре hard-сценария фиксированного кандидата. Это не поправка за выбор лучшей ячейки из всей сетки и не тест эквивалентности номинальному уровню. Выбирать победителя после просмотра этой таблицы нельзя.")
table(["Сценарий","Calibration","Сравнение independent_floor с","Общие доступные","Попадания reference / candidate","Выиграно / потеряно интервалов"],
 [[name,budget,ref,p["common"],str(p["reference_covered_common"])+" / "+str(p["candidate_covered_common"]),
 str(p["gained_intervals"])+" / "+str(p["lost_intervals"])]
 for name,s in selection["scenarios"].items() for budget in selection_protocol["calibration_budgets"]
 for ref in ("original","pooled_original","oracle_correct_selection")
 if budget+"/independent_floor_vs_"+ref+"/percentile" in s["paired"]
 for p in [s["paired"][budget+"/independent_floor_vs_"+ref+"/percentile"]]])
para("Independent floor меняет само правило порога; его перенос в primary P3 был бы изменением протокола. Oracle — контроль механизма, не практическое решение. Увеличение calibration одновременно влияет на точность tau и прохождение gate; поэтому оба показателя отчётны.")
para("q=0.001, межзадачная heterogeneity, сильная зависимость шагов, whitening и поглощающий отбор первой ошибки не проверены этим генератором. Значения внутри синтетических групп независимы; task-bootstrap не делает их реалистично зависимыми. Хороший результат здесь не устанавливает калибровку реального Lean.")
para("Независимая сверка по сохранённым draws: "+str(selection_audit["checks"]["gates_and_arrays"])+" условий gate/массивов, "+str(selection_audit["checks"]["summary_cells"])+" сводных ячеек, несовпадений "+str(selection_audit["mismatches"])+". Это аудит отчётности, не второй независимый симулятор.")

para("### Содержательные выводы новой проверки")
o=selection["scenarios"]["original_support"]["cells"]
para("В original_support исходный current/original даёт "+prop(o["current/original/percentile"]["coverage_conditional"])+
     ". При большей calibration original даёт "+prop(o["larger/original/percentile"]["coverage_conditional"])+
     ", independent_floor "+prop(o["larger/independent_floor/percentile"]["coverage_conditional"])+
     ", oracle "+prop(o["larger/oracle_correct_selection/percentile"]["coverage_conditional"])+
     ". Все эти larger-методы доступны на "+str(o["larger/independent_floor/percentile"]["availability"]["datasets"])+" наборах. Pooled original при том же общем failure-бюджете даёт "+prop(o["larger/pooled_original/percentile"]["coverage_conditional"])+". Это поддерживает диагноз ошибки нижней границы: эффект не объясняется одним только добавлением failure-наблюдений.")
para("У current independent_floor условное покрытие "+prop(o["current/independent_floor/percentile"]["coverage_conditional"])+
     " достигается при доступности "+prop(o["current/independent_floor/percentile"]["availability"])+
     ". У larger доступность "+prop(o["larger/independent_floor/percentile"]["availability"])+
     ". Поэтому прежняя потеря интервалов действительно связана с объёмом calibration, но её устранение не гарантирует правильного coverage.")
table(["Hard-сценарий","Percentile primary","Basic того же метода","Промахи percentile ниже / выше истины","Point bias","Порог ниже support (point / bootstrap)"],
 [[name,prop(s["cells"][primary]["coverage_conditional"]),prop(s["cells"]["larger/independent_floor/basic"]["coverage_conditional"]),
  str(s["cells"][primary]["miss_below_truth"])+" / "+str(s["cells"][primary]["miss_above_truth"]),
  num(s["cells"][primary]["mean_point_bias"]),
  str(s["cells"][primary]["point_threshold_below_support"])+" / "+str(s["cells"][primary]["bootstrap_threshold_below_support"])]
  for name,s in selection["scenarios"].items() if selection_protocol["scenarios"][name]["selection"]=="hard"])
para("В остальных hard-сценариях порог уже лежит выше c; методы original, independent_floor и oracle в larger-режиме совпадают. Недопокрытие сохраняется даже с известной истинной границей. Почти все промахи направлены вниз, point bias отрицателен. Это указывает на оставшуюся проблему конечновыборочного смещения/центрирования bootstrap-интервала; данная проверка не разделяет до конца вклад MLE, случайного числа превышений и bootstrap.")
para("Basic частично улучшает долю попаданий, но не был фиксированным primary. Переназначить его победителем по этой таблице нельзя. Следующий ограниченный диагноз: сравнить известный фиксированный threshold с пересчитываемым threshold на сохранённых моделях, затем зафиксировать одну inferential процедуру и проверить её на fresh validation. Не требуется новая генерация моделей.")
soft=selection["scenarios"]["soft_selection_stress"]["cells"][primary]
para("В soft stress primary доступен на "+prop(soft["availability"])+
     ", условное восстановление target "+prop(soft["coverage_conditional"])+
     ", попадание на всей запланированной выборке "+prop(soft["coverage_counting_unavailable_as_failure"])+
     ". Причины недоступности: "+json.dumps(soft["unavailable_reason_sets"])+". При мягком отборе независимый минимум не даёт полезной hard-support гарантии; ограничение объёма failure-tail остаётся.")
para("Итоговое решение P3: кандидат не прошёл критерий надёжного номинального percentile coverage. Основной production не меняется. Простое увеличение calibration и ремонт optimizer не закрывают статистическую задачу.")

para("## Whitening и позиционные эффекты")
para("Пилотная сетка сохранена из раннего lineage. Сравнение семантических меток с текущей версией ниже. Оно не доказывает равенства заново извлечённых активаций. Main-контроли работают от новой основной кампании и до завершения зависимостей не считаются полученными.")
table(["Модель","Control root","Общих ID","Изменённых семантических меток","ID только с одной стороны"],
 [[m,v["control_model_root"],v["shared_ids"],v["changed_semantic_labels"],len(v["only_old_ids"])+len(v["only_new_ids"])] for m,v in pilot_lineage.items()])
control_rows=[]
for m,cs in pilot_controls.items():
    for name,data in cs.items():
        if not name.startswith("whitening"):continue
        v=data["variant"];s=v["specification"];t=v.get("threshold")
        if not t:continue
        e=t["evaluation"]["accepted_evaluation"]
        control_rows.append([m,name,s["disjoint"],s["drop_first"],s["shrinkage"],v["fit_increments"],v["effective_fit_tasks"],
            v["overlap_tasks"],num(t["tau"]),str(e["exceedances"])+"/"+str(e["steps"]),num(e["exceedance_rate"])])
table(["Модель","Вариант","Disjoint","Drop first","Shrinkage","Fit шагов","Fit задач","Overlap задач","tau","Accepted > tau","Доля"],control_rows)
para("Повторное использование calibration для transform и threshold занижает порог относительно новых трасс. Disjoint меняет результат, но малая выборка не устанавливает номинальную tail-вероятность. Shrinkage и исключение первого приращения остаются вторичными проверками; основной слой/статистика/температура сохранены.")
table(["Модель","Статистика","Трасс/задач","Jump top1","Surprisal top1","Парный gain","CI"],
 [[m,stat,str(v["P2"]["all"]["n_traces"])+"/"+str(v["P2"]["all"]["n_tasks"]),num(v["P2"]["all"]["jump_top1"]),
 num(v["P2"]["all"]["surprisal_top1"]),num(v["P2"]["all"]["paired_gain"]),ci(v["P2"]["all"]["paired_ci95"])]
 for m,cs in pilot_controls.items() for stat,v in cs["positional"]["cells"].items()])
para("Jump и surprisal сравниваются на одинаковых trace IDs. При недостатке независимых задач CI отсутствует. Исключение первого шага может исключить и трассы, ошибившиеся на нём: популяция меняется. Высокий raw top1 без позиционного контроля не доказывает локализацию математического отказа.")
para("## P4: все парные real/null")
table(["Arm","Seed","Финальная test accuracy","Moment до / после","GPD до / после","Hill до / после","Решение"],
 [[v["arm"],v["seed"],num(v["final"]["test_acc"]),
 num(v["measurement"]["primary_transition"].get("moment",{}).get("before"))+" / "+num(v["measurement"]["primary_transition"].get("moment",{}).get("after")),
 num(v["measurement"]["primary_transition"].get("gpd",{}).get("before"))+" / "+num(v["measurement"]["primary_transition"].get("gpd",{}).get("after")),
 num(v["measurement"]["primary_transition"].get("hill",{}).get("before"))+" / "+num(v["measurement"]["primary_transition"].get("hill",{}).get("after")),
 v["measurement"]["scientific_decision"]] for v in p4])
para("NA у null означает отсутствие собственного перехода generalization. Парное сравнение использует real-reference каждого seed:")
table(["Seed","Reference step","Δ moment real","Δ moment null","Парная Δ moment","Парная Δ GPD","Парная Δ Hill"],
 [[p["seed"],p["real_reference_step"],num(p["real"]["moment"]),num(p["null"]["moment"]),
   num(p["paired_difference"]["moment"]),num(p["paired_difference"]["gpd"]),num(p["paired_difference"]["hill"])]
  for p in p4_summary["pairs"]])
para("Окна вокруг устойчивого перехода test accuracy и fixed-final-frequency измерения сохранены в metrics. Null сопоставляется по парной reference-точке. Независимая единица межзапускового сравнения — training seed. Checkpoint и примеры сложения не увеличивают число независимых training-репликаций.")
para("Пять пар дают ограниченную мощность. Итог: обучение подтверждено; ожидаемый переход xi не продемонстрирован. Отрицательная точечная moment/GPD сама по себе не доказывает bounded support, а положительный Hill не доказывает тяжёлый хвост. Все три оценивателя показаны без clipping gamma.")
para("Fixed-fraction кривые measurement и полная tail-сетка с выбором k — разные анализы. Полные tail/step-*.json включены. Старые GPD bootstrap сохраняют ограничения прежнего fit и не заменены новым кандидатом в этой ревизии.")
para("## Дедукция и P5")
para("worked-example-v2: "+json.dumps(ded_v2_counts,ensure_ascii=False)+". Полный аудит в metrics.json → deduction_v2_review. numbered-slots-v3: "+json.dumps(deduction_exact.get("label_summary",{}),ensure_ascii=False)+". Оба пилота не прошли gate; main остаётся закрыт.")
para("Gold-checker проверки, исходные ответы и причины исключений сохранены. Задачи между пилотами свежие: это не парный причинный тест промптов. Неизвестные строки/комментарии не удалялись ради gate. Формат и reasoning разделены: повтор исходного факта не считается новым modus ponens.")
para("P5 требует управляемой длины и отложенных задач/длин. Из одной зависимости exp(-theta*L*Fbar(tau)) свободные theta и tau не определяются раздельно без дополнительных ограничений: length-данные определяют произведение. Нужно фиксировать tau и calibration law, отдельно проверять зависимость; сильное утверждение о tolerance требует интервенции по tolerance.")
para("## Остаток полного контракта статьи")
table(["Раздел","Что ещё нужно"],[
["P1/P2/P3 main","Полная разметка → активации → измерения → фиксированный анализ → согласованные контроли"],
["P1","Все три gamma, k-устойчивость и bands, семейства задач, split-half, task resampling и честные NA"],
["P2","Парный surprisal, позиционный null по длине/семейству, первый шаг, ROC; supervised probe отдельной работой"],
["P3","q=0.001, зависимость, heterogeneity, selection и независимая калибровка до confirmatory CI"],
["P4","Итоговый paired seed рисунок/вывод с ограничениями; без новых seeds ради желаемого знака"],
["P5","Допуск deduction, held-out длины/задачи, идентифицируемая модель и зависимый null"],
["Kesten/Figure 1","Отдельно сверить publication-run с контрактом и digests; здесь симуляция заново не запускалась"],
["Другие ветки","ProofNet/PutnamBench, другие deduction-модели, two-hop, recurrent depth, Tracr/ngram нельзя считать завершёнными"],
["Публикация","Generated tables/figures, compute accounting, исключения, анонимный репозиторий и ограничения"]])
para("## Следующие действия и независимый аудит")
para("Подробные приоритеты, зависимости и критерии завершения — в [NEXT_PLAN.md](NEXT_PLAN.md). Ближайший результат: целостная основная выборка и контроли на одной версии измерений, затем научное решение по фиксированной ячейке. Рост данных не исправляет ошибку модели отбора.")
para("artifact-index.json сопоставляет серверные пути, копии и SHA256. manifest.json содержит provenance отчёта, package versions, hardware и digests. source/ — основной v7; экспериментальный P3-код — в artifacts/audit/revision_2026_09_13/p3_selection_v1/code. Все новые bootstrap draws включены. Отсутствующие внешние веса/активации reviewer должен явно перечислить как непроверенные.")
(out/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
lines=[]
para("# P3: все ячейки и причины недоступности")
for scenario,item in selection["scenarios"].items():
    para("## "+scenario)
    table(["Ячейка","Доступность","Условное покрытие","MC CI95","Попадание / все","Bias","Width","Промах ниже / выше"],
      [[key,prop(c["availability"]),prop(c["coverage_conditional"]),ci(c["coverage_conditional"]["monte_carlo_ci95"]),
      prop(c["coverage_counting_unavailable_as_failure"]),num(c["mean_point_bias"]),num(c["mean_width"]),
      str(c["miss_below_truth"])+" / "+str(c["miss_above_truth"])]
      for key,c in item["cells"].items() if c["applicable"]])
    for key,c in item["cells"].items():
        if not c["applicable"] or not key.endswith("/percentile"):continue
        para("### "+key)
        para("Недоступность: "+json.dumps(c["unavailable_reason_sets"],ensure_ascii=False)+".")
        para("Bootstrap fit: "+json.dumps(c["bootstrap_fit_reasons"],ensure_ascii=False)+".")
        para("Порог ниже support, original / bootstrap: "+str(c["point_threshold_below_support"])+" / "+str(c["bootstrap_threshold_below_support"])+".")
(out/"P3_ALL_CELLS.md").write_text("\n".join(lines),encoding="utf-8")


for filename in ("NEXT_PLAN.md","FOR_REVIEWING_GPT.md"):
    template=out/"code"/(filename+".template")
    inputs.append(template)
    shutil.copy2(template,out/filename)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig,axes=plt.subplots(2,2,figsize=(16,10),sharex=True,sharey=True)
names=list(selection_protocol["scenarios"])
colors=plt.get_cmap("tab10")
for bi,budget in enumerate(selection_protocol["calibration_budgets"]):
    for col,key in enumerate(("availability","coverage_conditional")):
        ax=axes[bi,col]
        for mi,method in enumerate(selection_protocol["methods"]):
            for si,name in enumerate(names):
                c=selection["scenarios"][name]["cells"][budget+"/"+method+"/percentile"]
                if not c["applicable"]:continue
                p=c[key]; value=p["fraction"]
                if value is None:continue
                low,high=p["monte_carlo_ci95"]
                ax.errorbar(si+(mi-2)*.13,value,yerr=[[value-low],[high-value]],
                            fmt="o",markersize=4,capsize=2,color=colors(mi),
                            label=method if si==0 else None)
        ax.axhline(.95,color="black",linestyle="--",alpha=.4)
        ax.axvspan(3.55,4.5,color="orange",alpha=.08)
        ax.set_ylim(0,1.03);ax.set_xlim(-.5,4.5)
        ax.set_title(budget+" calibration: "+("interval availability" if col==0 else "target inclusion, conditional"))
        ax.set_xticks(range(len(names)),[x.replace("_","\n") for x in names],fontsize=8)
        ax.grid(axis="y",alpha=.15)
axes[0,0].legend(fontsize=8,loc="lower left")
fig.suptitle("P3 fixed threshold/selection validation\nSoft selection: misspecified target recovery, not exact GPD coverage",fontsize=13)
fig.tight_layout(rect=(0,0,1,.94))
fig.savefig(out/"p3-selection.png",dpi=180)
fig.savefig(out/"p3-selection.pdf")
plt.close(fig)
report=(out/"REPORT.md").read_text(encoding="utf-8")
report=report.replace("### Зафиксированный кандидат: неопределённость Monte Carlo","![P3: доступность и попадание в target](p3-selection.png)\n\n### Зафиксированный кандидат: неопределённость Monte Carlo")
(out/"REPORT.md").write_text(report,encoding="utf-8")

plan=(out/"NEXT_PLAN.md").read_text(encoding="utf-8")
urgent=("# Текущий первый приоритет: восстановить ветку Kimina\n\n"
 "Аудит обнаружил отказ "+outdent["failed_shard"]+" в задании "+outdent["failed_job"]+
 ". Все ответы шарда обработаны, но guard правильно остановил downstream из-за whole-proof/replay расхождения. "
 "Причина — удаление непробельных символов при dedent строки с меньшим отступом. "
 "Результат ограниченной проверки кандидата: "+str(outdent["candidate_passed_bounded_review"])+".\n\n"
 "Ближайшая последовательность: новый immutable snapshot с узким исправлением _finalise и регрессией на сохранённый случай; "
 "make test и make test-all в Slurm; live-gate; новая recovery lineage для затронутой проверки с сохранёнными генерациями; "
 "явная проверка совместимости остальных шардов; только затем gather и разблокирование зависимых контролей. "
 "Не исправлять состояние очереди вручную в обход gate и не удалять несогласованную трассу. "
 "Работающие основные задачи сохранять. Ограниченный replay-кандидат ещё не является production-допуском.\n\n"
 "P3 уже показал оставшееся недопокрытие. Следующая узкая CPU-диагностика — известный фиксированный threshold против пересчитываемого, "
 "чтобы разделить вклад MLE bias и bootstrap-центрирования. Basic выглядит лучше, но не переименовывается в основной после просмотра данных.\n\n")
(out/"NEXT_PLAN.md").write_text(urgent+plan,encoding="utf-8")
review=(out/"FOR_REVIEWING_GPT.md").read_text(encoding="utf-8")
(out/"FOR_REVIEWING_GPT.md").write_text(
 "# Новый блокер, который нужно проверить первым\n\n"
 "Один Kimina shard имеет полный manifest, но не прошёл semantic gate. Не считать такой manifest достаточным допуском к анализу. "
 "Проверь превращение <;> в > при dedent, изолированный candidate и его границы проверки. "
 "Production-исправление и восстановление ветки пока не выполнены.\n\n"+review,encoding="utf-8")
write_once(out/"artifact-index.json",artifacts)
(out/"PACKAGING.md").write_text(
 "# Provenance of the final report\n\n"
 "The numerical collector finished in job 8466129 and saved metrics after all data checks; "
 "a later text-rendering step failed on the intentionally unavailable soft-selection oracle. "
 "This finalizing Slurm job verifies each copied evidence file against its original, records "
 "a separate validation manifest beside that completed checkpoint, and renders the report again. "
 "The earlier failure is preserved in inputs/collector-log.txt. No experiment is rerun or altered "
 "to repair presentation. The new independent Lean blocker diagnosis has its own manifest.\n\n"
 "All final package outputs have fixed hashes. Slurm stdout is outside the final output folder. "
 "Upstream recursive verification was performed by the numerical collector before the checkpoint; "
 "the finalizer verifies copied-file identity and the additional blocker manifest. "
 "External weights and the entire activation dataset remain on Zhores.\n",encoding="utf-8")
outputs=[p for p in out.rglob("*") if p.is_file()]
manifest=finish(out,stage="whole-project-review-with-new-main-blocker",
 context={"source":digest(source),"collector_metrics":digest(checkpoint/"metrics.json"),
          "primary_method_changed":False},
 inputs=list(dict.fromkeys(inputs)),outputs=outputs,
 metrics={"collector_complete":True,"report_complete":True,"primary_method_changed":False,
          "p3_selection_validation_complete":True,"p3_recheck":selection_audit,
          "new_main_blocker":outdent["failed_shard"],"bounded_candidate_passed":outdent["candidate_passed_bounded_review"]})
verify_manifest(manifest)
print("FINAL_REPORT_VERIFIED",out,flush=True)
import zipfile
delivery=audit/"delivery-whole-project-final-v1"
delivery.mkdir(exist_ok=False)
archive=delivery/"onebigjump-full-review-20260913.zip"
with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(out.rglob("*")):
        if p.is_file():z.write(p,Path("whole-project-review")/p.relative_to(out))
receipt=write_once(delivery/"metrics.json",{
 "archive":str(archive),"archive_sha256":digest(archive),"archive_bytes":archive.stat().st_size,
 "files":sum(p.is_file() for p in out.rglob("*")),"report":str(out/"REPORT.md"),"plan":str(out/"NEXT_PLAN.md"),
 "report_manifest_sha256":digest(manifest),"created_utc":datetime.now(timezone.utc).isoformat(),
 "primary_method_changed":False})
finish(delivery,stage="whole-project-review-delivery",context={"source":digest(source)},
 inputs=[source,manifest,Path(__file__)],outputs=[archive,receipt],metrics=read_json(receipt))
(audit/"latest-whole-review.txt").write_text(str(out)+"\n",encoding="utf-8")
print("DELIVERY_COMPLETE",json.dumps(read_json(receipt)),flush=True)
