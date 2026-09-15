from pathlib import Path
from datetime import datetime,timezone
import os,json,shutil,zipfile,hashlib,xml.etree.ElementTree as ET
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,verify_manifest

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/statistical-fitness-v1"
ORIGINAL=HERE/"report"
OUT=HERE/"report-v2"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
shutil.copytree(ORIGINAL,OUT)
(OUT/"manifest.json").unlink()
b=read_json(HERE/"benchmark-guarded/metrics.json")
assert b["passed"] and b["semantic_equal"]==b["sampled_traces"]
g=read_json(HERE/"guarded-activation.json")
rollback=read_json(HERE/"rollout-rollback.json")
guard_run=HERE/"resource-guard-runs/8466175/manifest.json"
verify_manifest(guard_run)
tree=ET.parse(HERE/"guard-tests-8466175.xml")
counts={key:sum(int(s.attrib.get(key,0)) for s in tree.getroot().iter("testsuite")) for key in ["tests","errors","failures","skipped"]}
assert counts["tests"] and not any(counts[k] for k in ["errors","failures","skipped"])
q=read_json(HERE/"captured-main-queue-v2.json")
side=read_json(HERE/"captured-sidecar-queue-v2.json")
production=read_json(HERE/"production-observation.json")
from onebigjump.e1.stages import rows
prefix=rows(HERE/"production-prefix.jsonl")
production["observed_rows"]=len(prefix)
production["observed_lanes"]=sorted({r.get("execution",{}).get("lane") for r in prefix})
assert prefix and all(r.get("execution",{}).get("workers")==production["capacity"]["selected_workers"] for r in prefix)
assert production["running"] and production["capacity"]["selected_workers"] in [1,2]
m=read_json(ORIGINAL/"metrics.json")
old_counts=m["main_queue_counts"]
old_side=m["sidecar_queue_counts"]
m.update(created_utc=datetime.now(timezone.utc).isoformat(),benchmark_initial=m["benchmark"],benchmark=b,
         activation=g,initial_rollout_rollback=rollback,guard_tests=counts,production_observation=production,
         main_queue_counts=q["counts"],main_queue_capture=q["last_poll_utc"],sidecar_queue_counts=side["counts"],
         operational_policy="adaptive one or two workers; live descriptor budget; one guarded job per node")
# Read-only diagnostic scans of append-only prefixes, not a revalidation of live science data.
scan=[]
main_root=BASE/"runs/lean_reverification_20260913_local"
for model,shard,job in [("deepseek",2,"8466112"),("goedel",2,"8466115"),("kimina",2,"8466118"),("deepseek",3,"8466124")]:
    paths=[main_root/model/("main/verification/shard-%03d-of-008/labels.jsonl"%shard),
           main_root/"logs"/("obj0913local-%s-main-verify-%d-%s.log"%(model,shard,job))]
    for path in paths:
        if not path.exists():continue
        data=path.read_bytes()
        scan.append({"path":str(path),"prefix_bytes":len(data),"prefix_sha256":hashlib.sha256(data).hexdigest(),
                     "too_many_open_files_occurrences":data.count(b"Too many open files"),
                     "file_descriptor_occurrences":data.count(b"file descriptor")})
m["existing_jobs_diagnostic_scan"]={"records":scan,"scope":"read-only prefixes at report time; absence of this diagnostic does not prove every possible impact absent"}
(OUT/"metrics.json").write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
text=(ORIGINAL/"REPORT.md").read_text(encoding="utf-8")
text=text.replace(read_json(ORIGINAL/"metrics.json")["created_utc"],m["created_utc"])
text=text.replace(read_json(ORIGINAL/"metrics.json")["main_queue_capture"],m["main_queue_capture"])
text=text.replace(f"Основная очередь: {json.dumps(old_counts,ensure_ascii=False)}. Дополнительная очередь: {json.dumps(old_side,ensure_ascii=False)}.",
                  f"Основная очередь: {json.dumps(q['counts'],ensure_ascii=False)}. Дополнительная очередь: {json.dumps(side['counts'],ensure_ascii=False)}.")
text=text.replace("- Ускорение включено для 14 ещё не отправленных фрагментов.",
                  f"- Адаптивный режим с защитой файловых ресурсов включён для {len(g['changed_waiting_tasks'])} ожидавших фрагментов.")
