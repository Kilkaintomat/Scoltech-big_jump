from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import os,json,shutil,xml.etree.ElementTree as ET,zipfile
import numpy as np
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,verify_manifest
from onebigjump.e1.generation import planned_requests

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/statistical-fitness-v1"
OUT=HERE/"report"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
OUT.mkdir(parents=True,exist_ok=True)
a=read_json(HERE/"analysis/metrics.json")
b=read_json(HERE/"benchmark/metrics.json")
activation=read_json(HERE/"activation.json")
checks=read_json(HERE/"activation-preconditions.json")
p3path=BASE/"runs/p3_selection_validation_20260913/metrics.json"
p3=read_json(p3path)
planned={}
for model in ["deepseek","goedel","kimina"]:
    root=BASE/"runs/lean_reverification_20260913_local"/model
    config=read_json(root/"main/protocol.json")
    requests=planned_requests(root,"main",config)
    planned[model]={"attempts":len(requests),"tasks":len({r["problem_id"] for r in requests}),
                   "by_role":{role:{"attempts":sum(r["role"]==role for r in requests),
                                  "tasks":len({r["problem_id"] for r in requests if r["role"]==role})}
                              for role in ["calibration","evaluation"]}}
snap=read_json(HERE/"captured-main-queue.json")
side=read_json(HERE/"captured-sidecar-queue.json")
metrics={
 "created_utc":datetime.now(timezone.utc).isoformat(),
 "analysis":a,"benchmark":b,"activation":activation,"checks":checks,"planned":planned,
 "main_queue_counts":snap["counts"],"main_queue_capture":snap["last_poll_utc"],
 "sidecar_queue_counts":side["counts"],"p3_primary_candidate":p3["config"]["primary_candidate"],
 "p3_calibration":{name:{"current_original":r["cells"]["current/original/percentile"],
                       "larger_independent_floor":r["cells"]["larger/independent_floor/percentile"]}
                   for name,r in p3["scenarios"].items()},
 "p3_mc_family":p3["primary_family_monte_carlo"],
 "failed_jobs":[{"task":key,"job_id":t.get("job_id"),"state":t["state"]} for key,t in snap["tasks"].items() if t["state"]=="FAILED"],
 "bootstrap_primary_unchanged":True,
 "statistical_conclusion":"pilot cannot establish practical advantage or tail mechanism; threshold defect is observable; full sample pending",
 "new_generations_submitted":0,
}
mfile=write_once(OUT/"metrics.json",metrics)

