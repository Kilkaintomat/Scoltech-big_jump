"""Separate P5 development runner; no writes to any protected experiment."""

import argparse
from pathlib import Path

from onebigjump.experiments.p5_rate import diagnose_records

from onebigjump.e1.artifacts import digest, finish, identity, read_json, verify_manifest, write_once
from onebigjump.e1.stages import rows
from onebigjump.readiness import deduction

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/p5_repair_20260914_v2"
RUNS = BASE / "runs/p5_repair_20260914_v2"
SOURCE = HERE / "source/source-manifest.json"


def records_for(root):
    found, manifests = deduction.samples(root, "pilot")
    lm = root / "pilot/verification/manifest.json"
    verify_manifest(lm)
    labels = {r["trace_id"]: r for r in rows(lm.parent / "labels.jsonl")}
    if set(labels) != {s["trace_id"] for s in found}:
        raise ValueError("generation/verification population mismatch")
    result = []
    for sample in found:
        label = labels[sample["trace_id"]]
        if label["request_sha256"] != identity(sample):
            raise ValueError("verification request identity mismatch")
        p = sample["problem"]
        result.append(
            {
                "trace_id": sample["trace_id"],
                "problem_id": p["problem_id"],
                "role": p["role"],
                "length": p["length"],
                "temperature": sample["temperature"],
                "verified": label["verified"],
                "format_eligible": label["format_eligible"],
                "category": label["category"],
            }
        )
    return result, [lm, *manifests]


def rate_analysis(root, out):
    records, inputs = records_for(root)
    metrics = diagnose_records(records)
    out.mkdir(parents=True, exist_ok=True)
    metric = write_once(out / "metrics.json", metrics)
    report = [
        "# P5: зависимость успеха от назначенной длины",
        "",
        "Оценка интенсивности ошибок отделена от подгонки GPD. Все назначенные попытки остаются в знаменателе.",
        "",
        "| Температура | Роль | Попыток | Задач | Формат | Статус оценки | c |",
        "|---|---|---:|---:|---:|---|---:|",
    ]
    for t in metrics["temperatures"]:
        for role in ("calibration", "evaluation"):
            s = t[role]
            fit = s["rate_fit"]
            value = (
                "не определено"
                if fit is None
                else "∞"
                if fit["rate_is_infinite"]
                else str(fit["rate_per_step"])
            )
            report.append(
                f"| {t['temperature']} | {role} | {s['attempts']} | {s['tasks']} | {s['format_fraction']:.1%} | {fit['status'] if fit else 'insufficient_lengths'} | {value} |"
            )
    report.extend(
        [
            "",
            "Нулевой успех на всех длинах даёт граничную оценку c=∞; это не численная ошибка и не оценка параметров хвоста.",
            "Предсказания на evaluation рассчитаны из calibration; loglik, Brier и исходные счётчики сохранены в metrics.json.",
            "Значимость, доверительные интервалы, θ и τ здесь не заявляются. Форматные потери препятствуют интерпретации как чистого закона ошибок вывода.",
        ]
    )
    report_file = out / "REPORT.md"
    report_file.write_text("\n".join(report) + "\n", encoding="utf-8")
    finish(
        out,
        stage="P5-rate-only-development",
        context={"source": digest(SOURCE)},
        inputs=[SOURCE, Path(__file__), *inputs],
        outputs=[metric, report_file],
        metrics={
            "attempts": len(records),
            "decision": "inconclusive",
            "rate_estimation_decoupled_from_GPD": True,
        },
    )
    return metrics


def gate_attempt(root):
    try:
        deduction.gate(root, SOURCE)
        result = {"passed": True, "reason": "original acquisition gate passed"}
    except ValueError as exc:
        if not str(exc).startswith("synthetic technical pilot failed:"):
            raise
        result = {"passed": False, "reason": str(exc)}
    write_once(root / "pilot/gate-attempt.json", result)
    return result


def summarize():
    out = RUNS / "summary"
    out.mkdir()
    arms = {}
    inputs = [SOURCE, HERE / "study-protocol.json"]
    for arm in ("unguided", "guided"):
        root = RUNS / arm
        m = root / "pilot/analysis/manifest.json"
        verify_manifest(m)
        inputs.extend([m, root / "pilot/gate-attempt.json"])
        inputs.extend(
            root / "pilot" / stage / "manifest.json"
            for stage in ("verification", "extraction", "measurement")
        )
        if (root / "pilot/gate/manifest.json").exists():
            inputs.append(root / "pilot/gate/manifest.json")
        arms[arm] = {
            "rate_diagnostics": read_json(m.parent / "metrics.json"),
            "technical_gate": read_json(root / "pilot/gate-attempt.json"),
        }
    metrics = {
        "arms": arms,
        "new_attempts": sum(a["rate_diagnostics"]["attempts"] for a in arms.values()),
        "allow_main": False,
        "scientific_decision": "inconclusive",
        "interpretation": "paired task-level acquisition pilot; grammar restricts syntax only; no verifier feedback during generation",
        "main_jobs_changed": False,
    }
    path = write_once(out / "metrics.json", metrics)
    report = [
        "# Отдельный пилот исправления P5",
        "",
        "| Вариант | Попыток | Категории | Исход технического допуска |",
        "|---|---:|---|---|",
    ]
    for arm, a in arms.items():
        d = a["rate_diagnostics"]
        report.append(
            f"| {arm} | {d['attempts']} | {d['categories']} | {a['technical_gate']['passed']} |"
        )
    report.extend(
        [
            "",
            "Грамматика фиксирует только синтаксис и число строк, не правила вывода и не правильную цепочку.",
            "Большая серия автоматически не запускается. Даже пройденный технический допуск не подтверждает P5.",
            "Оба варианта используют одни задачи, запросы и начальные seed; это не обещание побитового совпадения случайных выборок после разных масок.",
        ]
    )
    report_file = out / "REPORT.md"
    report_file.write_text("\n".join(report) + "\n", encoding="utf-8")
    finish(
        out,
        stage="paired-syntax-only-P5-pilot",
        context={"source": digest(SOURCE)},
        inputs=inputs,
        outputs=[path, report_file],
        metrics=metrics,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    parser.add_argument("arm", nargs="?")
    args = parser.parse_args()
    if args.stage == "summary":
        summarize()
        return
    root = RUNS / args.arm
    if args.stage == "population":
        deduction.population(root, SOURCE)
    elif args.stage == "generate":
        deduction.generate(root, "pilot", SOURCE, 0, 1)
    elif args.stage == "verify":
        deduction.verify(root, "pilot", SOURCE)
    elif args.stage == "extract":
        deduction.extract(root, "pilot", SOURCE)
    elif args.stage == "measure":
        deduction.measure(root, "pilot", SOURCE)
    elif args.stage == "analyze":
        rate_analysis(root, root / "pilot/analysis")
    elif args.stage == "gate":
        print(gate_attempt(root), flush=True)
    else:
        raise ValueError("unknown stage")


if __name__ == "__main__":
    main()
