"""Audit all fresh point fits, render all prespecified comparisons, package evidence."""
from __future__ import annotations
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import os
import shutil
import sys
import zipfile
import numpy as np
from scipy import stats

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
METHOD = BASE/"audit/revision_2026_09_13/p3_constrained_v1"
sys.path.insert(0,str(METHOD/"code"))
from candidate import constrained_gpd_fit
from onebigjump.e1.analysis import finite_json
from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.stages import rows
from onebigjump.readiness.p3_diagnosis import draw_sample
from onebigjump.readiness.p3_validation import thresholds

HERE = Path(__file__).resolve().parent
ROOT = BASE/"runs/p3_constrained_validation_20260913"
OUT = BASE/"audit/revision_2026_09_13/reviews/p3-constrained-validation-v1"
SOURCE = Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"


def point_audit(task):
    config, record = task
    request = record["request"]
    setting = config["scenarios"][request["scenario"]]
    cal, fail, _ = draw_sample(request["seed"],setting["shape"],setting["failure_quantile"],tasks=config["tasks"])
    results = []
    previous_threshold, cached = None, None
    for name, threshold in thresholds(cal,fail,config["q"]).items():
        excess = fail[fail>threshold]-threshold
        saved = record["point_fit_diagnostics"]["constrained"][name]
        if excess.size<5:
            matches = saved["shape_estimate"] is None
            fresh = None
        else:
            if previous_threshold != threshold:
                cached = constrained_gpd_fit(excess,grid_size=2049)
                previous_threshold = threshold
            fresh = cached
            matches = (
                saved["converged"] == fresh.converged and
                abs(saved["gamma"]-fresh.gamma)<1e-6 and
                np.isclose(saved["sigma"],fresh.sigma,rtol=1e-6) and
                abs(saved["loglik"]-fresh.loglik)<1e-5
            )
        results.append({
            "trace_id":record["trace_id"],"threshold_method":name,
            "matches_dense_grid":bool(matches),
            "saved":saved,"dense":fresh.as_dict() if fresh is not None else None,
        })
    return finite_json(results)


def fraction_text(value):
    if not value["datasets"]:
        return "недоступно"
    return f"{value['successes']}/{value['datasets']} ({100*value['fraction']:.1f}%)"