def pct(x):return "—" if x is None else f"{100*x:.2f}%"
def pp(x):return "—" if x is None else f"{100*x:+.2f} п.п."
def ci(x):return "—" if x is None else "["+", ".join(f"{100*v:+.1f}" for v in x)+"] п.п."
lines=[
"# Релевантность статистических проверок и ускорение обработки",
"",
f"Срез сформирован {metrics['created_utc']}. Состояние очереди на {snap['last_poll_utc']}.",
"",
"**Вывод.** Часть требований избыточна для прикладного вопроса «помогает ли скачок найти ошибку», "
"но оправдана для значительно более сильного утверждения о механизме и классе хвоста. Малый пилот "
"не способен надёжно ответить на второй вопрос. При этом старые хвостовые интервалы местами "
"недостаточно осторожны: проблема заключается также в смещении и неполном покрытии, а не только "
"в низкой мощности. Ослабление порогов значимости не исправляет это.",
"",
"**Что уже выполнено.**",
"",
f"- Добавлен и выполнен отдельный анализ парных эффектов по задачам, конечных пороговых частот и позиций.",
"- Исправлена ошибочная трактовка интервала, содержащего ноль, в экспериментальной спецификации.",
f"- Полная проверка: {checks['tests']['tests']} тестов; ошибок {checks['tests']['errors']}, падений {checks['tests']['failures']}, пропусков {checks['tests']['skipped']}. Также прошли ruff и mypy; живые Lean/GPT-2 проверки входят в набор.",
f"- Проверено {b['sampled_traces']} сохранённых доказательств: {b['semantic_equal']} совпадений последовательной/параллельной разметки и {b['archived_equal']} совпадений с архивной разметкой.",
f"- Ускорение включено для {len(activation['changed_waiting_tasks'])} ещё не отправленных фрагментов. Выполнявшиеся задания продолжают работать со своими исходными настройками.",
"- Создана отдельная очередь автоматического дополнительного анализа полной выборки после завершения измерений. Она не ждёт дорогостоящего хвостового bootstrap.",
"",
"**Какой вопрос проверяет каждый анализ.**",
"",
"| Проверка | Подходит ли задаче | Решение |",
"|---|---|---|",
"| P1: Hill, moment, GPD, диапазон k | Нужна для утверждения о промежуточном хвостовом режиме, но избыточна для первого ответа о полезности детектора | Сохранена как исходный анализ механизма; не требовать её успеха для публикации прикладной оценки |",
"| P2: парное сравнение с surprisal | Прямо отвечает на прикладной вопрос, использует те же трассы | Добавлены средний эффект с равным весом задач, границы неопределённости и отдельный точный знаковый экран |",
"| Равномерная перестановка позиций | Сильная предпосылка при выраженных эффектах начала/длины | Оставлена как справочный контроль; сохраняются семейно-позиционные проверки и baseline первого шага |",
"| P3: GPD превышений и совпадение параметров | Нужна для механизма overshoot, требует хвостовых данных и корректного учёта отбора | Исходные результаты сохранены; добавлены простые конечнопороговые частоты без подгонки GPD |",
"| P4: переход формы хвоста при grokking | Проверяет сильное механистическое предсказание | Считать независимыми пары seed; показывать отрицательный/неопределённый результат, не считать checkpoint новой репликацией |",
"| Порог не менее 20 задач | Практический фильтр для старого bootstrap, а не универсальная математическая граница | Старый фильтр сохранён; для дополнительных ограниченных средних возможны честные, широкие границы и при меньшем n |",
"| Поправка за множественные проверки | Защищает от выбора удачной ячейки | Исходная семья сохранена; для новой вторичной прикладной семьи — только три заранее названные whitened-ячейки моделей |",
"| q=0.001 | Крайне дорогая проверка редкого хвоста | Не использовать её недоступность как запрет на прикладной анализ; не повышать q после просмотра результата ради значимости |",
"",
"**Что означает новая статистика.**",
"",
"Для каждой задачи сначала усредняются результаты её подходящих попыток, затем усредняются задачи. "
"Таким образом, десять попыток одной задачи не превращаются в десять независимых задач. Это другой, "
"явно обозначенный объект оценки, чем взвешенное по числу попыток среднее в старом анализе; старый "
"результат не заменён.",
"",
"Парный top-1 эффект равен доле попаданий скачка в первый ошибочный шаг минус доля попаданий surprisal "
"на тех же трассах. В новой сводке каждая задача имеет одинаковый вес. При совпадении максимумов "
"используется самый ранний шаг. Отдельно выведены baseline самого первого шага, нормированный ранг "
"(только разведочный результат) и исключение первого приращения с явным изменением популяции.",
"",
"Для ограниченных независимых средних по задачам используется граница Hoeffding: "
"среднее ± (верхняя−нижняя граница)·sqrt(log(2/alpha)/(2n)), с обрезкой по известному диапазону. "
"Она не требует нормальности или модели хвоста, но может быть очень широкой. Это дополнительная "
"характеристика неопределённости, **не новый обязательный барьер для проекта**. Она условна на "
"независимо оценённое преобразование и независимость задач; сам фиксированный benchmark не доказывает "
"переносимость на все математические задачи. [Hoeffding, 1963](https://doi.org/10.1080/01621459.1963.10500830).",
"",
"Знаковый экран использует точный биномиальный расчёт для вероятности положительного эффекта среди "
"задач без ничьей. Он требует независимых одинаково распределённых знаков и проверяет **не среднюю "
"величину выигрыша**. Ничьи и их число сохранены. Перестановка названий алгоритмов не объявлена "
"автоматически корректной. [SciPy binomtest](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html), "
"[предпосылки permutation_test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html).",
"",
"Границы с поправкой на три модели предназначены только для трёх основных whitened-ячеек нового "
"вторичного анализа. Поля с тем же расчётом в raw/innovation и вариантах исключения не дают общей "
"защиты при выборе между всеми вариантами. Эти варианты остаются разведочными. Поправка исходной "
"подтверждающей семьи не уменьшена.",
"",
"**Что получилось на реальном пилоте.**",
"",
"| Модель | Задач / трасс | Whitened top-1 | Surprisal top-1 | Парный эффект | 95% граница эффекта | Baseline первого шага |",
"|---|---:|---:|---:|---:|---|---:|",
]
for model,r in a["models"].items():
    cell=r["cells"]["whitened"]["P2"];e=cell["estimates"]
    lines.append(f"| {model} | {cell['tasks']} / {cell['traces']} | {pct(e['jump']['mean'])} | {pct(e['surprisal']['mean'])} | {pp(e['gain']['mean'])} | {ci(e['gain']['interval'])} | {pct(e['first_position']['mean'])} |")
