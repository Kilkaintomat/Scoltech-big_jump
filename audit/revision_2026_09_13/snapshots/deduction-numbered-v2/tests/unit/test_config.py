"""Configs are strict on purpose: a typo in a YAML key must not silently become a default."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from onebigjump.config import RunConfig, TailEstimationConfig, dump_config, load_config


def _write(tmp_path: Path, obj: dict) -> Path:
    p = tmp_path / "run.yaml"
    p.write_text(yaml.safe_dump(obj), encoding="utf-8")
    return p


class TestLoading:
    def test_round_trip(self, tmp_path: Path) -> None:
        raw = {
            "name": "kesten-figure1",
            "kind": "kesten",
            "description": "Figure 1",
            "kesten": {"rho": 0.7, "kappa": 2.5, "n_traces": 100, "n_steps": 16},
        }
        cfg = load_config(_write(tmp_path, raw))
        assert cfg.name == "kesten-figure1"
        assert cfg.kesten is not None
        assert cfg.kesten.rho == 0.7
        assert cfg.kesten.n_traces == 100
        assert dump_config(cfg)["kesten"]["kappa"] == 2.5

    def test_section_returns_the_active_block(self, tmp_path: Path) -> None:
        cfg = load_config(_write(tmp_path, {"name": "s", "kind": "kesten", "kesten": {}}))
        assert cfg.section() is cfg.kesten

    def test_generate_maps_to_the_model_block(self, tmp_path: Path) -> None:
        cfg = load_config(
            _write(tmp_path, {"name": "g", "kind": "generate", "model": {"model_id": "x/y"}})
        )
        assert cfg.section() is cfg.model

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "absent.yaml")

    def test_non_mapping_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            load_config(p)


class TestStrictness:
    def test_unknown_keys_are_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="Extra inputs"):
            load_config(_write(tmp_path, {"name": "x", "kind": "kesten", "typo_here": 1}))

    def test_unknown_kind_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            load_config(_write(tmp_path, {"name": "x", "kind": "not-a-kind"}))

    @pytest.mark.parametrize("bad", ["", "has space", "has/slash", "has\\backslash"])
    def test_bad_names_are_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            RunConfig(name=bad, kind="kesten")

    @pytest.mark.parametrize(
        "field,value",
        [
            ("rho", 1.5),
            ("rho", 0.0),
            ("kappa", 0.5),
            ("n_traces", 1),
            ("n_steps", 2),
            ("tolerance_quantile", 1.0),
            ("sigma", -1.0),
        ],
    )
    def test_kesten_bounds_are_enforced(self, tmp_path: Path, field: str, value: float) -> None:
        with pytest.raises(ValidationError):
            load_config(_write(tmp_path, {"name": "x", "kind": "kesten", "kesten": {field: value}}))

    @pytest.mark.parametrize(
        "field,value",
        [
            ("k_min", 1),
            ("k_max_frac", 0.9),
            ("ci_level", 1.0),
            ("bootstrap_resamples", 10),
            ("double_bootstrap_n1_exponent", 1.0),
            ("k_selector", "eyeball"),
        ],
    )
    def test_tail_bounds_are_enforced(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            TailEstimationConfig(**{field: value})  # type: ignore[arg-type]


class TestDefaults:
    def test_paper_defaults_are_the_ones_in_appendix_b4(self) -> None:
        cfg = TailEstimationConfig()
        assert cfg.k_selector == "double_bootstrap"
        assert cfg.double_bootstrap_n1_exponent == 0.9
        assert cfg.double_bootstrap_resamples == 200
        assert cfg.bootstrap_resamples == 500
        assert cfg.bootstrap_unit == "trace"
        assert cfg.ci_level == 0.95
        assert cfg.estimators == ["hill", "moment", "gpd"]

    def test_figure_one_parameters_are_the_ones_in_the_caption(self) -> None:
        from onebigjump.config import KestenConfig

        k = KestenConfig()
        assert (k.rho, k.kappa, k.d, k.n_traces, k.n_steps) == (0.7, 2.5, 8, 3000, 64)
        assert k.tolerance_quantile == 0.999

    def test_nested_configs_are_independent_instances(self) -> None:
        a, b = TailEstimationConfig(), TailEstimationConfig()
        a.k_min = 99
        assert b.k_min == 20
