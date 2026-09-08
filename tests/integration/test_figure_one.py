"""End to end: simulate, estimate, write metrics and a manifest, draw the figure."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from onebigjump.config import KestenConfig, TailEstimationConfig
from onebigjump.simulation.figure1 import analyse_setting, run_figure_one

SMALL = KestenConfig(
    p_values=[0.0, 0.05],
    n_traces=400,
    n_steps=32,
    burn_in=50,
    tail=TailEstimationConfig(
        k_min=20, bootstrap_resamples=50, double_bootstrap_resamples=50, k_selector="fixed_frac"
    ),
)


class TestSetting:
    def test_analyse_setting_fills_every_panel(self) -> None:
        res, tr = analyse_setting(0.05, SMALL)
        assert res.p == 0.05
        assert res.n_traces == 400
        assert res.n_steps == 32
        assert res.chance == pytest.approx(1 / 32)
        assert res.tau > 0
        assert 0 <= res.top1 <= 1
        assert res.survival["z"] and res.survival["s"]
        assert len(res.exemplar_trace) == 32
        assert tr.z.shape == (400, 32)

    def test_the_control_and_the_mixture_separate(self) -> None:
        alg, _ = analyse_setting(0.0, SMALL)
        heur, _ = analyse_setting(0.05, SMALL)
        assert heur.tail["hill"] > alg.tail["hill"]
        assert heur.tau > alg.tau
        assert alg.alpha_theory == float("inf")
        assert heur.alpha_theory == pytest.approx(2.7992, abs=0.01)


class TestRun:
    @pytest.fixture(scope="class")
    def run(self, tmp_path_factory) -> tuple[dict, Path, Path]:
        out = tmp_path_factory.mktemp("kesten")
        figs = tmp_path_factory.mktemp("figs")
        metrics = tmp_path_factory.mktemp("metrics")
        payload = run_figure_one(
            SMALL, out_dir=out, figure_dir=figs, metrics_dir=metrics, make_figure=True
        )
        return payload, out, figs

    def test_metrics_record_the_caption_setting(self, run) -> None:
        payload, _, _ = run
        cap = payload["caption_setting"]
        assert (cap["rho"], cap["kappa"], cap["d"]) == (0.7, 2.5, 8)
        assert cap["p_critical"] == pytest.approx(0.2802, abs=1e-4)

    def test_closed_form_is_recorded_for_every_rate(self, run) -> None:
        payload, _, _ = run
        assert set(payload["closed_form"]) == {"0.00", "0.05"}
        assert payload["closed_form"]["0.05"]["alpha"] == pytest.approx(2.7992, abs=0.01)

    def test_outputs_and_manifest_are_written(self, run) -> None:
        _, out, figs = run
        assert (out / "figure1_metrics.json").is_file()
        assert (out / "figure1_summary.csv").is_file()
        assert (figs / "figure1_kesten_dichotomy.pdf").is_file()
        assert (figs / "figure1_kesten_dichotomy.png").is_file()

        man = json.loads(next(out.glob("manifest-*.json")).read_text(encoding="utf-8"))
        assert man["status"] == "ok"
        assert man["kind"] == "kesten"
        roles = {o["role"] for o in man["outputs"]}
        assert {"metrics", "table", "figure"} <= roles
        assert all(o["digest"] for o in man["outputs"])
        assert man["environment"]["git"]["commit"]
        assert "hill_p0.05" in man["metrics"]

    def test_the_metrics_file_is_strict_json(self, run) -> None:
        """Infinite alpha at p = 0 must round-trip as null, not as the bare token Infinity."""
        _, out, _ = run
        text = (out / "figure1_metrics.json").read_text(encoding="utf-8")
        assert "Infinity" not in text and "NaN" not in text
        reloaded = json.loads(text)
        assert reloaded["settings"][0]["alpha_theory"] is None

    def test_the_summary_csv_has_one_row_per_rate(self, run) -> None:
        _, out, _ = run
        lines = (out / "figure1_summary.csv").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        assert lines[0].startswith("p,alpha_theory,xi_theory,hill")

    def test_the_figure_can_be_redrawn_from_the_metrics_alone(self, run, tmp_path: Path) -> None:
        """No number in a figure comes from anywhere but a metrics file."""
        payload, out, _ = run
        from onebigjump.reporting.plots import figure_one

        reloaded = json.loads((out / "figure1_metrics.json").read_text(encoding="utf-8"))
        paths = figure_one(reloaded, tmp_path)
        assert all(p.is_file() and p.stat().st_size > 0 for p in paths)
        assert reloaded == payload or np.isclose(
            reloaded["settings"][1]["tail"]["hill"], payload["settings"][1]["tail"]["hill"]
        )


class TestHillPlotFigure:
    """Section 4 requires the full Hill plot alongside any point estimate."""

    def test_it_is_drawn_from_the_metrics_alone(self, tmp_path) -> None:
        import json

        from onebigjump.reporting.plots import figure_hill_plots
        from onebigjump.simulation.figure1 import run_figure_one

        out = tmp_path / "run"
        payload = run_figure_one(
            SMALL,
            out_dir=out,
            figure_dir=tmp_path / "figs",
            metrics_dir=tmp_path / "metrics",
            make_figure=True,
        )
        assert (tmp_path / "figs" / "hill_plots_kesten.pdf").is_file()

        reloaded = json.loads((out / "figure1_metrics.json").read_text(encoding="utf-8"))
        paths = figure_hill_plots(reloaded, tmp_path / "again")
        assert all(p.is_file() and p.stat().st_size > 0 for p in paths)
        assert payload["settings"][0]["tail"]["hill_plot"]["k"]

    def test_the_manifest_registers_both_figures(self, tmp_path) -> None:
        import json

        from onebigjump.simulation.figure1 import run_figure_one

        out = tmp_path / "run"
        run_figure_one(
            SMALL,
            out_dir=out,
            figure_dir=tmp_path / "figs",
            metrics_dir=tmp_path / "metrics",
            make_figure=True,
        )
        man = json.loads(next(out.glob("manifest-*.json")).read_text(encoding="utf-8"))
        figures = [o["path"] for o in man["outputs"] if o["role"] == "figure"]
        assert any("figure1_kesten_dichotomy" in f for f in figures)
        assert any("hill_plots_kesten" in f for f in figures)