def main():
    verify_manifest(ROOT/"manifest.json")
    verify_manifest(METHOD/"preflight/manifest.json")
    config = read_json(METHOD/"protocol.json")
    metrics = read_json(ROOT/"metrics.json")
    records = rows(ROOT/"replicates.jsonl")
    preflight = read_json(METHOD/"preflight/metrics.json")
    OUT.mkdir(parents=True,exist_ok=False)
    with ProcessPoolExecutor(max_workers=8) as pool:
        audited = [cell for result in pool.map(point_audit,[(config,r) for r in records]) for cell in result]
    mismatches = [r for r in audited if not r["matches_dense_grid"]]
    availability_reasons = {}
    for scenario in config["scenarios"]:
        for estimator in config["estimators"]:
            for threshold in config["thresholds"]:
                reasons = Counter()
                for r in records:
                    if r["request"]["scenario"] != scenario:
                        continue
                    c = r["methods"][estimator][threshold]
                    if c["percentile"]["ci95"] is not None:
                        continue
                    why = []
                    for key,minimum in [("calibration_tail_tasks",10),("calibration_excesses",20),
                                        ("failure_tail_tasks",20),("failure_excesses",50)]:
                        if c[key]<minimum:
                            why.append(key+"_insufficient")
                    if c["percentile"]["n_tasks"]<config["statistics"]["min_tasks"]:
                        why.append("too_few_independent_tasks")
                    if c["percentile"]["valid"]/config["statistics"]["bootstrap"]<config["statistics"]["valid_fraction"]:
                        why.append("too_few_finite_bootstrap_fits")
                    if estimator=="constrained" and c["point"] is None:
                        why.append("original_point_unusable")
                    if not why:
                        why.append("unexplained")
                    reasons[";".join(why)] += 1
                availability_reasons[scenario+"/"+estimator+"/"+threshold] = dict(reasons)
    assert all("unexplained" not in item for item in availability_reasons.values())
    # Family-adjusted Monte Carlo diagnostic for the single prespecified primary
    # candidate over four scenarios; broader cellwise MC95 intervals remain descriptive.
    family_diagnostics = {}
    for scenario,item in metrics["scenarios"].items():
        coverage = item["cells"][config["primary_candidate_for_decision"]]["coverage_conditional"]
        n,k = coverage["datasets"],coverage["successes"]
        tail = .05/(2*len(config["scenarios"]))
        bounds = [
            float(stats.beta.ppf(tail,k,n-k+1)) if k else 0.,
            float(stats.beta.ppf(1-tail,k+1,n-k)) if k<n else 1.,
        ] if n else None
        family_diagnostics[scenario] = {
            "mc_family_95_bounds":bounds,
            "undercoverage_detected":bounds is not None and bounds[1]<.95,
            "interpretation":"Bonferroni across four scenarios for frozen primary candidate",
        }
    report_metrics = finite_json({
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "validation":metrics,"preflight":preflight,
        "fresh_point_checks":len(audited),"fresh_point_mismatches":len(mismatches),
        "availability_reason_sets":availability_reasons,
        "primary_family_monte_carlo":family_diagnostics,
        "primary_method_changed":False,
        "decision":"do_not_promote_primary_method",
        "decision_reason":"numerical agreement is not sufficient evidence of interval calibration",
    })
    p = write_once(OUT/"metrics.json",report_metrics)
    a = write_once(OUT/"fresh-point-audit.json",audited)
    # Data-derived plot for the prespecified primary threshold/percentile comparison.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    scenarios = list(config["scenarios"])
    fig, axes = plt.subplots(1,2,figsize=(12,4.6),layout="constrained")
    for column, (measure,title) in enumerate([
        ("availability","Interval availability"),
        ("coverage_conditional","Coverage among available intervals"),
    ]):
        ax = axes[column]
        for offset,estimator,color in [(-.12,"legacy","#9b5960"),(.12,"constrained","#167d8d")]:
            cells = [metrics["scenarios"][s]["cells"][estimator+"/original/percentile"][measure] for s in scenarios]
            y = np.array([c["fraction"] for c in cells])
            low = np.array([c["monte_carlo_ci95"][0] for c in cells])
            high = np.array([c["monte_carlo_ci95"][1] for c in cells])
            ax.errorbar(np.arange(len(scenarios))+offset,y,
                        yerr=np.array([y-low,high-y]),fmt="o",capsize=3,label=estimator,color=color)
        ax.set_xticks(np.arange(len(scenarios)),["Heavy\noriginal support","Heavy\nlower support","Exponential","Bounded"])
        ax.set_title(title)
        ax.set_ylim(.45,1.025)
        ax.grid(axis="y",alpha=.25)
        ax.legend()
    axes[1].axhline(.95,color="#555555",linestyle="--",linewidth=1)
    fig.suptitle("P3: independent paired validation at q=0.01; bars are Monte Carlo 95% intervals")
    png,pdf = OUT/"coverage-availability.png",OUT/"coverage-availability.pdf"
    fig.savefig(png,dpi=180)
    fig.savefig(pdf)
    plt.close(fig)

    lines = [
        "# P3: отдельный оцениватель и независимая валидация",
        "",
        "Результат получен на Жоресе. Основной производственный оцениватель и метки доказательств не изменялись.",
        "",
        "## Что изменено",
        "",
        "Отдельная реализация ищет внутренние стационарные решения GPD с gamma > −1 и сравнивает их правдоподобие с граничным равномерным случаем gamma = −1, sigma = max(excesses). Если выигрывает граница, сохраняется явный отказ; отрицательные внутренние оценки не обрезаются.",
        "Основание: [Grimshaw (1993), разделы 2.1–2.2](https://www.stat.cmu.edu/technometrics/90-00/vol-35-02/v3502185.pdf). В обозначениях статьи k = −gamma. Использованы численный поиск корней и аналитическая формула около нуля; это собственная реализация, а не дословно перенесённый алгоритм автора.",
        "",
        "## Проверка реализации",
        "",
        f"До новых данных пройдены {preflight['cases']} численных случаев: опубликованный пример, фиксированные распределения, граничные случаи и сохранённые сбои. Проверены независимая двумерная оптимизация, четырёхкратное сгущение сетки, изменение масштаба и перестановка наблюдений.",
        f"После фиксации результата дополнительно проверены все {len(audited)} новые точечные оценки на плотной сетке. Несовпадений: {len(mismatches)}. Это дополнительный численный аудит, не замена сохранённых оценок.",
        "Граница gamma = −1 остаётся непригодной для обычного интервала. Допустимость внутренней оценки gamma > −1 сама по себе не гарантирует асимптотическую нормальность или корректность bootstrap.",
        "",
        "## Независимый протокол",
        "",
        f"Код и протокол зафиксированы до генерации новых данных: {metrics['method_freeze_sha256']}. Проведено {metrics['datasets']} наборов, по {config['datasets']} на сценарий, {config['tasks']} независимых задач и {config['statistics']['bootstrap']} bootstrap-повторов. Seed исходных наборов не пересекаются с прежней валидацией.",
        "В каждой паре методы используют одинаковые задачи, пороги и индексы ресэмплинга. Порог переоценивается в каждом повторе; известная истинная граница поддержки используется только генератором и для диагностики. Сохранены оба определения порога и оба типа интервала.",
        "Основное заранее выбранное сравнение: constrained / original threshold / percentile. Проверка ограничена q = 0.01; для q = 0.001 калибровка этим запуском не установлена.",
        "",
        "## Основное сравнение",
        "",
        "| Сценарий | Метод | Доступно | Покрытие среди доступных | Покрытие с недоступными как неуспех | MC95 для условного покрытия |",
        "|---|---|---:|---:|---:|---|",
    ]
    for scenario in scenarios:
        for estimator in config["estimators"]:
            c = metrics["scenarios"][scenario]["cells"][estimator+"/original/percentile"]
            bounds = c["coverage_conditional"]["monte_carlo_ci95"]
            interval = f"[{bounds[0]:.3f}, {bounds[1]:.3f}]" if bounds else "недоступно"
            lines.append(f"| {scenario} | {estimator} | {fraction_text(c['availability'])} | {fraction_text(c['coverage_conditional'])} | {fraction_text(c['coverage_counting_unavailable_as_failure'])} | {interval} |")
    lines += ["","![Доступность и покрытие](coverage-availability.png)","",
              "Полосы на графике — интервалы Монте-Карло для вероятностей, а не интервалы параметра gamma. Пары используют общие данные; нельзя считать методы независимыми выборками.",
              "","## Парные изменения","","| Сценарий | Доступно обоим | Покрыто: старый / новый | Новых интервалов | Потеряно интервалов | Исправленных / испорченных покрытий на общей части |",
              "|---|---:|---:|---:|---:|---:|"]
    for scenario in scenarios:
        c = metrics["scenarios"][scenario]["paired"]["original/percentile"]
        lines.append(f"| {scenario} | {c['common_available']} | {c['legacy_covered_common']} / {c['candidate_covered_common']} | {c['gained_intervals']} | {c['lost_intervals']} | {c['coverage_gains_common']} / {c['coverage_losses_common']} |")
    lines += ["","## Вывод и решение",""]
    detected = [s for s,v in family_diagnostics.items() if v["undercoverage_detected"]]
    if mismatches:
        lines.append("Обнаружены численные несовпадения. Продвижение кандидата запрещено до объяснения; исходные результаты сохранены.")
    if detected:
        lines.append("Даже после поправки Монте-Карло на четыре сценария недопокрытие основного кандидата выявлено в: " + ", ".join(detected) + ".")
        lines.append("Численная проблема и калибровка интервалов — разные вопросы: прохождение численных тестов не устранило всё статистическое смещение.")
    else:
        lines.append("При поправке Монте-Карло на четыре сценария недопокрытие основного кандидата не выявлено. Это не доказывает калибровку: точность ограничена числом независимых наборов.")
    lines += [
        "Основной метод не заменяем. Кандидат остаётся отдельно проверенной экспериментальной реализацией; никакой выбор лучшей комбинации по этим данным не переносится в основной анализ.",
        "Дальше: завершить основную серию и предусмотренные контроли; P3-интервалы трактовать как описательные до подтверждения калибровки. Если продолжать методическую работу, отдельно зафиксировать модель отбора превышений/порог и проверить её на следующей независимой выборке. Новую гипотезу нельзя подтверждать теми же данными, по которым она предложена.",
        "",
        "## Все заранее заданные комбинации",
        "",
        "| Сценарий | Оцениватель / порог / интервал | Доступно | Условное покрытие | Средняя ширина | Смещение доступной точки |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for scenario in scenarios:
        for name,c in metrics["scenarios"][scenario]["cells"].items():
            width = c["mean_ci_width"]
            bias = c["mean_point_bias_when_point_available"]
            lines.append(f"| {scenario} | {name} | {fraction_text(c['availability'])} | {fraction_text(c['coverage_conditional'])} | {width if width is not None else 'NA'} | {bias if bias is not None else 'NA'} |")
    lines += [
        "",
        "metrics.json также содержит причины недоступности, число отказов каждого оптимизатора, положение пропущенных интервалов относительно истины и частоту ложного положительного семейного вывода на нулевых сценариях.",
        "Сводный отказ нового метода на границе не подменяется gamma = 0 или успешной отрицательной оценкой. bootstrap-draws/*.npz сохраняют все точечные значения повторов, сырые gamma, пороги и причины отказа.",
        "",
        "Архив включает код кандидата и запуска, протокол, фиксацию файлов, предварительные проверки, новые результаты, массивы bootstrap и исходный снимок кода. Для другого GPT: проверьте сравнение с равномерной границей, парность bootstrap, правила доступности и вывод о калибровке, а затем сопоставьте с substantive-review-v2 и предыдущим P3_AND_MAIN_UPDATE.",
    ]
    report = OUT/"REPORT.md"
    report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    finish(OUT,stage="constrained-gpd-complete-review",
        context={"source":digest(SOURCE)},
        inputs=[SOURCE,ROOT/"manifest.json",METHOD/"preflight/manifest.json",METHOD/"method-freeze.json",
                Path(__file__),HERE/"protocol.json",HERE/"run.sbatch"],
        outputs=[p,a,report,png,pdf],
        metrics={"fresh_point_checks":len(audited),"mismatches":len(mismatches),"primary_changed":False})
    files = {}
    def add_directory(path,prefix):
        for child in sorted(path.rglob("*")):
            if child.is_file() and not child.is_symlink() and child.suffix!=".log":
                files[prefix+"/"+str(child.relative_to(path))] = child
    add_directory(OUT,"review")
    add_directory(ROOT,"validation")
    add_directory(METHOD,"method")
    add_directory(HERE,"review-code")
    source_manifest = read_json(SOURCE)
    files["source/source-manifest.json"] = SOURCE
    for filename in source_manifest["outputs"]:
        original = Path(filename)
        files["source/"+str(original.relative_to(SOURCE.parent))] = original
    index = {name:{"sha256":digest(path),"server_path":str(path),"bytes":path.stat().st_size} for name,path in files.items()}
    archive = BASE/"audit/revision_2026_09_13/review-packages/p3-constrained-validation-v1.zip"
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as z:
        for name,path in files.items():
            z.write(path,name)
        z.writestr("bundle-index.json",json.dumps(index,sort_keys=True,indent=2)+"\n")
    write_once(archive.with_suffix(".json"),{
        "archive_sha256":digest(archive),"files":len(index),"bytes":archive.stat().st_size,
        "report_manifest_sha256":digest(OUT/"manifest.json"),
    })
    assert not mismatches, mismatches
    print("CONSTRAINED_GPD_REVIEW_COMPLETE",archive,flush=True)


if __name__=="__main__":
    main()
