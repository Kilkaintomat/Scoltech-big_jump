"""Replay fixed existing P3 draws with GPD diagnostics; never modify the estimator."""
from __future__ import annotations

import gzip
import json
import math
import os
import platform
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from importlib.metadata import version
from pathlib import Path

import numpy as np

from onebigjump.e1.analysis import finite_json
from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.stages import rows
from onebigjump.readiness import p3_validation
from onebigjump.readiness.p3_diagnosis import draw_sample
from onebigjump.stats.gpd import _profile_nll, gpd_fit

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = Path(__file__).resolve().parent
ROOT = BASE / "runs/p3_validation_20260913"
OUT = BASE / "runs/p3_fit_diagnostics_20260913"
SOURCE = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"


def worker(task):
    config, archived = task
    request = archived["request"]
    settings = config["scenarios"][request["scenario"]]
    cal, fail, cutoff = draw_sample(
        request["seed"], settings["shape"], settings["failure_quantile"],
        tasks=config["tasks"],
    )
    records = []
    example_counts = Counter()
    examples = []
    methods = ["original", "observed_support"]
    original_shape_at = p3_validation.shape_at

    def instrumented_shape_at(failures, threshold):
        call = len(records)
        phase = "point" if call < 2 else "bootstrap"
        b = None if call < 2 else (call - 2) // 2
        method = methods[call % 2]
        excess = failures[failures > threshold] - threshold
        fit = None
        reason = "success"
        value = float("nan")
        if excess.size < 5:
            reason = "fewer_than_5_excesses"
        else:
            try:
                fit = gpd_fit(excess, threshold=threshold)
                value = fit.shape_estimate
                if not np.isfinite(value):
                    reason = fit.message or "nonfinite_shape_without_message"
            except (ValueError, FloatingPointError, OverflowError) as error:
                reason = type(error).__name__ + ": " + str(error)
        largest = float(excess.max()) if excess.size else None
        r = {
            "trace_id": archived["trace_id"],
            "scenario": request["scenario"],
            "method": method,
            "phase": phase,
            "bootstrap_index": b,
            "threshold": float(threshold),
            "n_excesses": int(excess.size),
            "n_unique": int(np.unique(excess).size),
            "max_multiplicity": int((excess == largest).sum()) if excess.size else 0,
            "usable": bool(np.isfinite(value)),
            "reason": reason,
            "fit": fit.as_dict() if fit is not None else None,
        }
        records.append(finite_json(r))
        key = (method, reason)
        if phase == "bootstrap" and not r["usable"] and example_counts[key] < 3:
            example_counts[key] += 1
            examples.append({**finite_json(r), "excesses": excess.tolist()})
        return value

    p3_validation.shape_at = instrumented_shape_at
    try:
        replay = p3_validation.evaluate(cal, fail, config, request["seed"] + 10000000)
    finally:
        p3_validation.shape_at = original_shape_at
    assert len(records) == 2 + 2 * config["statistics"]["bootstrap"]
    mismatch = replay != archived["methods"] or cutoff != archived["true_support_diagnostic_only"]
    return {
        "trace_id": archived["trace_id"],
        "request": request,
        "archived": archived["methods"],
        "replayed": replay,
        "exact_match": not mismatch,
        "records": records,
        "examples": examples,
    }


