"""Run P1-P5 over one deviations table and write the metrics, tables and figures.

This is the command the paper's Section 5 corresponds to: given labelled traces with their step
deviations, produce Table 1, Table 2, the overshoot fits and the length law, with a manifest
recording what produced them.

It runs unchanged on the Kesten surrogate and on Lean traces. That is the point of having one
table schema: the surrogate is where the answers are known in closed form, so a discrepancy there
is a bug in the analysis, and only once it is clean is the same code worth pointing at real data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..config import AnalysisConfig, TailEstimationConfig
from ..logging import get_logger
from ..manifests import run_manifest
from ..reproducibility import write_json
from .p1_tail_separation import run_p1
from .p2_localization import run_p2
from .p3_overshoot import run_p3
from .p5_length_law import run_p5

__all__ = ["run_analysis"]

log = get_logger(__name__)


def run_analysis(
    df: pd.DataFrame,
    cfg: AnalysisConfig | None = None,
    *,
    out_dir: Path | str,
    name: str = "analysis",
    tables_dir: Path | str = "paper_outputs/tables",
    metrics_dir: Path | str = "paper_outputs/metrics",
    figures_dir: Path | str = "paper_outputs/figures",
    tau_override: float | None = None,
    with_hill_plot: bool = False,
) -> dict[str, Any]:
    """Run every prediction the table can support, and say which ones it could not."""
    cfg = cfg or AnalysisConfig()
    tail: TailEstimationConfig = cfg.tail
    out = Path(out_dir)

    with run_manifest(
        name, "analysis", out, config=cfg.model_dump(mode="json"), seed=cfg.seed
    ) as man:
        p1 = run_p1(df, tail, seed=cfg.seed, with_hill_plot=with_hill_plot)
        pooled = {
            (r.model, r.layer, r.statistic): r.estimates.get("refuted_all", {}).get("hill")
            for r in p1
            if r.estimates.get("refuted_all")
        }
        p2 = run_p2(df, permutation_resamples=cfg.permutation_resamples, seed=cfg.seed)
        p3 = run_p3(
            df,
            thresholds_q=tuple(cfg.thresholds_q),
            bootstrap_resamples=tail.bootstrap_resamples,
            ci_level=tail.ci_level,
            seed=cfg.seed,
            pooled_gamma={k: v for k, v in pooled.items() if v is not None},
            tau_override=tau_override,
        )
        p5 = run_p5(df)

        payload: dict[str, Any] = {
            "n_rows": len(df),
            "n_traces": int(df["trace_id"].nunique()),
            "cells": sorted(
                {
                    (str(m), int(ell), str(s))
                    for m, ell, s in df[["model", "layer", "statistic"]]
                    .drop_duplicates()
                    .itertuples(index=False)
                }
            ),
            "P1": [r.as_dict() for r in p1],
            "P2": [r.as_dict() for r in p2],
            "P3": [r.as_dict() for r in p3],
            "P5": [r.as_dict() for r in p5],
            "not_run": [
                key
                for key, results in (("P1", p1), ("P2", p2), ("P3", p3), ("P5", p5))
                if not results
            ],
        }
        man.add_output(write_json(out / "analysis_metrics.json", payload), "metrics")
        pm = Path(metrics_dir)
        pm.mkdir(parents=True, exist_ok=True)
        man.add_output(write_json(pm / f"{name}.json", payload), "metrics")

        if payload["not_run"]:
            man.note(
                "predictions with no result on this table (too few traces, subsets or lengths): "
                + ", ".join(payload["not_run"])
            )

        from ..reporting.plots import figure_length_law, figure_overshoot, figure_roc
        from ..reporting.tables import render_table1, render_table2, write_table

        figures = Path(figures_dir)

        if p1:
            headers, rows = render_table1(p1)
            for path in write_table(
                headers,
                rows,
                tables_dir,
                f"table1_{name}",
                caption="Tail index on step deviations (P1).",
                label=f"tab:table1-{name}",
            ):
                man.add_output(path, "table")
        if p2:
            headers, rows = render_table2(p2)
            for path in write_table(
                headers,
                rows,
                tables_dir,
                f"table2_{name}",
                caption="Localization of the first rejected step (P2).",
                label=f"tab:table2-{name}",
                group_column=0,
            ):
                man.add_output(path, "table")

        # Every figure the predictions produce, drawn from the results just computed.
        if p3:
            for path in figure_overshoot(
                [r.as_dict() for r in p3], figures, f"p3_overshoot_{name}"
            ):
                man.add_output(path, "figure")
        if p5:
            for path in figure_length_law(p5[0].as_dict(), figures, f"p5_length_law_{name}"):
                man.add_output(path, "figure")
        if p2:
            for path in figure_roc([r.as_dict() for r in p2], figures, f"p2_roc_{name}"):
                man.add_output(path, "figure")

        for r1 in p1:
            man.add_metric(f"P1_{r1.model}_L{r1.layer}_{r1.statistic}", r1.separation)
        for r2 in p2:
            man.add_metric(f"P2_{r2.model}_L{r2.layer}_{r2.statistic}", r2.row())

        log.info(
            "analysis done: P1 %d cells, P2 %d cells, P3 %d fits, P5 %d fits%s",
            len(p1),
            len(p2),
            len(p3),
            len(p5),
            f"; not run: {', '.join(payload['not_run'])}" if payload["not_run"] else "",
        )
        return payload
