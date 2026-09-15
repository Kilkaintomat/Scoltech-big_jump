"""Render a dated processing/ETA receipt from live journal prefixes and completed manifests."""
from pathlib import Path
import collections,datetime,json,math,os,shutil,statistics,zipfile,xml.etree.ElementTree as ET
from onebigjump.e1.artifacts import digest,finish,identity,read_json,write_once,verify_manifest
from onebigjump.e1.stages import configuration
from onebigjump.e1.generation import planned_requests
BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/speedup-v2"
ROOT=BASE/"runs/lean_reverification_20260913_local"
SOURCE=BASE/"audit/revision_2026_09_13/snapshots/lean-saved-repair-v8/source-manifest.json"
EXECUTION=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
OUT=HERE/("report-"+os.environ["SLURM_JOB_ID"])
OUT.mkdir()
capture=read_json(HERE/"timing-capture-final.json");queue=capture["queue"]
sacct={}
for line in capture["sacct"].splitlines():
 v=line.split("|")
 if len(v)>=8:sacct[v[0]]={"state":v[2],"elapsed_seconds":int(v[3]),"start_utc":v[4],"end_utc":v[5],"cpus":v[6],"node":v[7]}
inputs=[SOURCE,Path(__file__),HERE/"timing-capture-final.json",HERE/"PROPOSAL.json",HERE/"tests-8466207.xml"]
accept=HERE/"acceptance/manifest.json";verify_manifest(accept);inputs.append(accept)
am=read_json(accept)["metrics"]
io=read_json(HERE/"io-benchmark/metrics.json")
io_xml=HERE/"io-tests-8466227.xml"
io_suites=list(ET.parse(io_xml).getroot().iter("testsuite"))
assert all(int(x.get(k,"0"))==0 for x in io_suites for k in ("failures","errors","skipped"))
io_test_count=sum(int(x.get("tests","0")) for x in io_suites)
inputs.extend([EXECUTION,HERE/"io-benchmark/manifest.json",io_xml])
details=[];summary=[];medians={}
for model in ("deepseek","goedel","kimina"):
 root=ROOT/model
 expected=len(list(planned_requests(root,"main",configuration(root,"main"))))
 done=0;accepted=0;fresh=0;seconds_per_worker=[]
 for i in range(8):
  name="shard-%03d-of-008"%i;task=queue["tasks"][model+"/main-verify-"+str(i)]
  label=root/"main/verification"/name/"labels.jsonl";n=0
  if label.exists():
   raw=label.read_bytes();prefix=raw[:raw.rfind(b"\n")+1]
   for line in prefix.splitlines():
    row=json.loads(line);sha=row.pop("row_sha256");assert identity(row)==sha;n+=1
   evidence={"path":str(label),"captured_bytes":len(prefix),"sha256":__import__("hashlib").sha256(prefix).hexdigest()}
  else:evidence=None
  done+=n
  job=task.get("job_id");timing=sacct.get(job,{})
  capacity=BASE/("audit/revision_2026_09_13/statistical-fitness-v1/resource-guard-runs/"+str(job)+"/capacity.json")
  workers=read_json(capacity)["selected_workers"] if capacity.exists() else 1
  if (label.parent/"manifest.json").exists() and n and timing.get("state") in {"COMPLETED","FAILED"}:
   seconds_per_worker.append(timing["elapsed_seconds"]*workers/n)
  repaired=HERE/"repaired"/model/name/"manifest.json"
  correction=None
  if repaired.exists():
   verify_manifest(repaired);inputs.append(repaired);correction=read_json(repaired)["metrics"]
   if correction["unexplained_disagreements"]==0:accepted+=correction["attempts"]
   fresh+=correction["fresh_selected"]
  details.append({"model":model,"shard":i,"raw_rows":n,"queue_state":task["state"],"job_id":job,
                  "workers":workers,"timing":timing,"journal_prefix":evidence,"repair":correction})
 medians[model]=statistics.median(seconds_per_worker)
 summary.append({"model":model,"saved_attempts":expected,"raw_labeled":done,"remaining_raw":expected-done,
                 "accepted_repaired":accepted,"fresh_rechecks":fresh,
                 "median_worker_seconds_per_attempt":medians[model]})
work=sum(s["remaining_raw"]*s["median_worker_seconds_per_attempt"] for s in summary)
lean_range=[work/8/3600,work/6/3600*1.5]
gpu=[]
for model in ("deepseek","goedel","kimina"):
 p=ROOT/model/"pilot/extraction/manifest.json";m=read_json(p);inputs.append(p)
 job=m["environment"]["slurm_job_id"];elapsed=sacct[job]["elapsed_seconds"]
 total=next(s["saved_attempts"] for s in summary if s["model"]==model)
 gpu.append({"model":model,"pilot_attempts":m["metrics"]["attempts"],"pilot_seconds":elapsed,
             "linear_main_gpu_seconds":elapsed*total/m["metrics"]["attempts"]})
