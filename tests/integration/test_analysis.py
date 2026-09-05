"""P1-P5 end to end over one table, with its manifest, tables and metrics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from onebigjump.config import AnalysisConfig, TailEstimationConfig
from onebigjump.experiments.analysis import run_analysis
from onebigjump.experiments.dataset import from_kesten
from onebigjump.simulation.kesten import simulate

FAST = AnalysisConfig(
    permutation_resamples=100,
    tail=TailEstimationConfig(
        bootstrap_resamples=50, double_bootstrap_resamples=50, k_selector="fixed_frac", k_min=20
    ),
)


@pytest.fixture(scope="module")
def table():
    return from_kesten(simulate(0.05, n_traces=1200, n_steps=64, seed=2))


@pytest.fixture(scope="module")
def result(table, tmp_path_factory):
    out = tmp_path_factory.mktemp("analysis")
    payload = run_analysis(
        table,
        FAST,
        out_dir=out,
        name="unit",
        tables_dir=out / "tables",
        metrics_dir=out / "metrics",
        tau_override=table.attrs["tau"],
    )
    return payload, out


class TestPredictions:
    def test_the_predictions_the_table_supports_all_ran(self, result) -> None:
        payload, _ = result
        assert len(payload["P1"]) == 1
        assert len(payload["P2"]) == 1
        assert len(payload["P3"]) == 2  # one per tolerance level

    def test_p5_is_reported_as_not_run_rather_than_omitted(self, result) -> None:
        """Every trace here has the same length, so the length law has nothing to fit."""
        payload, _ = result
        assert payload["P5"] == []
        assert "P5" in payload["not_run"]

    def test_the_manifest_records_why(self, result) -> None:
        _, out = result
        man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        assert man["status"] == "ok"
        assert any("P5" in note for note in man["notes"])

    def test_p3_is_told_the_pooled_estimate_to_compare_against(self, result) -> None:
        payload, _ = result
        for fit in payload["P3"]:
            assert "cmp_pooled_gamma" in fit
            assert "cmp_compatible" in fit


class TestArtifacts:
    def test_both_tables_are_written_in_both_formats(self, result) -> None:
        _, out = result
        for stem in ("table1_unit", "table2_unit"):
            for ext in ("md", "tex"):
                path = out / "tables" / f"{stem}.{ext}"
                assert path.is_file() and path.stat().st_size > 0

    def test_table_one_has_the_paper_s_subsets(self, result) -> None:
        _, out = result
        text = (out / "tables" / "table1_unit.md").read_text(encoding="utf-8")
        assert "verified" in text
        assert r"refuted, $t<t^*$" in text
        assert r"refuted, $t \geq t^*$" in text

    def test_a_column_the_data_cannot_fill_shows_the_placeholder(self, result) -> None:
        """The surrogate has no tokens, so the surprisal baseline is genuinely unavailable."""
        _, out = result
        text = (out / "tables" / "table2_unit.md").read_text(encoding="utf-8")
        assert "[x.xx]" in text

    def test_the_latex_is_booktabs(self, result) -> None:
        _, out = result
        text = (out / "tables" / "table1_unit.tex").read_text(encoding="utf-8")
        for token in (r"\toprule", r"\midrule", r"\bottomrule", r"\caption"):
            assert token in text

    def test_metrics_are_strict_json(self, result) -> None:
        _, out = result
        text = (out / "analysis_metrics.json").read_text(encoding="utf-8")
        assert "NaN" not in text and "Infinity" not in text
        json.loads(text)

    def test_outputs_are_registered_with_digests(self, result) -> None:
        _, out = result
        man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        roles = {o["role"] for o in man["outputs"]}
        assert {"metrics", "table"} <= roles
        assert all(o["digest"] for o in man["outputs"])


class TestAgainstTheClosedForm:
    def test_localisation_matches_the_papers_prediction(self, result) -> None:
        payload, _ = result
        p2 = payload["P2"][0]
        assert p2["top1"] == pytest.approx(0.85, abs=0.10)
        assert p2["chance"] == pytest.approx(1 / 64, rel=1e-6)
        assert p2["perm_p"] < 0.05

    def test_the_refuted_tail_is_the_heavier_one(self, result) -> None:
        payload, _ = result
        sep = payload["P1"][0]["separation"]
        assert sep["gamma_refuted"] > sep["gamma_verified"]

    def test_the_overshoot_variants_and_theta_are_recorded(self, result) -> None:
        payload, _ = result
        fit = payload["P3"][0]
        assert set(fit["variants"]) == {"first", "trace_max", "unconditional"}
        assert fit["theta"] <= 1.0


class TestEmptyCases:
    def test_a_table_with_no_refuted_traces_still_produces_p1(self, tmp_path: Path) -> None:
        table = from_kesten(simulate(0.0, n_traces=400, n_steps=64, seed=9))
        table = table[table["outcome"] == "verified"]
        payload = run_analysis(
            table,
            FAST,
            out_dir=tmp_path,
            name="verified-only",
            tables_dir=tmp_path / "t",
            metrics_dir=tmp_path / "m",
        )
        assert payload["P1"]
        assert "P2" in payload["not_run"]
        assert "P3" in payload["not_run"]