lines += [
"",
"Ни одна из этих оценок не устанавливает устойчивого превосходства. Знак эффекта различается между "
"моделями. У DeepSeek простое указание на первый шаг заметно сильнее whitened-скачка в этом пилоте. "
"Малое число задач и условие наличия локализованной ошибки ограничивают переносимость этих частот.",
"",
"| Модель | Raw: эффект | Innovation: эффект | Whitened без первого шага: задач / эффект |",
"|---|---:|---:|---:|",
]
for model,r in a["models"].items():
    cells=r["cells"];d=cells["whitened"]["P2_drop_first"]
    lines.append(f"| {model} | {pp(cells['raw']['P2']['estimates']['gain']['mean'])} | {pp(cells['innovation']['P2']['estimates']['gain']['mean'])} | {d['tasks']} / {pp(d['estimates']['gain']['mean'])} |")
lines += [
"",
"Исключение первого шага здесь оставляет другую, ещё меньшую популяцию. Его нельзя выбирать как "
"новую основную ячейку потому, что знак результата изменился.",
"",
"**Конечнопороговый анализ: видимый дефект без сложной хвостовой модели.**",
"",
"| Модель | Исходный whitening: превышения на правильных шагах | Раздельная калибровка: правильные шаги | Раздельная калибровка: первый ошибочный шаг |",
"|---|---:|---:|---:|",
]
for model,r in a["models"].items():
    old=r["cells"]["whitened"]["finite_threshold"]["groups"]["accepted"]
    new=r["cells"]["whitened_disjoint_0.1"]["finite_threshold"]["groups"]
    correct=new["accepted"];fail=new["first_failure"]
    lines.append(f"| {model} | {old['exceedances']} / {old['steps']} | {correct['exceedances']} / {correct['steps']} | {fail['exceedances']} / {fail['steps']} |")
lines += [
"",
"Это описательные частоты по шагам для наглядности; неопределённость в metrics.json вычисляется "
"по задачам. У исходного порога обе категории оказываются за порогом, поэтому такое превышение "
"плохо разделяет правильные и ошибочные шаги. Разделение данных для transform и threshold улучшает "
"поведение порога, но не создаёт доказательство полезности: независимых калибровочных задач всё "
"ещё мало, а превышения на ошибках не показывают единой картины. Пост-ошибочные unreached-шаги "
"не входят в знаменатель правильных шагов.",
"",
"| Модель | Задач для transform | Задач для threshold | Приращений transform / размерность | Шагов threshold |",
"|---|---:|---:|---:|---:|",
]
for model,r in a["models"].items():
    c=r["cells"]["whitened_disjoint_0.1"]
    lines.append(f"| {model} | {len(c['fit_task_ids'])} | {len(c['threshold_task_ids'])} | {c['fit_increments']} / {c['dimension']} | {c['threshold_steps']} |")
lines += [
"",
"**Почему нельзя просто ослабить требования к хвосту.**",
"",
"Предыдущая независимая проверка P3 сохранила проблему неполного покрытия. Ниже — фиксированный "
"кандидат с большей calibration-выборкой, независимым порогом поддержки и percentile-интервалом. "
"Покрытие считается среди случаев, где интервал доступен; отдельная колонка показывает доступность.",
"",
"| Сценарий | Покрытие доступных интервалов | Доступность | Выявлено недопокрытие с поправкой MC |",
"|---|---:|---:|---|",
]
for name in ["original_support","lower_support","exponential_null","bounded_null"]:
    c=metrics["p3_calibration"][name]["larger_independent_floor"]
    cov=c["coverage_conditional"];av=c["availability"]
    lines.append(f"| {name} | {cov['successes']} / {cov['datasets']} = {pct(cov['fraction'])} | {av['successes']} / {av['datasets']} | {'да' if p3['primary_family_monte_carlo'][name]['undercoverage_detected'] else 'нет'} |")