def profile_example(example, epsilons):
    y_raw = np.asarray(example["excesses"], dtype=float)
    if y_raw.size < 5:
        return example
    unit = float(np.median(y_raw))
    y = y_raw / unit
    diagnostics = []
    for epsilon in epsilons:
        lower = -1.0 / float(y.max()) + epsilon
        grid = np.concatenate([
            np.linspace(lower, -1e-8, 300),
            np.array([0.0]),
            np.geomspace(1e-8, 64.0, 400),
        ])
        values = np.array([_profile_nll(float(t), y) for t in grid])
        best = int(np.argmin(values))
        interior = []
        for i in range(1, len(grid) - 1):
            if values[i] <= values[i - 1] and values[i] <= values[i + 1]:
                theta = float(grid[i])
                gamma = 0.0 if abs(theta) < 1e-10 else float(np.log1p(theta * y).mean())
                if math.isfinite(float(values[i])) and gamma > -1:
                    interior.append({
                        "grid_index": i, "theta": theta, "gamma": gamma,
                        "profile_nll_normalized": float(values[i]),
                    })
        theta = float(grid[best])
        diagnostics.append({
            "support_epsilon": epsilon,
            "grid_winner_index": best,
            "grid_winner_gamma": 0.0 if abs(theta) < 1e-10 else float(np.log1p(theta * y).mean()),
            "grid_winner_profile_nll_normalized": float(values[best]),
            "left_endpoint_profile_nll_normalized": float(values[0]),
            "interior_grid_local_minima_gamma_above_minus_one": interior,
        })
    return finite_json({
        **example,
        "profile_grid_diagnostics": diagnostics,
        "profile_scope": "diagnostic grid only; no replacement estimate or confidence interval",
    })


def summarize_record(summary, record):
    key = record["scenario"] + "/" + record["method"]
    entry = summary.setdefault(key, {
        "point": Counter(), "bootstrap": Counter(),
        "bootstrap_ties_by_outcome": {},
        "bootstrap_excess_counts_by_outcome": {},
        "bootstrap_gamma_range_by_reason": {},
    })
    entry[record["phase"]][record["reason"]] += 1
    if record["phase"] != "bootstrap":
        return
    outcome = "usable" if record["usable"] else "unusable"
    ties = entry["bootstrap_ties_by_outcome"].setdefault(outcome, Counter())
    ties[str(record["max_multiplicity"])] += 1
    counts = entry["bootstrap_excess_counts_by_outcome"].setdefault(outcome, Counter())
    counts[str(record["n_excesses"])] += 1
    fit = record["fit"]
    if fit is not None and fit["gamma"] is not None:
        bounds = entry["bootstrap_gamma_range_by_reason"].setdefault(
            record["reason"], [fit["gamma"], fit["gamma"]]
        )
        bounds[0] = min(bounds[0], fit["gamma"])
        bounds[1] = max(bounds[1], fit["gamma"])