start=text.index("**Ускорение: что измерено и что включено.**")
end=text.index("**Проверка новых вычислений.**",start)
section=[
"**Ускорение: измерение, обнаруженное ограничение и исправленная эксплуатационная схема.**","",
f"Первоначальный четырёхпроцессный бенчмарк дал {m['benchmark_initial']['speedup']:.2f}× и полное совпадение "
f"{m['benchmark_initial']['semantic_equal']} трасс. Однако первый боевой запуск {rollback['failed_job']} "
"упёрся в общий файловый лимит узла при импорте Mathlib. На момент отказа было записано "
f"{rollback['labels_written']} меток. Неудачный запуск сохранён, ожидание возвращено в исходный режим, "
"а вызванная этим запуском блокировка Goedel снята. Поэтому результат короткого бенчмарка не выдан "
"за доказательство эксплуатационной надёжности.","",
"В окончательной схеме перед запуском читаются node-wide file-nr/file-max и лимит процесса. "
"Число работников выбирается между одним и двумя с резервом файловых дескрипторов; при недостатке "
"места запуск ждёт. Для наших защищённых заданий используется один общий lock на узел на всё "
"время задания. Это предотвращает гонку одновременных стартов нашего проекта. Внешняя нагрузка "
"других пользователей всё ещё может измениться; защита не является резервированием ресурсов ядром. "
"[Документация Linux](https://docs.kernel.org/admin-guide/sysctl/fs.html#file-max-file-nr).","",
f"Настройки защиты: не более {g['maximum_workers']} работников, бюджет {g['budget_per_worker']} "
f"файловых объектов на работника, резерв {g['reserve_file_handles']}. Это консервативные эксплуатационные "
"параметры, зафиксированные до повторного теста; научные пороги и бюджеты доказательства не менялись.","",
f"Повторный бенчмарк на том же наборе сохранённых трасс прошёл: {b['semantic_equal']} / "
f"{b['sampled_traces']} совпадений с последовательной разметкой и {b['archived_equal']} / "
f"{b['sampled_traces']} с архивом, без новых ресурсных отказов в этих сравнениях. "
"Он служит инженерной проверкой, не новой независимой статистической выборкой.","",
"| Модель | Последовательно, с | Два процесса, с | Ускорение |",
"|---|---:|---:|---:|",
]
for model in ["deepseek","goedel","kimina"]:
    s=next(r for r in b["measurements"] if r["model"]==model and r["workers"]==1)
    p=next(r for r in b["measurements"] if r["model"]==model and r["workers"]==2)
    section.append(f"| {model} | {s['seconds']:.2f} | {p['seconds']:.2f} | {s['seconds']/p['seconds']:.2f}× |")
section += [
f"| Сумма | {b['serial_seconds']:.2f} | {b['parallel_seconds']:.2f} | {b['speedup']:.2f}× |","",
"Это один раунд на небольшой фиксированной инженерной выборке. Время включает старт REPL, но "
"исключает размещение toolchain, проверку входных файлов и ожидание ресурсов. Поэтому общий "
"выигрыш всей кампании пока неизвестен. При выборе одного работника или ожидании lock ускорения "
"данного задания может не быть. Нельзя обещать четырёхкратное ускорение.","",
f"Боевой запуск {production['job_id']} ({production['task']}) уже RUNNING на "
f"{production['capacity']['node']}; выбрано {production['capacity']['selected_workers']} работника. "
f"В сохранённом срезе журнала есть {production['observed_rows']} завершённых записей. "
"Это наблюдение прогресса, а не завершение фрагмента или независимая оценка его полной скорости.","",
"Каждый работник владеет отдельным процессом Lean. Главный поток единолично пишет результаты "
"по мере готовности. Проверены дубликаты, исключения и закрытие процессов. Сохранены токены, "
"список задач, heartbeat и wall-clock бюджеты. Сравнение семантики включает категорию, whole/replay, "
"t*, axioms, spans и поля шагов; не включает время, номера окружений и текст диагностических "
"сообщений. Исходное ядро verifier побайтно совместимо с прежним pilot gate.","",
"Задания получают 32 CPU и 96 GiB; фактический выбранный параллелизм и состояние лимитов "
"записываются в отдельную квитанцию. Работающие старые задания не отменялись. В прочитанных "
"префиксах журналов основных заданий не найдено сообщения о таком файловом отказе; это "
"проверка конкретной диагностики, не доказательство отсутствия любого возможного воздействия.","",
f"Полный набор остаётся пройденным: {m['checks']['tests']['tests']} тестов без ошибок и пропусков. "
f"Дополнительно прошли {counts['tests']} проверок ресурсного выбора, тоже без ошибок и пропусков.","",
"Прикладная статистическая сводка теперь считается отдельной CPU-стадией, не ожидая nested "
"bootstrap хвостов. Она использует существующие измерения. Новый main-runner интеграционно "
"воспроизвёл пилотные результаты, а для трёх моделей уже создана автоматическая очередь.","",
]
text=text[:start]+"\n".join(section)+"\n"+text[end:]
text=text.replace("- [Benchmark](evidence/benchmark/metrics.json)", "- [Benchmark с ресурсной защитой](evidence/benchmark/metrics.json)")
text=text.replace("- [Пилот и синтетический экран](evidence/analysis/metrics.json), [приёмка](evidence/activation-preconditions.json), [активация](evidence/activation.json).",
"- [Пилот и синтетический экран](evidence/analysis/metrics.json), [приёмка](evidence/activation-preconditions.json), [окончательная активация](evidence/guarded-activation.json).\n"
"- [Ресурсная защита](evidence/resource_guard.py), [её тесты](evidence/guard-tests-8466175.xml), [первый боевой срез](evidence/production-observation.json).\n"
"- [Первый неудачный rollout](evidence/rollout-rollback.json), [первоначальный четырёхпроцессный бенчмарк](evidence/benchmark-four-worker-screen/metrics.json).")
(OUT/"REPORT.md").write_text(text,encoding="utf-8")
e=OUT/"evidence"
(e/"benchmark").rename(e/"benchmark-four-worker-screen")
shutil.copytree(HERE/"benchmark-guarded",e/"benchmark")
for filename in ["guarded-activation.json","guarded-protocol.json","rollout-rollback.json","production-canary.json",
                 "resource_guard.py","test_resource_guard.py","fast-verify-guarded.sbatch",
                 "guard-tests-8466175.xml","guarded-benchmark-8466175.log","benchmark_guarded.py",
                 "production-observation.json","production-log.txt","captured-main-queue-v2.json",
                 "captured-sidecar-queue-v2.json","captured-sacct-v2.tsv","captured-squeue-v2.tsv",
                 "guarded-queue-before.json","guarded-queue-after.json","rollback-queue-before.json",
                 "rollback-queue-after.json"]:
    shutil.copy2(HERE/filename,e/filename)
