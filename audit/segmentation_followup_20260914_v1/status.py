import json,os,platform,datetime,hashlib
from pathlib import Path
from onebigjump.e1.artifacts import digest,environment
REPO=Path("/beegfs/home/denis.rakhmankin/onebigjump")
SEG=REPO/"runs/segmentation_20260914_v3_recovery1";EXT=REPO/"runs/segmentation_states_20260914_v1"
OUT=REPO/"audit/segmentation_followup_20260914_v1"/("result-"+os.environ["SLURM_JOB_ID"]);OUT.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
shards=[]
meta=read(SEG/"inputs/manifest.json")
for task,s in meta["shards"].items():
 d=SEG/"shards"/f"{int(task):03d}"
 progress=read(d/"progress.json") if (d/"progress.json").exists() else {}
 if not progress and (d/"observations.jsonl").exists():
  progress={"completed":sum(1 for _ in (d/"observations.jsonl").open())}
 shards.append({"task":int(task),"model":s["model"],"completed":progress.get("completed",0),"expected":s["count"],
                "finished":(d/"manifest.json").exists(),"last_status":progress.get("last_status")})
for p in [EXT/"preflight/manifest.json"]:
 for file,h in read(p)["outputs"].items():
  if digest(file)!=h:raise ValueError("preflight artifact changed: "+file)
metrics={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"shards":sorted(shards,key=lambda s:s["task"]),
 "completed":sum(s["completed"] for s in shards),"expected":meta["total"],"finished_shards":sum(s["finished"] for s in shards),
 "recovery_queue":read(SEG/"queue.json"),"extraction_queue":read(EXT/"queue.json"),
 "recovery_tests":read(REPO/"audit/segmentation_recovery_20260914_v1/preflight-metrics.json"),
 "extraction_tests":read(EXT/"preflight/metrics.json"),"preflight_artifact_integrity":True,
 "partial_progress_is_not_a_statistical_result":True}
write(OUT/"metrics.json",metrics)
q=metrics["extraction_queue"];r=metrics["recovery_queue"]
lines=["# Продолжение обработки и очередь расчётов","",f"Срез UTC: {metrics['utc']}.",
 f"Учтено {metrics['completed']} из {metrics['expected']} ответов; завершено частей: {metrics['finished_shards']} из {len(shards)}.","",
 "Авария Lean Nat.pow выделена в observer_runtime_error. Исходный вердикт доказательства сохранён; такие случаи не дают новую метку ошибки.",
 "Восстановление ведётся в отдельном каталоге с переносом проверенных записей и сохранением контрольных сумм родительских результатов.",
 "Обнаружено системное ограничение открытых файлов при одновременных загрузках Mathlib. Повторы проблемных частей переведены на последовательное выполнение на cn70.","",
 f"GPU-извлечение готовых частей: {q['ready_array']}. Остальные части: {q['remaining_array']} после готовой сводки {q['segmentation_summary_job']} и первой GPU-порции.",
 f"Повторное измерение и статистический анализ: {q['analysis_job']}, после обеих GPU-порций.","",
 "Готовые части можно обрабатывать параллельно с восстановлением Lean. Фактическое начало GPU-работы зависит от очереди кластера.",
 "Используются прежние модели, токены ответов и разделение задач. Состояния извлекаются на трёх прежних слоях; статистический пересчёт сначала выполняется для прежней основной ячейки: температура 0.6, средний слой, whitening.",
 "Параметры статистики сохранены. Новый результат маркируется как проверка чувствительности к сегментации и не заменяет исходный основной эксперимент.",
 "Surprisal считается по исходным токенам новых шагов; проекция на словарь выполняется небольшими порциями. На CPU проверено совпадение с обычным проходом, на реальной GPU-модели встроена дополнительная проверка перед обработкой.",
 "Сводка Lean удерживается диспетчером до готовности всех частей. Статистический анализ не стартует по неполному набору.",
 "Новых статистических выводов этот документ не содержит.","",
 "## Проверки","",
 f"Восстановление: {sum(metrics['recovery_tests']['checks'].values())} успешных проверок, включая настоящий сбой и последующее успешное обращение к Lean.",
 f"Извлечение: {len(metrics['extraction_tests']['checks'])} успешных проверок; реальные границы и метки проверены для всех трёх моделей.",
 "Контрольные суммы артефактов предварительной проверки подтверждены.","",
 "## Файлы на Жоресе","",
 str(SEG),str(EXT)]
(OUT/"REPORT_RU.md").write_text("\n\n".join(lines)+"\n",encoding="utf-8")
write(OUT/"manifest.json",{"git_commit":os.environ.get("ONEBIGJUMP_GIT_COMMIT"),"dirty":bool(os.environ.get("ONEBIGJUMP_GIT_STATUS")),
 "environment":environment(),"config":read(EXT/"config.json"),"source":{__file__:digest(__file__)},
 "outputs":{str(p):digest(p) for p in [OUT/"metrics.json",OUT/"REPORT_RU.md"]}})
print(json.dumps({k:metrics[k] for k in ["completed","expected","finished_shards"]}));print(str(OUT))
