"""Descriptive paired audit; no inferential selection or changes to pilot labels."""
from collections import Counter
from pathlib import Path
import os

from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.stages import rows
from onebigjump.readiness import deduction

import pipeline

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/p5_repair_20260914"
RUNS = BASE / "runs/p5_repair_20260914"
SOURCE = HERE / "source/source-manifest.json"
OUT = HERE / ("review-" + os.environ["SLURM_JOB_ID"])


def fraction(a, b):
    return a / b if b else None


def display(a, b):
    return f"{a}/{b} ({a/b:.1%})" if b else "нет наблюдений"


def main():
    summary = RUNS / "summary/manifest.json"
    verify_manifest(summary)
    receipt = read_json(HERE / "preflight-result.json")
    preflight = Path(receipt["manifest"])
    if digest(preflight) != receipt["manifest_sha256"]:
        raise ValueError("changed preflight receipt")
    verify_manifest(preflight)
    metrics = {"arms": {}, "paired": {}, "scientific_decision": "inconclusive",
               "analysis_scope": "descriptive secondary acquisition audit; no p-values or model selection",
               "primary_outcome": "technical acquisition gate with unchanged symbolic checker"}
    found = {}
    inputs = [SOURCE, summary, preflight, Path(__file__), HERE / "review.sbatch"]
    for arm in ("unguided", "guided"):
        root = RUNS / arm
        records, upstream = pipeline.records_for(root)
        inputs.extend(upstream)
        found[arm] = {r["trace_id"]: r for r in records}
        generated, _ = deduction.samples(root, "pilot")
        generated = {r["trace_id"]: r for r in generated}
        labels = rows(root / "pilot/verification/labels.jsonl")
        recomputed_matches = 0
        initial_failures = 0
        first_failures = Counter()
        for label in labels:
            sample = generated[label["trace_id"]]
            new = deduction.check(sample["completion"], sample["problem"])
            if sample["finish_reason"] == "length":
                new.update(category="generation_truncation", verified=False,
                           format_eligible=False, steps=[], step_spans=[], t_star=None)
            for key, value in new.items():
                if label[key] != value:
                    raise ValueError("recomputed verification mismatch")
            recomputed_matches += 1
            if label["category"] == "invalid_inference":
                first_failures[str(label["t_star"])] += 1
                if label["t_star"] == 0 and label["steps"][0]["fact"] == sample["problem"]["initial"]:
                    initial_failures += 1
        total = len(records)
        eligible = sum(r["format_eligible"] for r in records)
        verified = sum(r["verified"] for r in records)
        extraction = read_json(root / "pilot/extraction/manifest.json")
        trajectories = rows(root / "pilot/extraction/trajectories.jsonl")
        extracted = sum(r["extraction_status"] == "extracted" for r in trajectories)
        independent_checks = sum(bool(r.get("forward_check", {}).get("passed")) for r in trajectories)
        metrics["arms"][arm] = {
            "attempts": total, "categories": dict(Counter(r["category"] for r in records)),
            "format_eligible": eligible, "format_fraction": fraction(eligible, total),
            "verified": verified, "verified_fraction": fraction(verified, total),
            "verified_among_eligible": fraction(verified, eligible),
            "initial_fact_failures": initial_failures,
            "first_failure_index_counts": dict(first_failures),
            "extracted": extracted, "independent_forward_checks": independent_checks,
            "recomputed_labels_matching": recomputed_matches,
            "gate": read_json(root / "pilot/gate-attempt.json"),
            "length_rate_diagnostics": read_json(root / "pilot/analysis/metrics.json"),
            "measurement": read_json(root / "pilot/measurement/manifest.json")["metrics"],
            "calibration_support": read_json(root / "pilot/measurement/calibration.json"),
        }
        inputs.append(root / "pilot/extraction/manifest.json")
    if found["unguided"].keys() != found["guided"].keys():
        raise ValueError("unpaired attempts")
    # Report paired cells separately by held-out role and temperature.
    for rid, a in found["unguided"].items():
        b = found["guided"][rid]
        for key in ("trace_id", "problem_id", "role", "length", "temperature"):
            if a[key] != b[key]:
                raise ValueError("changed paired factors")
        group = f'{a["role"]}:T{a["temperature"]}'
        cell = metrics["paired"].setdefault(group, {"attempts": 0, "format": Counter(), "verified": Counter()})
        cell["attempts"] += 1
        for measure, field in (("format", "format_eligible"), ("verified", "verified")):
            cell[measure][f'unguided_{int(a[field])}_guided_{int(b[field])}'] += 1
    metrics["total_label_rechecks"] = sum(a["recomputed_labels_matching"] for a in metrics["arms"].values())
    for arm in ("unguided", "guided"):
        metrics["arms"][arm]["format_gain_vs_unguided"] = metrics["arms"][arm]["format_fraction"] - metrics["arms"]["unguided"]["format_fraction"]
    out_metrics = write_once(OUT / "metrics.json", metrics)
    report = ["# P5: результат отдельного исправления", "",
        "Пилот завершён независимо от основного эксперимента. Сравнение описательное: задача — проверить сбор данных, не подтвердить теорию.", "",
        "| Вариант | Допустимый формат | Верные выводы среди всех | Верные среди допустимых | Извлечено активаций | Технический допуск |",
        "|---|---:|---:|---:|---:|---|"]
    for arm, a in metrics["arms"].items():
        report.append(f'| {arm} | {display(a["format_eligible"], a["attempts"])} | {display(a["verified"], a["attempts"])} | {display(a["verified"], a["format_eligible"])} | {a["extracted"]} | {"пройден" if a["gate"]["passed"] else "не пройден"} |')
    report.extend(["", "## Что именно изменено", "",
        "В отдельной копии оценка c в P(успех|L)=exp(-cL) отделена от подгонки хвоста GPD. Нулевая успешность даёт явный граничный исход, а не исключение.",
        "Для guided зафиксированы лишь синтаксис и назначенное число строк; допускаются любые идентификаторы p0000…p9999, включая неверные.",
        "Задачи, запросы, температуры, seed, веса и бюджет токенов одинаковы в двух вариантах. Грамматика меняет распределение выбора токенов.",
        "Функции проверки, поглощение ошибки и порог технического допуска не менялись. Исходные main-протоколы и очереди не редактировались.", "",
        "## Проверка результата", "",
        f'Повторная проверка меток совпала для {metrics["total_label_rechecks"]} ответов. Манифесты, хеши и связь генерации с разметкой проверены.',
        f'CPU: {read_json(preflight)["metrics"]["tests"]["tests"]} теста, Ruff, mypy и проверка xgrammar на реальном токенизаторе.',
    ])
    for arm, a in metrics["arms"].items():
        report.append(f'\n{arm}: категории {a["categories"]}; ошибок на первом повторении исходного факта — {a["initial_fact_failures"]}; независимых проверок forward — {a["independent_forward_checks"]}.')
    report.extend(["", "Calibration для активаций:", "",
        "| Вариант | Температура | Слой | Успешных задач | Приращений | Преобразование доступно |",
        "|---|---:|---:|---:|---:|---|"])
    for arm, a in metrics["arms"].items():
        for cell in a["calibration_support"]:
            report.append(f'| {arm} | {cell["temperature"]} | {cell["layer"]} | {cell["calibration_tasks"]} | {cell["increments"]} | {cell["available"]} |')
    report.extend(["", "## Сохранённые пилоты", ""])
    for name, old in read_json(preflight)["metrics"]["historical"].items():
        report.append(f'{name}: {old["attempts"]} ответов, категории {old["categories"]}. Пересчитано без изменения исходных меток.')
        for temp in old["temperatures"]:
            e = temp["evaluation"]
            success = sum(v[0] for v in e["counts"].values())
            report.append(f'- Evaluation T={temp["temperature"]}: {display(success, e["attempts"])}; оценка {e["rate_fit"]["status"]}.')
    report.extend(["", "## Что это позволяет заключить", "",
        "Технический допуск означает пригодность формата и извлечения активаций. Он не означает достаточного числа успешных независимых задач и не подтверждает P5.",
        "Нулевая успешность на маленькой выборке не доказывает бесконечную истинную интенсивность ошибки. Граничная оценка описывает только максимум данного правдоподобия.",
        "Из зависимости от длины оценивается только произведение c=θ·F̄(τ). Для θ, τ и различения хвостовых механизмов нужны отдельные данные и проверки.",
        "Форматные ошибки и обрывы оставлены в знаменателе; они мешают трактовать сырую кривую как чистый закон ошибок вывода.",
        "Формальная значимость и доверительные интервалы по этому пилоту не заявляются. Парные таблицы по ролям и температурам сохранены в metrics.json.", "",
        "## Следующий шаг", "",
    ])
    guided = metrics["arms"]["guided"]
    if guided["gate"]["passed"]:
        report.append("Зафиксировать guided как отдельный протокол сбора для дальнейшей разработки. Перед большой серией проверить число независимых успешных calibration-задач по температурам и длинам; подготовить размер calibration/evaluation по этим требованиям. Контроль без грамматики сохранить.")
        if not guided["verified"]:
            report.append("Успешных цепочек в guided нет: сначала требуется улучшение способности решать задачи, иначе хвостовой анализ подтверждённых траекторий остаётся невозможен.")
    else:
        report.append("Большую серию не запускать: разобрать причину технического отказа guided по gate-attempt.json и extraction, затем повторить только отдельный технический пилот.")
    report.append("Автоматический запуск большой серии отключён; основной эксперимент продолжает свой прежний процесс.")
    report_path = OUT / "REPORT.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    finish(OUT, stage="P5-repair-descriptive-paired-review",
           context={"source": digest(SOURCE)}, inputs=inputs,
           outputs=[out_metrics, report_path], metrics=metrics)
    print(report_path, flush=True)


if __name__ == "__main__":
    main()