gpu_hours=sum(g["linear_main_gpu_seconds"] for g in gpu)/2/3600
metrics={"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"scheduler_capture_utc":capture["utc"],
 "source_manifest_sha256":digest(SOURCE),"acceptance":am,"summary":summary,"shards":details,
 "eta":{"kind":"engineering scenarios, not confidence intervals or guarantees",
        "lean_hours":lean_range,"assumptions":"historical median seconds per independent Lean worker, 6-8 workers, upper multiplier 1.5; excludes unresolved new failures and queue waits",
        "gpu_two_devices_linear_hours":gpu_hours,"gpu_scenario_hours":[gpu_hours,gpu_hours*2],
        "gpu_assumptions":"linear extrapolation from 80-attempt pilots includes loading overhead; main length mix may differ; no queue wait",
        "practical_results_sequential_scenario_hours":[lean_range[0]+gpu_hours,lean_range[1]+gpu_hours*2],
        "full_tail_analysis_eta":None,"full_tail_reason":"pilot gates skip most expensive estimators; main double-bootstrap runtime not measured"},
 "gpu_pilot":gpu,"automation_proposal":read_json(HERE/"PROPOSAL.json"),
 "io_benchmark":io,"io_full_test_count":io_test_count,"execution_source_sha256":digest(EXECUTION),
 "primary_statistical_specification_unchanged":True,"generation_restarted":False}