lines += [
"",
"Номинальная цель — 95%. Следовательно, уменьшение min_tasks или числа обязательных хвостовых "
"превышений может увеличить число выданных интервалов, не исправив их качество. Рост bootstrap B "
"уменьшает только Monte Carlo-погрешность вычисленного интервала; он не добавляет задач и не устраняет "
"смещение оценивателя. Ранее найденный basic-интервал остаётся вторичным наблюдением, не новым "
"подтверждённым основным методом.",
"",
"Следующий узкий методический эксперимент для P3 должен отделить ошибку оценивания GPD от случайности "
"порога: известный фиксированный порог против оценённого, одинаковые объёмы данных, затем свежая "
"проверка заранее выбранного исправления. В этом заходе новые дорогие GPD-симуляции не запускались: "
"прикладной анализ теперь может продвигаться независимо от них.",
"",
"**Пять seed-пар P4 и недостижимые требования.**",
"",
]
size5=next(x for x in a["sign_test_size"] if x["non_tied_tasks"]==5)
lines += [
f"При пяти независимых ненулевых знаках минимально возможное двухстороннее p знакового теста равно "
f"{size5['minimum_two_sided_p']:.4f}: даже совпадение всех знаков не даёт p<0.05. Это свойство "
"конкретного точного теста, а не запрет любому параметрическому тесту работать с пятью наблюдениями. "
"Переходить на односторонний тест после просмотра результатов было бы сменой правила.",
"",
"| Оцениватель | Положительных / отрицательных разностей real−null | Точное двухстороннее p |",
"|---|---:|---:|",
]
for est,r in a["P4_sign_screens"].items():
    lines.append(f"| {est} | {r['wins']} / {r['losses']} | {r['p_two_sided']:.3f} |")
lines += [
"",
"Это дополнительный экран разности изменений в окне реального перехода, а не тест исходного "
"предсказания «положительная gamma до обучения, неположительная после». В общей ревизии моментная "
"и GPD-оценки уже были отрицательны до перехода: отсутствие предсказанного изменения знака нельзя "
"сводить только к нехватке статистической мощности. Новые seed не запускаются ради получения "
"нужного знака.",
"",
"**Сколько у нас данных и что даст увеличение.**",
"",
"| Модель | Сохранённых main-попыток | Всего задач | Calibration: задач | Evaluation: задач |",
"|---|---:|---:|---:|---:|",
]
for model,r in planned.items():
    lines.append(f"| {model} | {r['attempts']} | {r['tasks']} | {r['by_role']['calibration']['tasks']} | {r['by_role']['evaluation']['tasks']} |")
lines += [
"",
"Это план уже сохранённой генерации, не число готовых парных наблюдений. Для P2 останутся задачи "
"с подходящими локализованными ошибками и корректным извлечением; для P3 — ещё более узкий хвостовой "
"поднабор. Число bootstrap-повторов, шагов, температур и слоёв не является числом независимых задач. "
"Модели используют тот же набор задач, поэтому их тоже нельзя механически складывать как "
"независимые репликации.",
"",
"Сначала следует превратить сохранённые генерации в готовые проверенные измерения. Если после "
"полной фиксированной партии точности недостаточно, следующая партия должна расширять число "
"независимых prompts и число проверенных calibration-задач. Повторные попытки полезны для "
"стабилизации оценки внутри задачи, но не заменяют расширение набора задач.",
"",
"| Желаемая полуширина границы среднего парного эффекта | Достаточно задач по Hoeffding, одна оценка | Для одновременных границ трёх моделей |",
"|---|---:|---:|",
]
for r in a["precision_planning"]["distribution_free_gain_bound"]:
    lines.append(f"| ±{100*r['half_width']:.0f} п.п. | {r['tasks_for_marginal_95']} | {r['tasks_for_three_model_95']} |")
lines += [
"",
"Это консервативная достаточная оценка, **не минимально необходимое количество задач** и не новая "
"цель генерации. При дополнительных предпосылках интервалы могут быть существенно уже. Например, "
"нормальная аппроксимация при стандартном отклонении эффекта задачи 0.5 даёт следующие "
"иллюстративные требования к точности, без обещания покрытия на наших данных:",
"",
"| Полуширина | Иллюстративное число задач |",
"|---|---:|",
]
for r in a["precision_planning"]["normal_approximation_gain"]:
    if r["assumed_task_sd"]==.5:
        lines.append(f"| ±{100*r['half_width']:.0f} п.п. | {r['tasks_approx']} |")
