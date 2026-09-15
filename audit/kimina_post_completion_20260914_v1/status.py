import csv,io,json,shutil
from pathlib import Path
from data import check_manifest
from support import *
check_manifest(OUT/"preflight/manifest.json");check_manifest(OUT/"analysis-tests/manifest.json")
p=read(OUT/"preflight/metrics.json");t=read(OUT/"analysis-tests/metrics.json");q=read(OUT/"queue.json")
masks=read(OUT/"preflight/masks.json");hist=read(HERE/"scheduler-history.json")
accounting={r["JobID"]:r for r in csv.DictReader(io.StringIO(hist["accounting"]),delimiter="|")}
analysis_history=[{"model":j["model"],"seconds":int(accounting[j["job_id"]]["ElapsedRaw"])} for j in hist["jobs"]
 if j["kind"]=="analysis" and accounting.get(j["job_id"],{}).get("State")=="COMPLETED"]
out=OUT/"status";out.mkdir(exist_ok=False)
def table(h,rows):
 return "\n".join(["| "+" | ".join(h)+" |","|"+"|".join(["---"]*len(h))+"|",*["| "+" | ".join(map(str,r))+" |" for r in rows]])
parts=["# Kimina: очистка хвостов и ожидание результатов",
       "Снимок очереди: "+q["created_utc"]+". Основные GPU-задания сохранены. Пересчёт использует только CPU и уже запланированные активации.",
       "**Сколько ждать**",
       "Планировщик не показывает время старта основных GPU-заданий: Pending / Priority, StartTime N/A. Ожидание ресурсов нельзя перевести в надёжный срок «к утру».",
       table(["Модель","Проверено прежних порций","Прежнее суммарное GPU-время, мин","Ориентир нового GPU-прохода, мин"],[
          [model,v["historical_completed_shards"],f"{v['historical_gpu_seconds']/60:.1f}",f"{v['linear_projection_gpu_seconds']/60:.1f}"] for model,v in p["historical_runtime"].items()]),
       "Ориентир — линейный перенос прежнего времени на число новых запросов. Это оценка порядка вычислительного времени, без очереди, повторного ожидания между волнами и CPU-анализа. Число наблюдений и реализация извлечения изменились; отдельный профиль уточнит скорость. При одновременном старте моделей эти времена не складываются.",
       table(["Прежний CPU-анализ","Фактические минуты"],[[x["model"],f"{x['seconds']/60:.1f}"] for x in analysis_history]),
       "Прежний CPU-анализ даёт дополнительный ориентир, но не прогноз нового: более подробные трассы меняют нагрузку. Лимиты Slurm на длительность заданий не равны ожидаемому времени работы.",
       "**Что исправляется у Kimina**",
       f"Просмотрены все {p['attempts']} ответа Kimina. Для дополнительного анализа пригодны {p['accepted_for_analysis']} трасс. Выделены {p['trimmed_traces']} принятых доказательств с терминальным хвостом post_completion: удалению подлежат {p['removed_steps']} наблюдений.",
       "Удаляется только суффикс после доказанного закрытия корневой цели при отсутствии активных целей. Шаг, закрывающий доказательство, остаётся. Завершение вложенной леммы или одной ветви не считается завершением всего доказательства.",
       f"Неоднозначных случаев: {p['blockers']}. Изменённых ошибочных трасс: {p['refuted_traces_changed']}. Сохраняются исходные тексты, токены, общий вердикт, разбиение задач, позиции ошибок и поглощающие метки.",
       table(["Роль и температура","Трасс с хвостом","Удаляемых шагов","Верных шагов до → после","Независимых верных задач"],[
         [key,v["trimmed_traces"],v["removed_steps"],f"{v['verified_steps_before']} → {v['verified_steps_after']}",v["verified_tasks"]] for key,v in p["by_role_temperature"].items()]),
       "Отличие от предыдущего числа всех post_completion: в ошибочной трассе встречается ещё одно такое диагностическое наблюдение, но оно уже поглощено меткой post. Это наблюдение сохраняется; правило очистки применяется только к принятым доказательствам.",
       "Whitening и преобразование innovation будут переоценены отдельно по температурам на очищенных принятых калибровочных трассах. Пороги P3 пересчитаются из новых калибровочных значений с исходными q. Будут повторены P1/P2/P3 и позиционные контроли с прежними настройками статистики.",
       "Проверка остаётся дополнительной чувствительностью. Исходные результаты сохраняются. Обозначение before в будущем comparison.json относится к новой подробной сегментации с хвостами; after — к той же сегментации после очистки и повторной калибровки.",
       "**Что уже сделано и что поставлено в очередь**",
       f"Маски очистки зафиксированы до новых GPU-результатов. Прошли {p['tests_run']+t['tests_run']} тестов: границы суффикса, корневая цель, защита ошибочных трасс, сохранение исходных приращений и surprisal, разделение задач и формирование статистических таблиц.",
       table(["Задание","Номер","Условие запуска"],[
          ["Пересчёт Kimina и статистика",q["jobs"]["recompute"]["job_id"],"После GPU-извлечения Kimina 8467087_2"],
          ["Сравнение с неочищенным анализом",q["jobs"]["comparison"]["job_id"],"После пересчёта и основного анализа 8467088"]]),
       "Пересчёт не ждёт GPU-результатов других моделей. Сравнительный отчёт дождётся завершения исходной статистики. Дополнительная генерация и дополнительный GPU-проход для очистки не нужны.",
       "В конце будет выполнено точное сравнение raw-значений, surprisal и меток всех сохранённых наблюдений. Изменения P2 у ошибочных трасс могут возникнуть из-за переоценки whitening, поскольку сами ошибочные трассы не обрезаются.",
       "**Ограничения вывода**",
       "Сейчас подтверждена корректность правила очистки на сохранённых свидетельствах Lean; новые хвостовые индексы и показатели локализации ещё не получены. Просмотр сохранённых свидетельств не заменяет новый полный запуск Lean. Преобразование остаётся фиксированным внутри bootstrap, а повторное использование калибровки для преобразования и порога остаётся ограничением P3.",
       "Ошибки тактик, неизвестные имена и native_decide со свободными переменными требуют отдельных проверок совместимости и самих доказательств. Обрезание post_completion их не исправляет. Повышение лимита генерации не решает проблему повторов после уже закрытой цели.",
       "Полные маски очистки, метрики, исходники, настройки и результаты тестов сохранены в provenance. Научные результаты следующего этапа появятся в measurement, analysis и comparison серверного каталога runs/kimina_post_completion_20260914_v1."
]
report=out/"REPORT_RU.md";report.write_text("\n\n".join(parts)+"\n",encoding="utf-8")
sources=[OUT/"preflight/metrics.json",OUT/"preflight/manifest.json",OUT/"preflight/masks.json",OUT/"preflight/tests.log",OUT/"preflight/blockers.json",
         OUT/"analysis-tests/metrics.json",OUT/"analysis-tests/manifest.json",OUT/"analysis-tests/tests.log",OUT/"queue.json",*list(HERE.glob("*"))]
outputs=[report]
for src in sources:
 if src.is_file():
  dest=out/"provenance"/src.relative_to(REPO);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);outputs.append(dest)
summary={"cleanup_preflight":p,"tests_total":p["tests_run"]+t["tests_run"],"historical_cpu_analysis":analysis_history,
         "queue":q,"new_scientific_results_available":False}
finish(out,summary,sources,outputs)
print("STATUS REPORT READY",str(out),flush=True)
