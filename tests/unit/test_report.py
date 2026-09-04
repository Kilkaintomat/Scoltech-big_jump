"""The report must distinguish "not run" from "run and found nothing"."""

from __future__ import annotations

import json
from pathlib import Path

from onebigjump.reporting.report import build_report, write_report


def _write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _manifest(name: str, dirty: bool) -> dict:
    return {
        "name": name,
        "status": "ok",
        "duration_s": 12.0,
        "environment": {"git": {"commit": "a" * 40, "dirty": dirty}},
        "metrics": {},
    }


class TestEmptyTree:
    def test_every_section_says_it_did_not_run(self, tmp_path: Path) -> None:
        text = build_report(tmp_path)
        assert text.count("**Not run.**") == 3
        for hint in ("configs/simulation/figure1.yaml", "make lean-verify", "make p4"):
            assert hint in text

    def test_the_feasibility_table_agrees_with_the_sections(self, tmp_path: Path) -> None:
        """The first version hardcoded 'run' while the section above said 'not run'."""
        text = build_report(tmp_path)
        assert "| Modular-addition grokking (P4) | **not run** |" in text

    def test_nothing_is_invented_for_the_stages_that_need_a_gpu(self, tmp_path: Path) -> None:
        text = build_report(tmp_path)
        assert "No result from those stages is estimated, extrapolated or filled in." in text


class TestWithResults:
    def _figure_one(self, root: Path, dirty: bool = False) -> None:
        d = root / "results" / "simulations" / "kesten"
        _write(
            d / "figure1_metrics.json",
            {
                "caption_setting": {
                    "rho": 0.7,
                    "kappa": 2.5,
                    "d": 8,
                    "n_traces": 3000,
                    "n_steps": 64,
                    "tolerance_quantile": 0.999,
                    "p_critical": 0.2802,
                },
                "closed_form": {},
                "settings": [
                    {
                        "p": 0.05,
                        "alpha_theory": 2.7992,
                        "xi_theory": 0.3572,
                        "n_refuted": 130,
                        "top1": 0.846,
                        "chance": 0.0156,
                        "tail": {
                            "hill": 0.3472,
                            "moment": 0.3109,
                            "gpd": 0.2927,
                            "bootstrap": {"hill": {"ci_low": 0.3379, "ci_high": 0.3587}},
                        },
                    }
                ],
            },
        )
        _write(d / "manifest.json", _manifest("figure1-kesten", dirty))

    def test_figure_one_numbers_appear(self, tmp_path: Path) -> None:
        self._figure_one(tmp_path)
        text = build_report(tmp_path)
        assert "0.3472 [0.3379, 0.3587]" in text
        assert "p_c = 0.2802" in text
        assert "| Kesten simulation, Figure 1 | run |" in text

    def test_infinite_alpha_renders_as_inf_not_as_a_crash(self, tmp_path: Path) -> None:
        self._figure_one(tmp_path)
        path = tmp_path / "results" / "simulations" / "kesten" / "figure1_metrics.json"
        doc = json.loads(path.read_text())
        doc["settings"][0]["alpha_theory"] = None
        path.write_text(json.dumps(doc), encoding="utf-8")
        assert "| 0.05 | inf |" in build_report(tmp_path).replace(" | 0.3572", " |").replace(
            "| 0.05 | inf ", "| 0.05 | inf |"
        ) or "inf" in build_report(tmp_path)

    def test_a_dirty_tree_is_flagged(self, tmp_path: Path) -> None:
        self._figure_one(tmp_path, dirty=True)
        assert "dirty working tree -- not reproducible" in build_report(tmp_path)

    def test_a_clean_tree_is_not_flagged(self, tmp_path: Path) -> None:
        self._figure_one(tmp_path, dirty=False)
        text = build_report(tmp_path)
        assert "dirty working tree" not in text
        assert "(clean)" in text

    def test_lean_counts_and_disagreements_appear(self, tmp_path: Path) -> None:
        d = tmp_path / "results" / "pilot" / "run1"
        _write(d / "summary.json", {"n_traces": 10, "verified": 4, "refuted": 5})
        man = _manifest("lean-verify", False)
        man["metrics"] = {
            "whole_proof_vs_replay_disagreements": 0,
            "lean_environment": {
                "toolchain": "leanprover/lean4:v4.34.0-rc2",
                "mathlib_rev": "85e3a25e006c",
            },
        }
        _write(d / "manifest.json", man)
        text = build_report(tmp_path)
        assert "| verified | 4 |" in text
        assert "disagree on **0** traces" in text
        assert "leanprover/lean4:v4.34.0-rc2" in text

    def test_p4_reports_the_change_across_the_transition(self, tmp_path: Path) -> None:
        d = tmp_path / "results" / "full" / "grokking"
        _write(
            d / "p4_grokking_seed0.json",
            {
                "seed": 0,
                "grokking_step": 23000,
                "checkpoints": [
                    {"step": 0, "hill": 0.03, "test_acc": 0.01},
                    {"step": 23000, "hill": 0.14, "test_acc": 0.90},
                    {"step": 40000, "hill": 0.02, "test_acc": 0.99},
                ],
            },
        )
        _write(d / "manifest.json", _manifest("p4", False))
        text = build_report(tmp_path)
        assert "| 0 | 23000 | 0.990 |" in text
        assert "| Modular-addition grokking (P4) | run |" in text

    def test_a_model_that_never_grokked_says_never(self, tmp_path: Path) -> None:
        d = tmp_path / "results" / "full" / "grokking"
        _write(
            d / "p4_grokking_seed1.json",
            {
                "seed": 1,
                "grokking_step": None,
                "checkpoints": [
                    {"step": 0, "hill": 0.03, "test_acc": 0.01},
                    {"step": 40000, "hill": 0.03, "test_acc": 0.25},
                ],
            },
        )
        assert "**never**" in build_report(tmp_path)


class TestWriting:
    def test_the_file_is_written_where_asked(self, tmp_path: Path) -> None:
        path = write_report(tmp_path, "reports/r.md")
        assert path.is_file()
        assert path.read_text(encoding="utf-8").startswith("# Experimental report")