lines += [
"",
"Новый объём и момент остановки следует фиксировать по требуемой точности и стоимости до "
"следующего сравнения, а не наращивать выборку до первого значимого p.",
"",
"| q | Целевое ожидаемое число превышений | Шагов calibration в среднем |",
"|---|---:|---:|",
]
for r in a["precision_planning"]["expected_tail_steps"]:
    lines.append(f"| {r['q']} | {r['target_expected_exceedances']} | {r['required_steps_in_expectation']} |")
lines += [
"",
"Это только расчёт ожидания nq, не гарантия количества независимых хвостовых задач. Он объясняет, "
"почему очень редкий хвост требует существенно большего материала, чем практическое сравнение "
"локализации.",
"",
"**Ускорение: что измерено и что включено.**",
"",
"| Модель | Последовательно, с | Четыре процесса, с | Ускорение |",
"|---|---:|---:|---:|",
]
for model in ["deepseek","goedel","kimina"]:
    serial=next(r for r in b["measurements"] if r["model"]==model and r["workers"]==1)
    parallel=next(r for r in b["measurements"] if r["model"]==model and r["workers"]==4)
    lines.append(f"| {model} | {serial['seconds']:.2f} | {parallel['seconds']:.2f} | {serial['seconds']/parallel['seconds']:.2f}× |")
lines += [
f"| Сумма | {b['serial_seconds']:.2f} | {b['parallel_seconds']:.2f} | {b['speedup']:.2f}× |",
"",
"Выборка бенчмарка задана хешем идентичности до запуска, без отбора по результату: по шестнадцать "
"архивных трасс каждой модели. Один раунд измерений; время включает запуск REPL, но не размещение "
"toolchain на узле и проверку всех входных файлов. Поэтому это не обещание такого же ускорения "
"всей очереди. В боевом режиме больше трасс приходится на один запуск Lean, но долговременная "
"скорость и память ещё требуют наблюдения.",
"",
"Каждый процесс Lean получает собственное состояние; главный поток единолично пишет журнал. "
"Завершённые результаты записываются по мере готовности, а ошибка работника закрывает процессы "
"и прерывает успешное завершение стадии. Сохранены бюджеты heartbeat, времени, исходные токены, "
"список задач и исходный verifier. Проверяются дубликаты и пропуски. Тайминги, номера окружений "
"и текст диагностических сообщений не использовались как критерий семантического равенства; "
"сравнивались категории, whole/replay, t*, бюджеты, axioms, spans и поля шагов без времени/сообщений.",
"",
"Новые задания получают те же 32 CPU и четыре REPL; память увеличена до 96 GiB с учётом "
"наблюдавшихся затрат памяти. Это эксплуатационный параметр, не изменение научной процедуры. "
"Текущие выполняющиеся задания не отменены и не пересозданы.",
"",
"Новый прикладной анализ работает отдельно от nested bootstrap, не меняя исходный P1–P5. "
f"Пилотный расчёт с перепроверкой disjoint-whitening и {sum(r['datasets'] for r in a['calibration'].values())} "
f"простыми синтетическими наборами занял {a['analysis_seconds']:.2f} с внутри Python. Это другая "
"задача, поэтому эту длительность нельзя трактовать как ускорение самого GPD-bootstrap.",
"",
"**Проверка новых вычислений.**",
"",
"В синтетическом экране задачи независимы, их вероятности неодинаковы, а повторы внутри задачи "
"совершенно зависимы. Сохранены исходные массивы и границы всех реплик. Экран проверяет реализацию "
"известной границы, не удостоверяет независимость реальных задач.",
"",
"| Задач | Сдвиг вероятности | Наборов | Покрытие границы |",
"|---|---:|---:|---:|",
]
for name,r in a["calibration"].items():
    fields=name.split("_")
    lines.append(f"| {fields[1]} | {fields[3]} | {r['datasets']} | {pct(r['coverage'])} |")