mp=write_once(OUT/"metrics.json",metrics)
total=sum(s["saved_attempts"] for s in summary);raw=sum(s["raw_labeled"] for s in summary);accepted=sum(s["accepted_repaired"] for s in summary)
lines=["# Обработка сохранённых ответов и ускорение Lean","",
"Срез UTC: "+capture["utc"]+". Цифры сформированы программой report.py из журналов и Slurm.",
"",f"Сохранено {total} ответов. В текущих журналах Lean {raw} меток ({100*raw/total:.1f}%). После отдельного контроля ремонта принято {accepted} меток. Эти два счётчика различаются: окончание воспроизведения ещё не означает прохождение контроля качества.",
"","| Модель | Ответов | Записано меток | Принято после ремонта | Осталось первичного воспроизведения |",
"|---|---:|---:|---:|---:|"]
for s in summary:lines.append(f"| {s['model']} | {s['saved_attempts']} | {s['raw_labeled']} | {s['accepted_repaired']} | {s['remaining_raw']} |")
lines+=["","## Проверенные изменения",
f"- Полный набор: {am['full_test_count']} тестов, без ошибок и пропусков. Ruff и mypy прошли.",
f"- Повторно воспроизведены {am['original_disagreements']} известных расхождений: {am['fresh_verified']} доказательств прошли целую и пошаговую проверку.",
"- Исправлены удаление символов при снятии отступа, отрыв all_goals от его тактики и обращение к нижнему регистру вместо настоящего имени теоремы.",
"- Для нового исполнителя добавлена общая очередь: освободившийся процесс берёт следующую работу. Независимость процессов Lean, лимиты времени и heartbeat сохранены.",
"- Повторная проверка выбирает все ответы с изменившимся разбором или именем, включая ранее ошибочные; остальные метки переносятся только с проверкой исходного запроса, разборов и происхождения.",
"- Исходные журналы сохранены. Принятые исправления записаны отдельно и имеют собственные manifests.",
"- Устранено размещение будущих основных Lean-заданий на одном узле: запрос 64 CPU занимает CPU-узел, число Lean-процессов остаётся 1–2 с проверкой лимита файлов. Это повышает резервирование ресурсов, а не вычислительную параллельность. Флаг exclusive кластер отклонил.",
"- Отменено только задание 8466198, которое ожидало блокировку и ещё не запустило Lean/журнал. Повторная отправка имеет отдельное имя; история отказов сохранена.",
"","Совместимость пилотных меток:"]
for p in am["pilot_compatibility"]:lines.append(f"- {p['model']}: {p['attempts']} ответов, изменённых входов проверки — {p['changed']}.")
lines+=["","## Ускорение проверки файлов",
f"Дополнительный полный прогон: {io_test_count} тестов без ошибок и пропусков. Каждый общий манифест проверяется один раз в пределах вызова; постоянного кеша, отключения хешей или пропуска уникальных файлов нет.",
f"На одном и том же реальном графе файлов: объём повторного чтения уменьшился в {io['read_reduction']:.2f} раза, время контрольного обхода — в {io['speedup']:.2f} раза.",
"Это замер проверки происхождения, а не ускорение всех экспериментов во столько же раз. Базовый вариант запускался первым; прогрев файлового кеша мог повлиять на время.",
"Оптимизация проверена отдельно; работающие задания используют уже загруженные версии исходников.",
"","## Сколько ждать",
f"- Остаток первичного Lean: сценарий {lean_range[0]:.1f}–{lean_range[1]:.1f} ч при указанной загрузке, без новых блокирующих ошибок.",
f"- GPU по сохранённым текстам: линейный ориентир {gpu_hours:.1f} ч при двух устройствах; инженерный диапазон {gpu_hours:.1f}–{gpu_hours*2:.1f} ч.",
f"- Последовательная сумма до первых практических сравнений: {lean_range[0]+gpu_hours:.1f}–{lean_range[1]+gpu_hours*2:.1f} ч. Разные модели могут перекрываться по этапам. Очередь и ремонт новых ошибок добавят время.",
"- Это оценка до данных и быстрого практического анализа. Для полного набора хвостовых bootstrap-проверок срок пока не измерен; пилот непригоден для такого прогноза, поскольку многие расчёты были недоступны.",
"","## Что осталось",
"1. Завершить Lean на всех сохранённых ответах и принять все исправленные порции.",
"2. Собрать метки только после совпадения всех ожидаемых trace_id и отсутствия необъяснённых расхождений.",
"3. Запустить извлечение активаций из сохранённых токенов, затем измерения и уже подготовленный быстрый task-level анализ; далее исходные статистические проверки и контроли.",
"4. Измерить скорость первого полноценного хвостового расчёта и обновить срок, прежде чем обещать завершение всей статистики.",
"","## Состояние разрешений",
"Новый диспетчер не установлен и не запущен. Автоматическая проверка разрешений отклонила постоянный процесс, который мог менять зависимости очереди, связывать задачи сбора с успешными заданиями ремонта и отправлять дальнейшие работы. Действующая основная очередь и разрешённый отдельный прогон ремонта продолжаются.",
"Детальный ограниченный проект действий: PROPOSAL.json. Без согласованного включения дальнейшей обработки либо ручного проверенного переключения ожидание само по себе не снимет уже существующие блокировки анализа.",
"","## Источники и воспроизводимость",
"- metrics.json содержит расчёт времени, количества и происхождение срезов журналов.",
"- evidence/ содержит результаты приёмки, решений ремонта и снимок Slurm; source/ — проверенный исходный код.",
"- Linux лимиты файлов: https://docs.kernel.org/admin-guide/sysctl/fs.html",
"- Slurm размещение CPU: https://slurm.schedmd.com/sbatch.html",
"- Lean тактические комбинаторы: https://lean-lang.org/doc/reference/latest/Tactic-Proofs/Tactic-Reference/",
"","Дополнительные статистические сравнения здесь не пересчитывались. Исправление верификатора не является подтверждением научной гипотезы."]
(OUT/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
shutil.copyfile(HERE/"PROPOSAL.json",OUT/"PROPOSAL.json")
evidence=OUT/"evidence";evidence.mkdir()
for p in [HERE/"timing-capture-final.json",HERE/"acceptance/metrics.json",HERE/"acceptance/replays.json",HERE/"tests-8466207.xml",io_xml,HERE/"io-benchmark/metrics.json"]:
 name=p.parent.name+"-"+p.name if p.name=="metrics.json" else p.name
 shutil.copyfile(p,evidence/name)
for model in ("deepseek","goedel","kimina"):
 for p in (HERE/"repaired"/model).glob("shard-*/*.json"):
  if p.name not in {"metrics.json","decisions.json","manifest.json"}:continue
  target=evidence/"repair"/model/p.parent.name/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
for p in [HERE/"repair.py",HERE/"report.py",HERE/"verify-node.sbatch",HERE/"repair.sbatch",HERE/"io_benchmark.py",HERE/"io-benchmark/manifest.json"]:
 shutil.copyfile(p,evidence/p.name)
source_out=OUT/"source"
for folder in ("src","tests"):
 shutil.copytree(EXECUTION.parent/folder,source_out/folder,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
shutil.copyfile(EXECUTION,source_out/"source-manifest.json")
outputs=[p for p in OUT.rglob("*") if p.is_file()]
finish(OUT,stage="saved-processing-status-and-eta",context={"source":digest(SOURCE)},inputs=list(dict.fromkeys(inputs)),outputs=outputs,metrics=metrics)
integrity={str(p.relative_to(OUT)):digest(p) for p in OUT.rglob("*") if p.is_file()}
write_once(OUT/"integrity.json",integrity)
delivery=HERE/("delivery-"+os.environ["SLURM_JOB_ID"]);delivery.mkdir()
archive=delivery/"saved-processing-report.zip"
with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
 for p in OUT.rglob("*"):
  if p.is_file():z.write(p,Path("saved-processing")/p.relative_to(OUT))
write_once(delivery/"receipt.json",{"archive":str(archive),"sha256":digest(archive),"bytes":archive.stat().st_size,"report":str(OUT),"metrics":str(mp)})
print(json.dumps({"report":str(OUT),"delivery":str(delivery),"metrics":metrics["summary"],"eta":metrics["eta"]}),flush=True)