def main():
    protocol_path = HERE.parent / "protocol.json"
    protocol = read_json(protocol_path)
    config = read_json(ROOT / "protocol.json")
    archived_manifest = ROOT / "shard-00/manifest.json"
    verify_manifest(archived_manifest)
    verify_manifest(SOURCE)
    archive_meta = read_json(archived_manifest)
    old_source = next(
        Path(p) for p in archive_meta["inputs"] if p.endswith("source-manifest.json")
    )
    code_comparison = {}
    for relative in protocol["source_files_required_identical"]:
        old = old_source.parent / relative
        new = SOURCE.parent / relative
        code_comparison[relative] = {"old": digest(old), "current": digest(new)}
        assert code_comparison[relative]["old"] == code_comparison[relative]["current"]
    versions = {name: version(name) for name in ["numpy", "scipy"]}
    assert versions == {
        name: archive_meta["environment"]["packages"][name] for name in versions
    }
    assert platform.python_version() == archive_meta["environment"]["python"]
    selected = [
        r for r in rows(archived_manifest.parent / "replicates.jsonl")
        if r["request"]["index"] in protocol["indices_per_scenario"]
    ]
    selected.sort(key=lambda r: (
        protocol["scenarios"].index(r["request"]["scenario"]), r["request"]["index"]
    ))
    expected = {
        f"{scenario}:{index}" for scenario in protocol["scenarios"]
        for index in protocol["indices_per_scenario"]
    }
    assert len(selected) == len(expected) and {r["trace_id"] for r in selected} == expected
    OUT.mkdir(parents=True, exist_ok=False)
    detail = OUT / "fits.jsonl.gz"
    summary = {}
    dataset_checks = []
    examples = []
    example_counts = Counter()
    with ProcessPoolExecutor(max_workers=protocol["workers"]) as pool, gzip.open(
        detail, "wt", encoding="utf-8"
    ) as stream:
        for result in pool.map(worker, [(config, r) for r in selected]):
            for record in result.pop("records"):
                summarize_record(summary, record)
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            for example in result.pop("examples"):
                key = (example["scenario"], example["method"], example["reason"])
                if example_counts[key] < protocol["examples_per_scenario_method_reason"]:
                    example_counts[key] += 1
                    examples.append(profile_example(example, protocol["profile_support_epsilons"]))
            dataset_checks.append(result)
            print(result["trace_id"], "exact_match", result["exact_match"], flush=True)
    mismatches = [r["trace_id"] for r in dataset_checks if not r["exact_match"]]
    metrics = finite_json({
        "protocol": protocol,
        "datasets": len(dataset_checks),
        "bootstrap_fits": len(dataset_checks) * 2 * config["statistics"]["bootstrap"],
        "point_fits": len(dataset_checks) * 2,
        "exact_replay_mismatches": mismatches,
        "code_identity": code_comparison,
        "python": platform.python_version(),
        "versions": versions,
        "scenarios_methods": summary,
        "diagnostic_examples": len(examples),
        "main_method_changed": False,
        "scope": "first ten existing indices in each scenario, descriptive replay; not a fresh coverage validation",
    })
    metric_path = write_once(OUT / "metrics.json", metrics)
    checks_path = write_once(OUT / "dataset-replay.json", dataset_checks)
    examples_path = write_once(OUT / "examples.json", examples)
    lines = [
        "# P3: причины непригодных оценок GPD",
        "",
        f"Воспроизведены {metrics['datasets']} заранее выбранных наборов: первые десять индексов каждого исходного сценария.",
        f"Повторены {metrics['bootstrap_fits']} bootstrap-оценок и {metrics['point_fits']} точечных оценок. Несовпадений с сохранёнными результатами: {len(mismatches)}.",
        "Проверено полное совпадение исходного кода четырёх статистических модулей, Python, NumPy и SciPy. Порядок ресэмплинга и исходные seed сохранены.",
        "",
        "| Сценарий / порог | Причина результата bootstrap | Число |",
        "|---|---|---:|",
    ]
    for key, entry in summary.items():
        for reason, count in entry["bootstrap"].items():
            lines.append(f"| {key} | {reason} | {count} |")
    lines += [
        "",
        "fits.jsonl.gz сохраняет каждую попытку: исходную gamma, сходимость, сообщение, число превышений, число уникальных значений и кратность максимума.",
        "dataset-replay.json сравнивает все исходные и повторные точечные оценки, интервалы и числа доступных повторов.",
        "examples.json содержит первые зафиксированные неудачные выборки и диагностические профили на нескольких расстояниях от границы поддержки.",
        "",
        "Это разбор механизма на подмножестве прежней валидации. Он не подтверждает покрытие нового метода и не изменяет основной оцениватель.",
        "Связь с повторяющимися максимумами описательная; повторения естественно возникают при bootstrap задач.",
    ]
    report = OUT / "REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    finish(
        OUT, stage="p3-fixed-draw-fit-failure-replay",
        context={"source": digest(SOURCE), "protocol": digest(protocol_path)},
        inputs=[SOURCE, old_source, archived_manifest, ROOT / "protocol.json",
                Path(__file__), protocol_path, HERE.parent / "run.sbatch"],
        outputs=[metric_path, checks_path, examples_path, detail, report],
        metrics=metrics,
    )
    assert not mismatches, mismatches
    print("P3_FIT_DIAGNOSTICS_COMPLETE", OUT, flush=True)


if __name__ == "__main__":
    main()