lines += [
"",
"Границы здесь сильно консервативны. Это ожидаемая цена слабых предпосылок, а не причина считать "
"их единственным способом вывода. Дополнительно проверен точный уровень знакового теста "
"перебором всех биномиальных исходов, а интеграционный запуск будущего main-runner в точности "
"воспроизвёл пилотные значения.",
"",
"**Текущее состояние и следующие действия.**",
"",
f"Основная очередь: {json.dumps(snap['counts'],ensure_ascii=False)}. Дополнительная очередь: "
f"{json.dumps(side['counts'],ensure_ascii=False)}.",
"",
]
for r in metrics["failed_jobs"]:
    lines.append(f"Сохраняется незавершённая техническая ветка {r['task']} (Slurm {r['job_id']}).")
lines += [
"",
"Обнаруженная ранее ошибка сегментации Kimina не маскируется ускорением. Её отдельное исправление "
"прошло ограниченный replay-review в предыдущей ревизии, но в этой смене планировщика ядро verifier "
"намеренно оставлено побайтно совместимым с текущей линией. Ошибочный фрагмент продолжает блокировать "
"зависимое объединение; наличие файла manifest не делает его успешно принятым.",
"",
"1. Уже включено: закончить оставшиеся фрагменты сохранённой генерации через новый обработчик; "
"контролировать реальные память, число тайм-аутов, скорость и успешность объединения.",
"2. Уже поставлено в автоматическую очередь: сразу после готовности main-measurement получить "
"парные прикладные оценки трёх моделей. Одновременно выполняются ранее запланированные проверки "
"whitening и позиций; их исходная основная ячейка сохранена.",
"3. Отдельный ближайший технический шаг: завершить полную приёмку исправления outdent-сегментации "
"Kimina и возобновить заблокированную ветку с явным происхождением новых меток.",
"4. После полного фиксированного main: оценить число действительно подходящих независимых задач "
"и интервалы прикладного эффекта. При недостаточной точности сформировать следующую фиксированную "
"партию новых prompts и независимой calibration, без последовательного поиска значимости.",
"5. Для механистической части: провести узкий эксперимент фиксированного/оценённого порога P3; "
"честно описать P4 и ограничения P5. Не делать публикацию прикладной оценки зависимой от успеха "
"всех сильных механистических предсказаний.",
"",
"**Границы сделанного.** Полная main-выборка ещё не готова; новых генераций в этом заходе не было. "
"Исправление сегментации не выдано за внедрённое. Широкие пилотные границы не доказывают отсутствия "
"эффекта. Предварительные улучшения порога не доказывают хвостовой механизм. Все новые тесты и "
"семьи явно вторичны, поскольку пилот и прежние Monte Carlo-результаты уже были просмотрены.",
"",
"**Материалы для проверки другим GPT.**",
"",
"- [metrics.json](metrics.json): все числа отчёта и состояние на момент среза.",
"- [FOR_REVIEWING_GPT.md](FOR_REVIEWING_GPT.md): вопросы независимой ревизии.",
"- [Протокол поправки](evidence/protocol.json), [обоснование](source/docs/revisions/statistical_fitness_20260913.md).",
"- [Новый статистический код](source/src/onebigjump/readiness/finite_sample.py), [обработчик Lean](source/src/onebigjump/e1/parallel_verification.py).",
"- [Benchmark](evidence/benchmark/metrics.json), [сравнения](evidence/benchmark/comparisons.json), [исходные replay](evidence/benchmark/replays.json).",
"- [Пилот и синтетический экран](evidence/analysis/metrics.json), [приёмка](evidence/activation-preconditions.json), [активация](evidence/activation.json).",
"- [Предыдущая общая ревизия](evidence/previous-full-review.txt), [исходная P3-сводка](evidence/p3-selection-metrics.json).",
"",
"Все вычисления и тесты выполнены на Жоресе через Slurm. В manifest записаны source snapshot, "
"git commit/dirty, версии окружения и хеши файлов. Репозиторий остаётся dirty, commit не создавался. "
"Архив содержит проверяемые результаты и исходники, но не все веса моделей, активации и исходные "
"данные генерации; внешние входы доступны по серверным путям в manifests.",
]
report=OUT/"REPORT.md";report.write_text("\n".join(lines)+"\n",encoding="utf-8")
review=OUT/"FOR_REVIEWING_GPT.md"
review.write_text("""# Задание для независимой ревизии

Проверь REPORT.md, metrics.json, source и evidence. Не пытайся сделать отрицательный результат положительным.

1. Разделены ли прикладной эффект локализации и сильный вывод о хвостовом механизме?
2. Корректны ли task-weighting, парная eligibility, отсутствие post-failure шагов среди правильных?
3. Не выданы ли независимые попытки/шаги/модели/чекпойнты за независимые задачи?
4. Различены ли Hoeffding-граница среднего и биномиальный знаковый тест условной вероятности выигрыша?
5. Явно ли показаны предпосылки независимости, фиксированного benchmark и преобразования?
6. Сохранена ли исходная основная ячейка и семья; не расширено ли утверждение о поправке на три модели на весь набор вариантов?
7. Правильно ли использованы знаменатели покрытия и доступности P3? Не назван ли недоступный интервал подтверждением гипотезы?
8. Не выданы ли пять пар seed за мощный тест P4; отделён ли экран изменений от предсказания смены знака?
9. Достаточен ли benchmark для ограниченного запуска? Проверь selection, semantic comparison, worker cleanup и журналирование.
10. Не заявлено ли фактическое ускорение всей кампании до завершения боевых фрагментов?
11. Верно ли различены уже внедрённое, поставленное в очередь и ещё не выполненное?
12. Какую минимальную заранее фиксируемую следующую партию данных/валидации ты рекомендуешь после полного main?

Числа отчёта генерируются из метрик. Предыдущая общая ревизия дана как контекст и имеет более ранний срез.
""",encoding="utf-8")
evidence=OUT/"evidence";evidence.mkdir(exist_ok=True)
for directory in ["analysis","benchmark","sidecar-integration"]:
    shutil.copytree(HERE/directory,evidence/directory)