shutil.copy2(BASE/"runs/lean_reverification_20260913_local/logs/obj0913local-goedel-main-verify-3-8466170.log",
             e/"failed-production-8466170.log")
shutil.copytree(HERE/"resource-guard-runs/8466175",e/"guarded-benchmark-capacity")
(e/"production-observation.json").write_text(json.dumps(production,indent=2)+"\n",encoding="utf-8")
# Preserve the exact finite prefix observed from the running production journal.
for filename in ["production-prefix.jsonl","production-prefix.identity.json"]:
    shutil.copy2(HERE/filename,e/filename)
review=OUT/"FOR_REVIEWING_GPT.md"
review.write_text(review.read_text(encoding="utf-8")+"\n"
"13. Проверь отказ первого боевого запуска по node-wide file-max, нулевое число записанных меток, "
"откат и условие допуска новой защиты. Не называй двухпроцессный короткий benchmark скоростью всей кампании.\n"
"14. Оцени консервативность file-budget и lock на всё задание: он может уменьшать параллелизм на узле. "
"Сохраняются ли резерв ресурсов, происхождение конфигурации и различие между рабочим срезом и завершённым результатом?\n",
encoding="utf-8")
inputs=[ORIGINAL/"manifest.json",SOURCE,HERE/"benchmark-guarded/manifest.json",guard_run,
        HERE/"guard-tests-8466175.xml",HERE/"guarded-activation.json",HERE/"guarded-protocol.json",
        HERE/"rollout-rollback.json",HERE/"production-observation.json",HERE/"production-log.txt",
        HERE/"production-prefix.jsonl",HERE/"production-prefix.identity.json",
        HERE/"captured-main-queue-v2.json",HERE/"captured-sidecar-queue-v2.json",
        HERE/"captured-sacct-v2.tsv",HERE/"captured-squeue-v2.tsv",Path(__file__)]
outputs=sorted(p for p in OUT.rglob("*") if p.is_file())
finish(OUT,stage="statistical-fitness-review-with-operational-correction",
       context={"source":digest(SOURCE),"primary_unchanged":True},inputs=inputs,outputs=outputs,
       metrics={"tests":m["checks"]["tests"],"guard_tests":counts,"benchmark_speedup":b["speedup"],
                "production_job":production["job_id"],"production_complete":False,
                "primary_unchanged":True,"outputs":len(outputs)})
delivery=HERE/"delivery-v2";delivery.mkdir()
archive=delivery/"onebigjump-statistical-fitness-20260913.zip"
with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob("*")):
        if p.is_file():z.write(p,Path("statistical-fitness")/p.relative_to(OUT))
receipt={"archive":str(archive),"sha256":digest(archive),"bytes":archive.stat().st_size,
         "report_manifest_sha256":digest(OUT/"manifest.json")}
write_once(delivery/"metrics.json",receipt)
print("FINAL_REPORT_COMPLETE",json.dumps(receipt),flush=True)
