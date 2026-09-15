"""Generate a reviewable status report from immutable experiment artifacts, on Slurm."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import json, os, shutil, hashlib
from onebigjump.e1.artifacts import read_json, verify_manifest, write_once, finish, digest
from onebigjump.e1.stages import generation_inputs, rows

base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
audit = base / "audit/revision_2026_09_13"
out = Path(os.environ["REVIEW_OUTPUT"])
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
started = read_json(out / "inputs/capture.json")["captured_utc"]
inputs = [source, Path(__file__), out / "inputs/capture.json", out / "inputs/squeue.txt", out / "inputs/sacct.txt"]
artifacts = []
def attach(path, recursive=True):
    path = Path(path)
    if not path.exists(): return None
    if recursive and path.name.endswith("manifest.json"): verify_manifest(path)
    relative = path.relative_to(base) if path.is_relative_to(base) else Path("external") / str(path).lstrip("/")
    target = out / "artifacts" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    target.write_bytes(data)
    artifacts.append({"remote": str(path), "relative": str(target.relative_to(out)), "sha256": hashlib.sha256(data).hexdigest()})
    inputs.append(path)
    return read_json(path) if path.suffix == ".json" else None
def completed_stage(folder):
    manifest = folder / "manifest.json"
    if not manifest.exists(): return None
    m = attach(manifest)
    data = attach(folder / "metrics.json")
    return {"manifest": str(manifest), "stage_metrics": m["metrics"], "data": data}
def capture_progress(folder, pattern):
    result = []
    for p in sorted(folder.glob(pattern)):
        raw = p.read_bytes()
        complete_lines = raw.splitlines(keepends=True)
        count = sum(bool(line.strip()) for line in complete_lines if line.endswith(b"\n"))
        result.append({"path": str(p), "complete_records": count, "bytes": len(raw), "sha256_at_read": hashlib.sha256(raw).hexdigest(),
                       "manifest_complete": (p.parent / "manifest.json").exists()})
    return result

acceptance = attach(audit / "acceptance/manifest.json")["metrics"]
ded_review = attach(audit / "8465954-deduction-review/manifest.json")["metrics"]
queues = {}
for name in ("lean_reverification_20260913_local", "development_20260913", "controls_20260913_local", "lean_reverification_20260913", "development_20260913_exactlength"):
    p = out / "inputs" / (name + "-queue.json")
    q = read_json(p)
    inputs.append(p)
    queues[name] = {"counts": dict(Counter(t["state"] for t in q["tasks"].values())),
                    "last_poll_utc": q.get("last_poll_utc"), "source": q["source"],
                    "failures": {k: t for k,t in q["tasks"].items() if t["state"] in ("FAILED","BLOCKED")},
                    "active": {k: t for k,t in q["tasks"].items() if t["state"] in ("PENDING","RUNNING")}}
attach(base / "audit/status_2026_09_13/final-v2/REPORT.md", recursive=False)
for queue_name, queue_state in queues.items():
    for task in queue_state["failures"].values():
        for path in (base / "runs" / queue_name / "logs").glob("*-"+str(task.get("job_id"))+".log"):
            attach(path, recursive=False)
main = {}
for model in ("deepseek", "goedel", "kimina"):
    root = base / "runs/lean_reverification_20260913_local" / model
    samples, manifests = generation_inputs(root, "main")
    for p in manifests: attach(p)
    main[model] = {"saved_attempts": len(samples), "unique_ids": len({s["trace_id"] for s in samples}),
                   "complete_planned_ids": True, "distinct_tasks": len({s["problem_id"] for s in samples}),
                   "pilot": {}, "main": {},
                   "verification_progress": capture_progress(root / "main/verification", "shard-*/labels.jsonl")}
    for phase in ("pilot","main"):
        attach(root / phase / "protocol.json")
        for stage in ("verification","extraction","measurement","analysis"):
            main[model][phase][stage] = completed_stage(root / phase / stage)
    for p in (root / "collection-gate/manifest.json", root / "main/collection-gate/manifest.json"):
        if p.exists(): attach(p)
ded_root = base / "runs/development_20260913/deduction"
ded = {s: completed_stage(ded_root / "pilot" / s) for s in ("verification","extraction","measurement","analysis","gate")}
attach(ded_root / "protocol.json")
for name in ("inputs/problems.json","pilot/generation/shard-000-of-001/samples.jsonl","pilot/verification/labels.jsonl","pilot/extraction/trajectories.jsonl"):
    attach(ded_root / name, recursive=False)
ded_generations = rows(ded_root / "pilot/generation/shard-000-of-001/samples.jsonl")
assigned = {r["trace_id"]:r["problem"]["length"] for r in ded_generations}
format_labels = [r for r in rows(ded_root / "pilot/verification/labels.jsonl") if r["category"]=="format_error"]
format_breakdown = {"attempts":len(format_labels), "with_unknown_lines":sum(bool(r["unknown_lines"]) for r in format_labels),
                    "step_count_delta":dict(Counter(str(r["observed_steps"]-assigned[r["trace_id"]]) for r in format_labels))}
ded_review["format_breakdown"] = format_breakdown

p3_root = base / "runs/p3_validation_20260913"
p3 = {"protocol": attach(p3_root / "protocol.json"), "summary": completed_stage(p3_root / "summary"),
      "progress": capture_progress(p3_root, "shard-*/replicates.jsonl")}
for p in sorted(p3_root.glob("shard-*/manifest.json")):
    attach(p)
    attach(p.parent / "replicates.jsonl", recursive=False)
if p3["summary"]:
    from onebigjump.readiness.p3_validation import proportion
    records = [r for file in sorted(p3_root.glob("shard-*/replicates.jsonl")) for r in rows(file)]
    assert len(records) == p3["summary"]["data"]["datasets"]
    paired = {}
    for scenario in p3["protocol"]["scenarios"]:
        sample = [r for r in records if r["request"]["scenario"] == scenario]
        paired[scenario] = {}
        for method in ("percentile","basic"):
            common = [r for r in sample if all(r["methods"][c][method]["ci95"] is not None for c in ("original","observed_support"))]
            def covers(r,c):
                interval = r["methods"][c][method]["ci95"]
                return interval is not None and interval[0] <= r["truth"] <= interval[1]
            old_cov = [covers(r,"original") for r in common]
            new_cov = [covers(r,"observed_support") for r in common]
            dropped = [r for r in sample if r["methods"]["original"][method]["ci95"] is not None and r["methods"]["observed_support"][method]["ci95"] is None]
            paired[scenario][method] = {
                "both_available":len(common), "original_coverage_on_common":proportion(old_cov),
                "candidate_coverage_on_common":proportion(new_cov),
                "candidate_gains":sum(b and not a for a,b in zip(old_cov,new_cov)),
                "candidate_losses":sum(a and not b for a,b in zip(old_cov,new_cov)),
                "original_only":len(dropped),
                "original_coverage_on_dropped":proportion([covers(r,"original") for r in dropped])}
    p3["paired_review"] = paired
for queue_name in queues:
    for receipt in sorted((base / "runs" / queue_name / "controller").glob("*.json")):
        if receipt.name != "identity.json": attach(receipt, recursive=False)
controls_root = base / "runs/controls_20260913_local"
controls = []
for p in sorted((controls_root / "main").rglob("manifest.json")):
    m = attach(p); data = attach(p.parent / "metrics.json")
    controls.append({"path": str(p), "metrics": m["metrics"], "data": data})
for name in ("all-8465920.xml","all-8465920.log","cleanup-fixed-8465927.xml","cleanup-fixed-8465927.log",
             "8465921-preflight/metrics.json","8465921-preflight/results-server-only.json",
             "8465923-stress/metrics.json","8465954-deduction-review/metrics.json",
             "acceptance/metrics.json"):
    attach(audit / name, recursive=False)
for name in ("config.json","manifest.json","Snapshots.lean","Frontend.lean","build_scoped_repl.py"):
    attach(base / "runs/repl_runtime_20260913_sealed" / name)
attach(base / "configs/repl_runtime.json")
attach(base / "STATUS.md", recursive=False)
attach(audit / "snapshots/lean-scopes-v3/source-manifest.json")
attach(audit / "snapshots/lean-scopes-v3/tests/unit/test_repl_process_cleanup.py")
snapshot_copy = out / "source"
snapshot_copy.mkdir(exist_ok=True)
for folder in ("src","scripts","tests","configs","docs"):
    shutil.copytree(source.parent / folder, snapshot_copy / folder,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "._*"), dirs_exist_ok=True)
shutil.copy2(source, snapshot_copy / "source-manifest.json")
for name in ("pyproject.toml","Makefile","AGENTS.md"):
    shutil.copy2(source.parent / name, snapshot_copy / name)

# Read-only incident and repaired runtime evidence, retained beside scientific outputs.
io_incident = attach(audit / "io-audit-8466023/manifest.json")["metrics"]
attach(audit / "io-audit-8466023/metrics.json")
attach(audit / "io-audit-8466023/suspect-labels.json")
for name in ("io_audit_v2.py","io-unit-8466025.xml","io-unit-8466025.log","hashseed-unit-8466030.log","all-8466027.xml","local-validation-8466027.log",
             "all-8466032.xml","local-validation-8466032.log",
             "8466032-preflight/manifest.json","8466032-preflight/metrics.json",
             "8466032-preflight/results-server-only.json"):
    attach(audit / name)
toolchain_config = attach(source.parent / "configs/lean_toolchain_runtime.json")
toolchain_manifest = Path(toolchain_config["manifest"])
attach(toolchain_manifest)
attach(toolchain_manifest.parent / "metrics.json")
attach(toolchain_manifest.parent / "inventory.json")
validation = {"job_id":"8466032","preflight":None,"test_counts":None}
if (audit/"8466032-preflight/metrics.json").exists():
    validation["preflight"] = read_json(audit/"8466032-preflight/metrics.json")
if (audit/"all-8466032.xml").exists():
    import xml.etree.ElementTree as ET
    suites=list(ET.parse(audit/"all-8466032.xml").getroot().iter("testsuite"))
    validation["test_counts"]={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ("tests","failures","errors","skipped")}

# Additive reviews from the current continuation.
compiler_review = completed_stage(audit / "8466072-compiler-review")
pilot_attestation = completed_stage(audit / "8466083-review-attestation")
p3_availability = completed_stage(audit / "8466076-p3-availability")
for directory in (audit / "8466072-compiler-review", audit / "8466083-review-attestation", audit / "8466076-p3-availability"):
    if (directory / "manifest.json").exists():
        for p in sorted(directory.rglob("*")):
            if p.is_file() and p.name not in ("manifest.json","metrics.json"):
                attach(p, recursive=False)
exact_root = base / "runs/development_20260913_exactlength"
deduction_exact_review = completed_stage(audit / "8466088-deduction-review")
deduction_exact = {"protocol": attach(exact_root / "deduction/protocol.json"),
                   "review": deduction_exact_review,
                   "validation": completed_stage(exact_root / "validation"),
                   "stages": {stage: completed_stage(exact_root / "deduction/pilot" / stage)
                              for stage in ("verification","extraction","measurement","analysis","gate")}}
for p in (exact_root / "deduction/inputs/problems.json",
          exact_root / "validation/prompts.json",
          exact_root / "deduction/pilot/generation/shard-000-of-001/samples.jsonl",
          exact_root / "deduction/pilot/verification/labels.jsonl"):
    if p.exists() and (p.parent / "manifest.json").exists(): attach(p, recursive=False)
if deduction_exact["stages"]["verification"]:
    labels = rows(exact_root / "deduction/pilot/verification/labels.jsonl")
    deduction_exact["label_summary"] = {"attempts":len(labels),"categories":dict(Counter(r["category"] for r in labels)),
                                       "format_eligible":sum(r["format_eligible"] for r in labels)}
attach(audit / "snapshots/deduction-numbered-v3/source-manifest.json")
attach(audit / "snapshots/deduction-numbered-v3/src/onebigjump/readiness/deduction.py")
attach(audit / "deduction_exact_preflight.py", recursive=False)
attach(audit / "8466088-deduction-review/examples-server-only.json", recursive=False)
attach(audit / "deduction_exact_review.py", recursive=False)
attach(exact_root / "deduction/pilot/measurement/calibration.json", recursive=False)
attach(audit / "exact-preflight-8466080.xml", recursive=False)

# Future completion reports also audit axiom-policy exclusions on the full main labels.
from onebigjump.e1.verification import ALLOWED_AXIOMS
from onebigjump.e1.spans import mask_comments
import re
def native_policy_inventory(path):
    data = rows(path)
    native_only = []
    for r in data:
        live = mask_comments(r.get("body",""), mask_strings=True)
        live = re.sub(r"«[^»]*»", "", live)
        hole = bool(re.search(r"\b(?:sorry|admit|sorryAx)\b", live))
        unexpected = [name for name in r.get("axioms",[]) if name not in ALLOWED_AXIOMS]
        native = [name for name in unexpected if re.search(r"\._native\.native_decide\.ax(?:_\d+)?$", name)]
        if r.get("whole_proof_ok") is True and r.get("replay_ok") is True and not hole and native and set(native)==set(unexpected):
            native_only.append(r["trace_id"])
    return {"attempts":len(data),"primary_categories":dict(Counter(r["category"] for r in data)),
            "native_policy_only_count":len(native_only),"native_policy_only_ids":native_only,
            "primary_labels_changed":False}
full_native_policy = {}
for model in ("deepseek","goedel","kimina"):
    model_root = base / "runs/lean_reverification_20260913_local" / model
    pilot_check = native_policy_inventory(model_root / "pilot/verification/labels.jsonl")
    if compiler_review:
        assert pilot_check["native_policy_only_count"] == compiler_review["data"]["pilot_inventory"][model]["native_policy_only"]
    final_labels = model_root / "main/verification/labels.jsonl"
    if (final_labels.parent / "manifest.json").exists():
        attach(final_labels.parent / "manifest.json")
        full_native_policy[model] = native_policy_inventory(final_labels)
    else:
        full_native_policy[model] = {"available":False,"reason":"main verification manifest not complete"}

finished = datetime.now(timezone.utc).isoformat()
metrics = {"started_utc": started, "finished_utc": finished, "acceptance": acceptance,
           "queues": queues, "main": main, "deduction_review": ded_review, "deduction": ded,
           "p3": p3, "main_controls": controls, "primary_method_changed": False,
           "source": str(source), "source_sha256": digest(source), "io_incident":io_incident, "runtime_validation":validation}
metrics.update(compiler_review=compiler_review, pilot_attestation=pilot_attestation, p3_availability=p3_availability, deduction_exact=deduction_exact)
metrics["full_main_native_policy_inventory"] = full_native_policy
write_once(out / "metrics.json", metrics)

lines = []
def para(s): lines.extend([s, ""])
def table(headers, data):
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in data: lines.append("| " + " | ".join(str(x).replace("|","/") for x in row) + " |")
    lines.append("")
para("# Продолжение работ One Big Jump — проверяемый отчёт")
para("Срез собран на Жоресе: " + started + " — " + finished + ". Все расчёты, тесты и проверки выполнены через Slurm. Этот отчёт отделяет завершённые результаты от ещё выполняющихся стадий.")
para("## Новые результаты содержательного ревью")
if pilot_attestation:
    ar = pilot_attestation["data"]
    cr = compiler_review["data"]
    para("Ревью выполнено ассистентом по фиксированным пакетам gate: " + str(ar["reviewed_examples"]) +
         " примеров, " + str(ar["compilations"]) + " отдельных компиляций Lean. Это не человеческая подпись и не случайная выборка из основной серии.")
    table(["Результат проверки","Примеров"], [[k,v] for k,v in ar["statuses"].items()])
    para("Инфраструктурных ошибок в этих компиляциях: " + str(cr["infrastructure_errors"]) +
         "; превышений внешнего времени: " + str(cr["compiler_timeouts"]) +
         "; нарушений поглощающей разметки: " + str(cr["absorbing_violations"]) +
         ". Детерминированные ограничения heartbeats/recursion отдельно сохраняются как ресурсные отказы.")
    table(["Модель","Весь пилот","Исключения только из-за native-аксиом"],
          [[model,d["n"],d["native_policy_only"]] for model,d in cr["pilot_inventory"].items()])
    para("Все исключения Kimina, помеченные sorry_invalid_proof в этом пилоте, проходят whole/replay и не содержат буквального sorry в формальном теле. Причина — вспомогательные аксиомы native_decide, создаваемые закреплённым Lean и отсутствующие в прежнем белом списке. Оба примера из пакета проходят обычный компилятор. Отдельный диагностический вариант через decide использует стандартные аксиомы; он не подменяет выход модели.")
    para("Два разобранных исключения Goedel сохраняют условие, меняя только имя теоремы; строгая идентичность заголовка исключает их. Для одного DeepSeek-примера общий лимит heartbeats исчерпан при успешном пошаговом replay: t* отсутствует и не выдумывается.")
    para("Основные метки и политика допуска сохранены. В научном отчёте нужно отдельно считать native-зависимости и ограничения проверки заголовка. Возможный анализ с допуском native требует отдельной версии протокола, включая проверку происхождения аксиом; разрешать любые аксиомы по похожему имени нельзя.")
else:
    para("Манифест содержательного ревью ещё не готов на момент среза.")

para("Полная основная разметка: учёт native-политики выполняется автоматически после появления итоговых манифестов verification.")
table(["Модель","Результат аудита полной основной разметки"],
      [[model,{k:v for k,v in data.items() if k!="native_policy_only_ids"}] for model,data in full_native_policy.items()])
para("## P3: механизм потери интервалов")
if p3_availability:
    pa = p3_availability["data"]
    para("Разобраны все " + str(pa["datasets"]) + " ранее полученных наборов; новых подгонок и переоценок нет. Несовпадения восстановленных правил доступности: " + str(len(pa["availability_rule_mismatches"])) + ".")
    table(["Сценарий","Метод","Причины недоступности (совместные сочетания)"],
          [[scenario,method,data["exclusive_reason_sets"]] for scenario,item in pa["scenarios"].items()
           for method,data in item["methods"].items()])
    table(["Порог исходного метода, original_support","Наборов","Покрыто","Интервал ниже истины"],
          [[name,cell["datasets"],str(cell["coverage"]["successes"])+"/"+str(cell["coverage"]["datasets"]),
            cell["miss_below_truth"]]
           for name,cell in pa["scenarios"]["original_support"]["methods"]["original"]["intervals"]["percentile"].items()])
    para("Потери кандидата original_support объясняются недостатком калибровочных превышений после повышения порога. В экспоненциальном и ограниченном сценариях важны также нечисловые bootstrap-оценки. Эти разбиения описательные и не считаются новой независимой валидацией. Следующий ремонт должен отдельно объяснить сбои GPD-подгонки, затем пройти новый заранее зафиксированный независимый эксперимент.")

para("## Следующий технический пилот дедукции")
dc = deduction_exact["protocol"]
para("Зафиксирован " + dc["prompt_version"] + ", seed=" + str(dc["seed"]) +
     ". В промпте явно перечислены пронумерованные строки до назначенной длины. Порог формата: " +
     str(dc["format_gate"]) + "; allow_main=" + str(dc["allow_main"]) +
     ". Выходы не исправляются и не отбрасываются; guided decoding не используется.")
if deduction_exact["validation"]:
    dv = deduction_exact["validation"]["data"]
    para("Предпроверка: " + json.dumps(dv, ensure_ascii=False) + ". Функции чекера, генерации, измерений, анализа и gate совпадают с v7; изменён только промпт.")
if "label_summary" in deduction_exact:
    para("Свежие ответы: " + json.dumps(deduction_exact["label_summary"],ensure_ascii=False) + ".")
if deduction_exact_review:
    dr = deduction_exact_review["data"]
    para("Аудит всех свежих ответов: допустимый формат " + str(dr["groups"]["all"]["format_eligible"]) +
         "/" + str(dr["groups"]["all"]["attempts"]) + ", доля " + str(dr["groups"]["all"]["format_fraction"]) +
         "; format_gate_passed=" + str(dr["format_gate_passed"]) + ". Проверки эталонных цепочек: " +
         str(dr["gold_passed"]) + "/" + str(dr["gold_checks"]) + ".")
    para("Первые ошибки выводов: " + json.dumps(dr["first_errors"],ensure_ascii=False) +
         ". Среди ошибок формата встречаются добавленные объяснения в скобках; они сохранены в исходных текстах, а не удалены после генерации. В metrics.json есть разбивка по длинам и температуре.")
    para("Этот вариант не прошёл технический допуск. Сравнение с v2 описательное: задачи свежие и непарные, поэтому разность долей нельзя приписывать только изменению промпта. Следующий вариант генерации потребует отдельного протокола; произвольная серия подстроек промпта не является независимой проверкой.")
para("Готовность стадий: " + json.dumps({k:v is not None for k,v in deduction_exact["stages"].items()},ensure_ascii=False) +
     ". Успех технического gate не является подтверждением научной гипотезы и не разрешает автоматическую основную генерацию.")

para("## Инцидент хранилища и отдельная очередь восстановления")
para("Дополнительный дефект обнаружен полным прогоном: seed_everything передавал 64-битный seed в PYTHONHASHSEED, из-за чего дочерний Python отказывался запускаться. В v7 только PYTHONHASHSEED приведён к допустимому диапазону; seed Python random, NumPy и torch сохранены. Отдельные тесты реально запускают дочерние интерпретаторы. Полный повторный прогон выполнен; результаты приведены ниже.")

para("Основной прогон на снимке v4 прервался из-за Remote I/O error при чтении стандартной библиотеки Lean и записи артефактов. Свободное место было доступно; первопричина не установлена. Проба на одном узле прошла, что не доказывает устойчивость всего кластера.")
para("Аудит фиксированного снимка журналов: записей " + str(io_incident["total_rows"]) + ", меток с явными диагностическими признаками I/O — " + str(io_incident["suspect_label_count"]) + ". Отсутствие найденных строк ошибок не является полной валидацией незавершённого прогона.")
para("Защита транспорта теперь относит диагностические сообщения I/O к инфраструктурному отказу, без математического t*. Закреплённый Lean вместе со стандартной библиотекой размещается на диске вычислительного узла; версии и бинарники сохранены. Проверка монтирования требует, чтобы toolchain действительно находился на локальной файловой системе.")
para("Полная валидация v7 (Slurm 8466032): " + json.dumps(validation["test_counts"],ensure_ascii=False) + "; проверка сохранённых доказательств пройдена: " + str(bool(validation["preflight"] and validation["preflight"]["passed"])) + ".")
para("Промежуточный тестовый снимок v5 имел конфликт двух монтирований; исправление входит в v6. Очередь v7 допускается к запуску только после успешного задания 8466032. Подробная диагностика находится в metrics.json.")
para("Новая очередь: runs/lean_reverification_20260913_local; контрольные анализы: runs/controls_20260913_local. Старые задания не отменялись. Старые частичные метки сохраняются для аудита, новая очередь проверяет исходные генерации заново. Лимит отправки CPU-заданий снижен, каждый REPL резервирует 32 CPU. Это проверяемая мера против обращений Lean к сетевому хранилищу, а не установленное объяснение всех отказов.")
para("Автоматическая проверка ранее отклонила отмену старых работающих заданий из-за риска потери прогресса и недостаточной явности разрешения. Отмена не выполнялась; восстановление организовано отдельной очередью без изменения этих заданий.")

para("## Что реализовано и проверено")
para("Исправлены три дефекта Lean: восстановление активных scoped namespaces при replay с сохранением исходного набора констант; завершение всей принадлежащей REPL группы процессов и закрытие обоих потоков чтения; распознавание отказа ядра из proofStatus. Последний дефект мог сдвигать первый ошибочный шаг, даже когда итоговый отказ доказательства уже был известен.")
para("Сохранённые ответы моделей используются повторно без изменения токенов. Новая разметка хранится в runs/lean_reverification_20260913_local. Протоколы и основная ячейка анализа сохранены. Whitening/позиционные проверки ожидают её выходы. P4 повторно не обучался.")
tv = acceptance["tests"]
table(["Проверка","Тестов","Падений","Ошибок","Пропусков"], [
    ["Общий прогон 8465920",*[tv["full_run"][k] for k in ("tests","failures","errors","skipped")]],
    ["Исправленный тест очистки 8465927",*[tv["followup"][k] for k in ("tests","failures","errors","skipped")]]])
para("Общий прогон включает live Lean и GPT-2. Единственный отказ был гонкой чтения /proc в новом тесте: процесс исчезал между exists() и read_text(). Исправлен только этот тест и выполнен повторно. Допуск 8465929 проверил байтовую идентичность всех остальных файлов между снимками v3 и v4. Это составная валидация, а не повторный полностью зелёный общий прогон: уникальных проверенных тестов " + str(tv["unique_validated_tests"]) + ", неустранённых отказов " + str(tv["unresolved_failures"]) + ".")
stress = acceptance["stress"]
table(["Проверка ресурсов","Значение"], [
    ["Сессий REPL",stress["sessions"]],["Доказательств в стресс-тесте",stress["traces"]],
    ["Циклов",len(stress["cycles"])],["Максимальный счётчик открытых файлов",stress["peak_file_nr"]],
    ["Системный лимит файлов",stress["file_limit"]]])
para("Проверены две одновременные сессии и повторные циклы запуска/закрытия. Оставшихся живых дочерних процессов не обнаружено; задержанное освобождение файлов наблюдалось в течение нескольких секунд. Это ограниченная нагрузочная проверка, не гарантия отсутствия любых сбоев в многочасовой серии. Основные Lean-задачи резервируют половину CPU узла, ограничивая число наших REPL на узле двумя.")
table(["Сохранённый пример","Категория","Первый отказ, индекс с нуля","Необъяснённое расхождение"], [
    [r["trace_id"],r["category"],r["t_star"],r["unexplained_disagreement"]]
    for r in acceptance["preflight"]["cases_summary"]])
para("Отрицательный пример mathd_numbertheory_495 независимо проверен компиляцией префиксов: префикс до ошибочного шага принимается, включающий его — отклоняется. Он сохранён как отрицательный результат.")
para("## Основная Lean-выборка")
table(["Модель","Сохранённых генераций","Уникальных ID","Задач","Строк новой разметки, включая незавершённые шарды","Основной анализ готов"], [
    [model,m["saved_attempts"],m["unique_ids"],m["distinct_tasks"],
     sum(r["complete_records"] for r in m["verification_progress"]),bool(m["main"]["analysis"])]
    for model,m in main.items()])
para("Для каждой модели сверены все плановые ID и манифесты генераций. Счётчики незавершённой разметки приведены только как прогресс; они не являются пригодной для итоговых сравнений выборкой. Наличие отдельных правильных доказательств или завершённой генерации не заменяет полную верификацию, extraction, measurement и analysis.")
for model,m in main.items():
    v = m["pilot"]["verification"]
    if v: para(model + " — завершённая проверка пилота: `" + json.dumps(v["stage_metrics"],ensure_ascii=False,sort_keys=True) + "`.")
for model,model_data in main.items():
    analysis = model_data["main"]["analysis"]
    if not analysis: continue
    para("### Завершённый основной анализ: " + model)
    verification = model_data["main"]["verification"]
    if verification: para("Знаменатели проверки: " + json.dumps(verification["stage_metrics"],ensure_ascii=False,sort_keys=True))
    cells = analysis["data"].get("cells",[])
    tail_rows = []
    rank_rows = []
    for cell in cells:
        axes = [cell.get("layer"),cell.get("statistic"),cell.get("temperature")]
        for group,fit in (cell.get("P1") or {}).items():
            if not isinstance(fit,dict): continue
            tail_rows.append(axes+[group,fit.get("n_tasks"),fit.get("n_traces"),
                                  fit.get("hill"),fit.get("moment"),fit.get("gpd"),fit.get("ci"),fit.get("decision")])
        ranking=cell.get("P2") or {}
        rank_rows.append(axes+[ranking.get("n_tasks"),ranking.get("n_traces"),
                              ranking.get("jump",{}).get("top1"),ranking.get("chance"),
                              ranking.get("surprisal",{}).get("top1"),ranking.get("paired_difference"),
                              ranking.get("paired_ci"),ranking.get("decision")])
    if tail_rows: table(["Слой","Статистика","T","Группа","Задач","Трасс","Hill","Moment (signed)","GPD","CI","Решение"],tail_rows)
    if rank_rows: table(["Слой","Статистика","T","Задач","Трасс","Jump top1","Chance","Surprisal top1","Парная разность","CI","Решение"],rank_rows)
    para("Приведены все доступные ячейки; это не выбор основной ячейки по результату. P3, исключение первого приращения, полные знаменатели и причины недоступных оценок сохранены в metrics.json и манифестах.")

para("## Свежий технический пилот дедукции")
d = ded_review["groups"]["all"]
table(["Показатель","Результат"], [
    ["Все попытки",d["attempts"]],["Допустимый формат",d["format_eligible"]],
    ["Ошибки формата",d["format_error"]],["Ошибки вывода",d["invalid_inference"]],
    ["Доказательства, принятые проверяющим алгоритмом",d.get("verified",0)],
    ["Доля допустимого формата",d["format_fraction"]],
    ["Требуемый порог",ded_review["format_gate"]],
    ["Эталонные цепочки приняты",str(ded_review["gold_passed"])+"/"+str(ded_review["gold_checks"])],
    ["Проверяющий алгоритм сохранён",ded_review["checker_unchanged"]],
    ["Gate формата пройден",ded_review["format_gate_passed"]]])
para("Инструкция worked-example-v2 демонстрирует ровно L новых фактов и явно исключает печать исходного факта. Задачи свежие; это не парное сравнение инструкций на одинаковых задачах. Все ответы сохранены. Порог не снижался, проверяющий алгоритм не изменялся. Большая серия запрещена allow_main=false. FAILED у deduction/gate — ожидаемый отказ допуска из-за недостаточного формата, а не потеря пилотных результатов.")
table(["Срез","Попыток","Допустимый формат","Правильных доказательств"], [
    [key,v["attempts"],v["format_eligible"],v.get("verified",0)]
    for key,v in ded_review["groups"].items() if key.startswith("temperature:")])
table(["Назначенная длина","Попыток","Допустимый формат","Правильных доказательств"], [
    [length,ded_review["groups"]["length:"+str(length)]["attempts"],
     ded_review["groups"]["length:"+str(length)]["format_eligible"],
     ded_review["groups"]["length:"+str(length)].get("verified",0)] for length in range(3,13)])
para("Причины отклонения формата: `" + json.dumps(format_breakdown,sort_keys=True) + "`. Разница числа шагов считается относительно назначенной длины.")
para("Распределение первых ошибок: `" + json.dumps(ded_review["first_errors"],sort_keys=True) + "`. t_star здесь нумеруется с нуля. Это описательная диагностика; малый development-пилот не подтверждает P1–P5.")
para("## Независимая калибровка P3")
pc = p3["protocol"]
para("До запусков зафиксированы новые seed, четыре сценария и четыре варианта интервала. Новый кандидат выбирает максимум калибровочного квантиля и минимального наблюдаемого значения в группе ошибок. Оба компонента заново оцениваются в каждом bootstrap по задачам. Истинная граница используется только для диагностики симуляции и не поступает в оцениватель.")
table(["Сценарий","Истинная форма GPD","Квантиль отбора ошибок","Наборов по плану"], [
    [name,c["shape"],c["failure_quantile"],pc["datasets"]] for name,c in pc["scenarios"].items()])
para("Bootstrap-реплик на набор: " + str(pc["statistics"]["bootstrap"]) + ". Завершённых записей на момент чтения: " + str(sum(r["complete_records"] for r in p3["progress"])) + ".")
if p3["summary"]:
    final = p3["summary"]["data"]
    table(["Сценарий","Метод","Интервал доступен","Покрытие среди доступных","95% Monte Carlo CI","Недопокрытие обнаружено"], [
        [scenario,method,
         str(cell["availability"]["successes"])+"/"+str(cell["availability"]["datasets"]),
         str(cell["coverage_conditional_on_available"]["successes"])+"/"+str(cell["coverage_conditional_on_available"]["datasets"]),
         cell["coverage_conditional_on_available"]["monte_carlo_ci95"],cell["undercoverage_detected"]]
        for scenario,methods in final["scenarios"].items() for method,cell in methods.items()])
    table(["Сценарий","Интервал","Общие доступные наборы","Покрытие исходного на них","Покрытие кандидата на них","Исправлено/потеряно покрытий","Исходный доступен, кандидат нет"], [
        [scenario,method,cell["both_available"],cell["original_coverage_on_common"]["fraction"],
         cell["candidate_coverage_on_common"]["fraction"],str(cell["candidate_gains"])+"/"+str(cell["candidate_losses"]),cell["original_only"]]
        for scenario,methods in p3["paired_review"].items() for method,cell in methods.items()])
    para("Парное сравнение на общем доступном подмножестве показывает изменение покрытия отдельно от изменения доступности. Потерянные для кандидата наборы не исключаются из общего знаменателя.")
    common = p3["paired_review"]["original_support"]["percentile"]
    para("В original_support на общих доступных наборах исходный метод покрывает истину в " +
         str(common["original_coverage_on_common"]["successes"]) + "/" + str(common["both_available"]) +
         ", кандидат — в " + str(common["candidate_coverage_on_common"]["successes"]) + "/" + str(common["both_available"]) +
         ". Кандидат получает " + str(common["candidate_gains"]) + " новых покрытий и теряет " +
         str(common["candidate_losses"]) + ", одновременно не выдавая интервал ещё для " +
         str(common["original_only"]) + " наборов, где исходный метод был доступен. Поэтому сравнение условных процентов на разных знаменателях преувеличивает преимущество кандидата; калибровка всего метода не установлена.")

else:
    para("Сводная независимая валидация ещё не завершена. Промежуточные значения не используются для выбора метода или изменения протокола.")
para("В metrics.json и артефактах отдельно сохраняются доступность интервалов, условное покрытие, покрытие с учётом недоступных оценок как неудач, смещение и положительные семейные отвержения. Перекрытие Monte Carlo интервала с номиналом не доказывает калибровку. Автоматическое внедрение кандидата в основной анализ запрещено.")
para("## Whitening, позиционные эффекты и P4")
para("Все ранее выполненные пилотные контроли сохранены. Ожидающие основные контроли перепривязаны на новую разметку: независимые transform/threshold, shrinkage, исключение первого приращения и сравнение с surprisal на одинаковых трассах. Готовых основных манифестов в этой очереди: " + str(len(controls)) + ". Их значения находятся в metrics.json и вложенных артефактах.")
para("Основная ячейка анализа не менялась после просмотра результатов. Предыдущий вывод по P4 сохраняется: обучение воспроизведено, ожидаемый переход хвостового индекса не подтверждён. Новая серия P4 не запускалась.")
para("## Очереди и оставшиеся действия")
table(["Очередь","Состояния"], [[name,json.dumps(q["counts"],sort_keys=True)] for name,q in queues.items()])
para("Счётчики очередей включают внешние зависимости и повторно используемые генерации. Число COMPLETED нельзя интерпретировать как число новых научных результатов.")
for name,q in queues.items():
    if q["failures"]: para(name + " — задачи с отказом/блокировкой: `" + json.dumps({k:v["state"] for k,v in q["failures"].items()},ensure_ascii=False,sort_keys=True) + "`.")
para("До окончательных научных выводов нужны завершённые основные verification/extraction/measurement/analysis и весь предусмотренный набор контролей. Проверять следует полноту знаменателей, необъяснённые whole/replay расхождения, absorption, доступность независимой калибровки и стабильность результатов на заранее заданных проверках.")
para("Дедукция пока не готова к большой серии. Свежий технический пилот numbered-slots-v3 зафиксирован и описан выше; текущие и прошлые ответы нельзя переписывать или исключать задним числом. Независимая серия P3 завершена; кандидат не проходит совокупность проверок доступности и покрытия и не заменяет основной метод.")
para("## Происхождение и проверка другим GPT")
para("Предыдущий подробный отчёт приложен в artifacts/audit/status_2026_09_13/final-v2/REPORT.md как исторический срез. Состояния очередей в нём предшествуют текущему ремонту; актуальные состояния приведены в этом отчёте.")
para("Исходники: `" + str(source) + "`; SHA256 манифеста: `" + digest(source) + "`. Git commit: `" + read_json(source)["metrics"]["git_commit"] + "`, dirty=" + str(read_json(source)["metrics"]["dirty"]) + ". Один commit не описывает эти изменения; точные исходники и их хеши приложены.")
para("В каталоге source находятся код, тесты, конфигурации и документация снимка. artifact-index.json связывает серверные пути с копиями и SHA256. report manifest записывает входы, окружение и хеши выходов. Веса моделей, полный объём генераций и активаций в пакет не включены; их серверные пути и хеши сохранены в исходных манифестах.")
para("Для независимой проверки: сопоставить утверждения с metrics.json; проверить составную валидацию и единственное изменение теста между v3/v4; проверить шесть сохранённых Lean-примеров и результаты стресса; убедиться в неизменности проверяющего алгоритма дедукции и её порога; проверить все сценарии P3, включая недоступные интервалы; не принимать счётчики незавершённых шардов за итоговую статистику.")
(out / "REPORT.md").write_text("\n".join(lines),encoding="utf-8")
(out / "FOR_REVIEWING_GPT.md").write_text("# \u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f \u0434\u043b\u044f \u043d\u0435\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0433\u043e \u0440\u0435\u0432\u044c\u044e One Big Jump\n\n\u041f\u0440\u043e\u0432\u0435\u0440\u044c \u0440\u0430\u0431\u043e\u0442\u0443 \u043f\u043e \u044d\u0442\u043e\u043c\u0443 \u043f\u0430\u043a\u0435\u0442\u0443, \u043d\u0435 \u043f\u0440\u0435\u0434\u043f\u043e\u043b\u0430\u0433\u0430\u044f, \u0447\u0442\u043e \u0433\u0438\u043f\u043e\u0442\u0435\u0437\u0430 \u0434\u043e\u043b\u0436\u043d\u0430 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c\u0441\u044f.\n\n\u041d\u0430\u0447\u043d\u0438 \u0441 REPORT.md \u0438 metrics.json. \u0421\u0432\u0435\u0440\u044c \u0432\u044b\u0432\u043e\u0434\u044b \u0441 artifact-index.json \u0438\n\u043c\u0430\u043d\u0438\u0444\u0435\u0441\u0442\u0430\u043c\u0438 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0445 \u0437\u0430\u043f\u0443\u0441\u043a\u043e\u0432. \u041a\u0430\u0442\u0430\u043b\u043e\u0433 source \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u0442 \u0442\u043e\u0447\u043d\u044b\u0439 \u0441\u043d\u0438\u043c\u043e\u043a,\n\u0432\u043a\u043b\u044e\u0447\u0430\u044f experimental_specification.md \u0438 \u0442\u0435\u0441\u0442\u044b. \u0418\u0441\u0442\u043e\u0440\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u043e\u0442\u0447\u0451\u0442 \u0432 artifacts\n\u043e\u043f\u0438\u0441\u044b\u0432\u0430\u0435\u0442 \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435 \u0434\u043e \u0442\u0435\u043a\u0443\u0449\u0438\u0445 \u0438\u0441\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0439. \u0421\u0435\u0440\u0432\u0435\u0440\u043d\u044b\u0435 \u0430\u0431\u0441\u043e\u043b\u044e\u0442\u043d\u044b\u0435 \u043f\u0443\u0442\u0438 \u0432\n\u043c\u0430\u043d\u0438\u0444\u0435\u0441\u0442\u0430\u0445 \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u044e\u0442 \u043f\u0440\u043e\u0438\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435; \u0432\u0435\u0441\u0430, \u0432\u0435\u0441\u044c \u043c\u0430\u0441\u0441\u0438\u0432 \u0430\u043a\u0442\u0438\u0432\u0430\u0446\u0438\u0439 \u0438 \u0432\u0441\u0435 \u043e\u0441\u043d\u043e\u0432\u043d\u044b\u0435\n\u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438 \u0432 \u0430\u0440\u0445\u0438\u0432 \u043d\u0435 \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u044b. \u0415\u0441\u043b\u0438 \u043d\u0435 \u043c\u043e\u0436\u0435\u0448\u044c \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0442\u0430\u043a\u043e\u0439 \u0432\u0445\u043e\u0434, \u044f\u0432\u043d\u043e \u0443\u043a\u0430\u0436\u0438\n\u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u0435, \u0430 \u043d\u0435 \u043e\u0431\u044a\u044f\u0432\u043b\u044f\u0439 \u0432\u0441\u044e \u0446\u0435\u043f\u043e\u0447\u043a\u0443 \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0439.\n\n\u041f\u0440\u043e\u0432\u0435\u0440\u044c \u043f\u0440\u0435\u0436\u0434\u0435 \u0432\u0441\u0435\u0433\u043e:\n- \u041a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u043e\u0441\u0442\u044c Lean replay: \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 scopes \u0431\u0435\u0437 \u043f\u0435\u0440\u0435\u043d\u043e\u0441\u0430 \u043a\u043e\u043d\u0441\u0442\u0430\u043d\u0442-\u043e\u0442\u0432\u0435\u0442\u043e\u0432,\n  \u043e\u0442\u043a\u0430\u0437 \u044f\u0434\u0440\u0430 \u0438\u0437 proofStatus, \u0440\u0435\u0430\u043b\u044c\u043d\u044b\u0439 \u043f\u0435\u0440\u0432\u044b\u0439 \u043e\u0448\u0438\u0431\u043e\u0447\u043d\u044b\u0439 \u0448\u0430\u0433, absorbing labels,\n  \u0438\u0441\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043e\u0448\u0438\u0431\u043e\u043a \u0438\u043d\u0444\u0440\u0430\u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u044b \u0438\u0437 \u043c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0445 \u043e\u0442\u043a\u0430\u0437\u043e\u0432.\n- \u041e\u0447\u0438\u0441\u0442\u043a\u0443 \u0432\u0441\u0435\u0439 \u0441\u043e\u0431\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0439 \u0433\u0440\u0443\u043f\u043f\u044b \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0432 \u0438 \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e\u0435 \u0440\u0430\u0437\u043c\u0435\u0449\u0435\u043d\u0438\u0435 \u0432\u0441\u0435\u0433\u043e Lean.\n  \u041f\u0440\u043e\u0448\u0435\u0434\u0448\u0438\u0439 \u0442\u0435\u0441\u0442 \u043d\u0430 \u043e\u0434\u043d\u043e\u043c \u0443\u0437\u043b\u0435 \u043d\u0435 \u0434\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442, \u0447\u0442\u043e \u043f\u0440\u0438\u0447\u0438\u043d\u0430 \u0441\u0435\u0442\u0435\u0432\u043e\u0433\u043e I/O \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0430.\n- \u041f\u043e\u043b\u043d\u043e\u0442\u0443 \u043e\u0441\u043d\u043e\u0432\u043d\u044b\u0445 \u0434\u0430\u043d\u043d\u044b\u0445 \u043f\u043e \u043f\u043b\u0430\u043d\u043e\u0432\u044b\u043c ID. \u0427\u0430\u0441\u0442\u0438\u0447\u043d\u044b\u0435 \u0436\u0443\u0440\u043d\u0430\u043b\u044b \u043d\u0435 \u044f\u0432\u043b\u044f\u044e\u0442\u0441\u044f \u0438\u0442\u043e\u0433\u043e\u0432\u044b\u043c\n  \u043d\u0430\u0431\u043e\u0440\u043e\u043c, \u0430 COMPLETED \u0432\u043a\u043b\u044e\u0447\u0430\u0435\u0442 \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u043e \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u043c\u044b\u0435 \u0432\u0445\u043e\u0434\u044b \u0438 \u0432\u043d\u0435\u0448\u043d\u0438\u0435 \u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0441\u0442\u0438.\n- \u041f\u043e\u043b\u043d\u044b\u0435 \u0437\u043d\u0430\u043c\u0435\u043d\u0430\u0442\u0435\u043b\u0438 \u0441\u0432\u0435\u0436\u0435\u0433\u043e \u043f\u0438\u043b\u043e\u0442\u0430 \u0434\u0435\u0434\u0443\u043a\u0446\u0438\u0438, \u0442\u043e\u0447\u043d\u044b\u0439 checker, \u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0439 gate,\n  \u043e\u0448\u0438\u0431\u043a\u0438 \u0434\u043b\u0438\u043d\u044b \u0438 \u0432\u044b\u0432\u043e\u0434\u043e\u0432 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u043e. \u041d\u0435 \u043f\u0440\u0435\u0432\u0440\u0430\u0449\u0430\u0439 development-\u043f\u0438\u043b\u043e\u0442 \u0432 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435.\n- \u0412\u0441\u0435 \u043d\u0435\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u044b\u0435 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0438 P3: \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e\u0441\u0442\u044c, \u0443\u0441\u043b\u043e\u0432\u043d\u043e\u0435 \u0438 \u0431\u0435\u0437\u0443\u0441\u043b\u043e\u0432\u043d\u043e\u0435 \u043f\u043e\u043a\u0440\u044b\u0442\u0438\u0435,\n  \u0438\u043d\u0442\u0435\u0440\u0432\u0430\u043b\u044b Monte Carlo, \u0441\u043c\u0435\u0449\u0435\u043d\u0438\u0435 \u0438 \u0441\u0435\u043c\u0435\u0439\u043d\u044b\u0435 \u043e\u0442\u0432\u0435\u0440\u0436\u0435\u043d\u0438\u044f. \u0421\u0440\u0430\u0432\u043d\u0438 \u043c\u0435\u0442\u043e\u0434\u044b \u0442\u0430\u043a\u0436\u0435\n  \u043f\u043e\u043f\u0430\u0440\u043d\u043e \u043d\u0430 \u043e\u0431\u0449\u0435\u043c \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e\u043c \u043f\u043e\u0434\u043c\u043d\u043e\u0436\u0435\u0441\u0442\u0432\u0435; \u0443\u0447\u0438\u0442\u044b\u0432\u0430\u0439 \u043f\u043e\u0442\u0435\u0440\u044f\u043d\u043d\u044b\u0435 \u043d\u0430\u0431\u043e\u0440\u044b.\n- Whitening: \u043d\u0435\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0441\u0442\u044c transform \u0438 threshold, shrinkage, \u0438\u0441\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043f\u0435\u0440\u0432\u043e\u0433\u043e\n  \u043f\u0440\u0438\u0440\u0430\u0449\u0435\u043d\u0438\u044f, \u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0441 surprisal \u043d\u0430 \u0442\u0435\u0445 \u0436\u0435 \u0442\u0440\u0430\u0441\u0441\u0430\u0445. \u041e\u0441\u043d\u043e\u0432\u043d\u0443\u044e \u044f\u0447\u0435\u0439\u043a\u0443 \u0430\u043d\u0430\u043b\u0438\u0437\u0430\n  \u043d\u0435\u043b\u044c\u0437\u044f \u0432\u044b\u0431\u0438\u0440\u0430\u0442\u044c \u0437\u0430\u043d\u043e\u0432\u043e \u043f\u043e \u0443\u0434\u043e\u0431\u043d\u043e\u043c\u0443 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0443.\n- \u041e\u0442\u0440\u0438\u0446\u0430\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u0438\u0442\u043e\u0433 P4: \u043e\u0431\u0443\u0447\u0435\u043d\u0438\u0435 \u0443\u0441\u043f\u0435\u0448\u043d\u043e, \u043d\u043e \u043e\u0436\u0438\u0434\u0430\u0435\u043c\u044b\u0439 \u043f\u0435\u0440\u0435\u0445\u043e\u0434 \u0445\u0432\u043e\u0441\u0442\u043e\u0432\u043e\u0433\u043e\n  \u0438\u043d\u0434\u0435\u043a\u0441\u0430 \u043d\u0435 \u043f\u0440\u043e\u0434\u0435\u043c\u043e\u043d\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043d. Hill \u043d\u0435 \u043c\u043e\u0436\u0435\u0442 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u043d\u0435\u043f\u043e\u043b\u043e\u0436\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u0438\u043d\u0434\u0435\u043a\u0441;\n  signed moment \u0438 GPD \u043d\u0435\u043b\u044c\u0437\u044f \u043e\u0431\u0440\u0435\u0437\u0430\u0442\u044c \u0434\u043e \u043d\u0443\u043b\u044f \u043f\u0435\u0440\u0435\u0434 \u043e\u0442\u0447\u0451\u0442\u043e\u043c.\n\n\u0412\u044b\u0434\u0430\u0439:\n1. \u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d\u043d\u044b\u0435 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u0438 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u043e \u043d\u0435\u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d\u043d\u044b\u0435 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f.\n2. \u041a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u044b\u0435 \u043e\u0448\u0438\u0431\u043a\u0438 \u0441 \u0444\u0430\u0439\u043b\u0430\u043c\u0438/\u0444\u0443\u043d\u043a\u0446\u0438\u044f\u043c\u0438 \u0438 \u0432\u043e\u0441\u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0438\u043c\u044b\u043c\u0438 \u043f\u0440\u0438\u043c\u0435\u0440\u0430\u043c\u0438.\n3. \u0427\u0442\u043e \u043c\u0435\u0448\u0430\u0435\u0442 \u043d\u0430\u0443\u0447\u043d\u043e\u043c\u0443 \u0432\u044b\u0432\u043e\u0434\u0443, \u0430 \u0447\u0442\u043e \u044f\u0432\u043b\u044f\u0435\u0442\u0441\u044f \u0442\u043e\u043b\u044c\u043a\u043e \u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0439 \u0448\u0435\u0440\u043e\u0445\u043e\u0432\u0430\u0442\u043e\u0441\u0442\u044c\u044e.\n4. \u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0435 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u0432 \u043f\u043e\u0440\u044f\u0434\u043a\u0435 \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442\u0430 \u0441 \u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0435\u043c \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0438\u044f.\n5. \u0427\u0442\u043e \u0442\u044b \u043d\u0435 \u0441\u043c\u043e\u0433 \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u043f\u043e \u043f\u0440\u0435\u0434\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u043d\u044b\u043c \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u0430\u043c.\n\n\u041d\u0435 \u043f\u0440\u0435\u0434\u043b\u0430\u0433\u0430\u0439 \u043f\u043e\u0434\u0433\u043e\u043d\u043a\u0443 seed, \u043f\u043e\u0440\u043e\u0433\u0430 \u0438\u043b\u0438 \u043e\u0441\u043d\u043e\u0432\u043d\u043e\u0439 \u044f\u0447\u0435\u0439\u043a\u0438 \u0434\u043e \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u0436\u0435\u043b\u0430\u0435\u043c\u043e\u0433\u043e \u0437\u043d\u0430\u043a\u0430.\n",encoding="utf-8")
write_once(out / "artifact-index.json", artifacts)
outputs = [p for p in out.rglob("*") if p.is_file() and p.name != "manifest.json"]
# Include copied artifact manifests too; the report's own manifest does not exist yet.
outputs = [p for p in out.rglob("*") if p.is_file()]
finish(out,stage="revision-status-report",context={"source":digest(source),"started_utc":started,"slurm_step_id":os.environ.get("SLURM_STEP_ID")},
       inputs=list(dict.fromkeys(inputs)),outputs=outputs,
       metrics={"started_utc":started,"finished_utc":finished,"primary_method_changed":False,
                "main_analysis_complete":all(m["main"]["analysis"] for m in main.values()),
                "p3_validation_complete":p3["summary"] is not None})
print("REPORT_WRITTEN",out,flush=True)