for name in ["protocol.json","activation.json","activation-preconditions.json","main-queue-before.json",
             "main-queue-after.json","captured-main-queue.json","captured-sidecar-queue.json","captured-sacct.tsv",
             "captured-squeue.tsv","captured-sstat.tsv","changed-files.json","tests-8466153.xml",
             "validation-8466152.log","validation-8466153.log","benchmark-8466154.log",
             "analysis-8466155.log","integration-8466156.log","main_sidecar.py","fast-verify.sbatch",
             "analyze.py","benchmark.py","validate.sbatch","freeze.py"]:
    shutil.copy2(HERE/name,evidence/name)
shutil.copy2(p3path,evidence/"p3-selection-metrics.json")
shutil.copy2(BASE/"audit/revision_2026_09_13/reviews/whole-project-final-v2/REPORT.md",evidence/"previous-full-review.txt")
source_root=SOURCE.parent
for name in read_json(SOURCE)["outputs"]:
    p=Path(name);q=OUT/"source"/p.relative_to(source_root)
    q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
shutil.copy2(SOURCE,OUT/"source/source-manifest.json")
inputs=[SOURCE,HERE/"analysis/manifest.json",HERE/"benchmark/manifest.json",HERE/"sidecar-integration/manifest.json",
        p3path,BASE/"audit/revision_2026_09_13/reviews/whole-project-final-v2/manifest.json",
        Path(__file__),HERE/"activation.json",HERE/"activation-preconditions.json",
        HERE/"captured-main-queue.json",HERE/"captured-sidecar-queue.json",
        HERE/"captured-sacct.tsv",HERE/"captured-squeue.tsv",HERE/"captured-sstat.tsv",
        HERE/"tests-8466153.xml",HERE/"validation-8466153.log",HERE/"protocol.json"]
outputs=sorted(p for p in OUT.rglob("*") if p.is_file())
finish(OUT,stage="statistical-fitness-review",context={"source":digest(SOURCE),"amendment":"post-pilot"},
    inputs=inputs,outputs=outputs,
    metrics={"tests":checks["tests"],"benchmark_speedup":b["speedup"],"source_git":read_json(SOURCE)["metrics"],
             "outputs":len(outputs),"primary_unchanged":True,"activated_waiting_shards":len(activation["changed_waiting_tasks"])})
delivery=HERE/"delivery";delivery.mkdir()
archive=delivery/"onebigjump-statistical-fitness-20260913.zip"
with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob("*")):
        if p.is_file():z.write(p,Path("statistical-fitness")/p.relative_to(OUT))
receipt={"archive":str(archive),"sha256":digest(archive),"bytes":archive.stat().st_size,
         "report_manifest_sha256":digest(OUT/"manifest.json")}
write_once(delivery/"metrics.json",receipt)
print("REPORT_COMPLETE",json.dumps(receipt),flush=True)
