"""Recompute audit evidence without changing any archived experiment or paper artifact."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from onebigjump.config import KestenConfig
from onebigjump.manifests import run_manifest
from onebigjump.reproducibility import file_digest, write_json
from onebigjump.simulation.kesten import simulate
from onebigjump.stats import hill, moment
from onebigjump.stats.gpd import gpd_from_order_statistics
from onebigjump.stats.thresholds import select_k


def inventory(root: Path) -> dict:
    records = []
    manifests = []
    for directory in ("results", "data", "paper_outputs"):
        for path in sorted((root / directory).rglob("manifest*.json")):
            manifest = json.loads(path.read_text())
            manifests.append({
                "path": str(path.relative_to(root)), "name": manifest.get("name"),
                "git": manifest.get("environment", {}).get("git", {}),
                "status": manifest.get("status"), "digest": file_digest(path),
            })
            for record in manifest.get("outputs", []):
                stored = Path(record["path"])
                # Historical manifests use both absolute local/cluster paths and relative paths.
                if stored.is_absolute():
                    parts = stored.parts
                    starts = [i for i, x in enumerate(parts) if x in {"results", "data", "paper_outputs"}]
                    local = root.joinpath(*parts[starts[0]:]) if starts else root / "__unresolved__"
                else:
                    local = root / stored
                digest = file_digest(local)
                status = "missing" if digest is None else "match" if digest == record.get("digest") else "changed"
                records.append({
                    "manifest": str(path.relative_to(root)), "path": str(stored),
                    "expected": record.get("digest"), "actual": digest, "status": status,
                })
    samples_path = root / "data/raw/prover-sampling/samples.jsonl"
    samples = [json.loads(line) for line in samples_path.read_text().splitlines()] if samples_path.exists() else []
    return {
        "manifests": manifests, "outputs": records,
        "digest_counts": dict(Counter(r["status"] for r in records)),
        "sampling": {
            "n_samples": len(samples), "n_problems": len({s["problem_id"] for s in samples}),
            "temperatures": sorted({s["temperature"] for s in samples}),
            "with_exact_ids": sum(bool(s.get("prompt_token_ids") and s.get("completion_token_ids")) for s in samples),
            "with_raw_completion": sum(bool(s.get("completion")) for s in samples),
            "with_expected_statement": sum(bool(s.get("theorem_statement")) for s in samples),
            "digest": file_digest(samples_path),
        },
        "activation_tables": [str(p.relative_to(root)) for p in (root / "results").rglob("deviations.parquet")],
        "lean_trace_files": [str(p.relative_to(root)) for p in (root / "results").rglob("traces*.jsonl")],
    }


def p4_archive(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "results/full").glob("grokking*/p4_grokking*.json")):
        payload = json.loads(path.read_text())
        cps = payload["checkpoints"]
        gamma = np.array([c["moment"] for c in cps])
        xi = np.maximum(gamma, 0)
        h = np.array([c["hill"] for c in cps])
        steps = np.array([c["step"] for c in cps])
        test = np.array([c["test_acc"] for c in cps])
        grok = np.flatnonzero(test >= .9)
        i = int(grok[0]) if grok.size else None
        rows.append({
            "run": path.parent.name, "seed": payload["seed"],
            "input": str(path.relative_to(root)), "input_digest": file_digest(path),
            "n_checkpoints": len(cps), "grokking_step": int(steps[i]) if i is not None else None,
            "final_test_accuracy": float(test[-1]),
            "xi_positive_fraction": float(np.mean(xi > 0)), "xi_max": float(np.max(xi)),
            "moment_first": float(gamma[0]), "moment_last": float(gamma[-1]),
            "hill_first": float(h[0]), "hill_last": float(h[-1]),
            "rho_step_hill": float(spearmanr(steps, h).statistic),
            "rho_step_xi": float(spearmanr(steps, xi).statistic) if np.ptp(xi) > 0 else None,
            "moment_before_transition": float(np.mean(gamma[max(i-3, 0):i])) if i else None,
            "moment_after_transition": float(np.mean(gamma[i+1:i+4])) if i is not None and i+1<len(cps) else None,
            "progress_losses": "legacy; cannot reconstruct corrected Fourier losses from scalar checkpoints",
        })
    return rows


def kesten_diagnostics() -> list[dict]:
    cfg = KestenConfig(p_values=[0., .02, .05, .1])
    rows = []
    for p in cfg.p_values:
        tr = simulate(p, cfg)
        z = tr.z.ravel()
        selected = select_k(z, resamples=cfg.tail.double_bootstrap_resamples, seed=cfg.seed)
        fractions = [.005, .01, .02, .05, .1]
        grid = []
        for k in sorted({selected.k, *(round(f * len(z)) for f in fractions)}):
            grid.append({"k": k, "fraction": k / len(z), "hill": hill(z, k),
                         "moment": moment(z, k), "gpd": gpd_from_order_statistics(z, k).gamma})
        tau = tr.tolerance(cfg.tolerance_quantile)
        stars = tr.first_exceedance(tau)
        refuted = stars >= 0
        rows.append({
            "p": p, "alpha_theory": tr.alpha_theory, "xi_theory": tr.xi_theory,
            "selected_k": selected.as_dict(), "grid": grid,
            "n_refuted": int(refuted.sum()),
            "top1": float(np.mean(tr.argmax_step()[refuted] == stars[refuted])),
            "config": cfg.model_dump(mode="json"),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with run_manifest("revision-diagnostics", "audit", args.out, seed=20270101,
                      config={"archive": str(args.archive), "script_digest": file_digest(Path(__file__))}) as man:
        man.note("Exploratory code audit, not a preregistered paper experiment. Archived files remain untouched.")
        result = {"inventory": inventory(args.archive), "p4_recomputed": p4_archive(args.archive),
                  "kesten": kesten_diagnostics()}
        path = man.add_output(write_json(args.out / "diagnostics.json", result), "audit-metrics")
        lines = ["# Измерения для ревизии", "", "Сгенерировано scripts/revision_diagnostics.py из архивных файлов и диагностического запуска.", "",
                 "## Контрольные суммы", "", "```json", json.dumps(result["inventory"]["digest_counts"], indent=2), "```", "",
                 "## Архив P4", "", "| Прогон | seed | Шаг grokking | Accuracy в конце | Доля xi > 0 | rho(step, Hill) |",
                 "|---|---|---|---|---|---|"]
        for row in result["p4_recomputed"]:
            lines.append(f"| {row['run']} | {row['seed']} | {row['grokking_step']} | {row['final_test_accuracy']:.4f} | {row['xi_positive_fraction']:.4f} | {row['rho_step_hill']:.4f} |")
        lines += ["", "## Kesten: выбор k и чувствительность", "",
                  "| p | Теория xi | k | Hill | Moment | GPD |", "|---|---|---|---|---|---|"]
        for row in result["kesten"]:
            for point in row["grid"]:
                lines.append(f"| {row['p']} | {row['xi_theory']:.4f} | {point['k']} | {point['hill']:.4f} | {point['moment']:.4f} | {point['gpd']:.4f} |")
        summary = args.out / "MEASUREMENTS.md"
        summary.write_text("\n".join(lines) + "\n")
        man.add_output(summary, "audit-report")
        print(path)


if __name__ == "__main__":
    main()
