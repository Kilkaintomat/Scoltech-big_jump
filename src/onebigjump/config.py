"""Pydantic-validated experiment configuration loaded from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class TailEstimationConfig(Strict):
    """Settings shared by every tail-index estimate in the project."""

    k_min: int = Field(20, ge=5, description="smallest number of upper order statistics")
    k_max_frac: float = Field(0.25, gt=0, le=0.5, description="k_max = frac * n")
    k_selector: Literal["double_bootstrap", "ks", "fixed_frac", "plateau"] = "double_bootstrap"
    k_fixed_frac: float = Field(0.05, gt=0, lt=0.5)
    double_bootstrap_resamples: int = Field(200, ge=20)
    double_bootstrap_n1_exponent: float = Field(0.9, gt=0.5, lt=1.0)
    bootstrap_resamples: int = Field(500, ge=50)
    bootstrap_unit: Literal["trace", "prompt", "step"] = "trace"
    ci_level: float = Field(0.95, gt=0.5, lt=1.0)
    estimators: list[Literal["hill", "moment", "gpd"]] = ["hill", "moment", "gpd"]


class KestenConfig(Strict):
    """Heuristic-mixture stochastic recurrence E_t = a_t E_{t-1} + B_t."""

    rho: float = Field(0.7, gt=0, lt=1, description="contractive multiplier (on-support)")
    kappa: float = Field(2.5, gt=1, description="expansive multiplier (off-support)")
    p_values: list[float] = Field([0.0, 0.02, 0.05, 0.10, 0.15, 0.20])
    d: int = Field(8, ge=1, description="residual-stream dimension of the surrogate")
    n_traces: int = Field(3000, ge=10)
    n_steps: int = Field(64, ge=4)
    burn_in: int = Field(200, ge=0)
    sigma: float = Field(1.0, gt=0, description="scale of the Gaussian additive term B_t")
    tolerance_quantile: float = Field(0.999, gt=0, lt=1, description="tau = this quantile of Z")
    seed: int = 20270101
    tail: TailEstimationConfig = TailEstimationConfig()
    out_dir: Path = Path("results/simulations/kesten")
    figure_p_trace: float = Field(0.05, description="p shown in panel (a)/(d) against p=0")


class LeanConfig(Strict):
    workspace: Path = Path("lean_workspace")
    repl_dir: Path | None = None
    toolchain: str | None = None
    timeout_s: int = Field(180, ge=5)
    per_step_timeout_s: int = Field(60, ge=1)
    max_traces: int | None = None
    input_traces: Path | None = None
    out_dir: Path = Path("results/pilot/lean")
    seed: int = 0


class ModelConfig(Strict):
    """Sampling settings for Section 5.1 and 5.2 (Appendix B.3)."""

    model_id: str
    revision: str | None = None
    dtype: Literal["float32", "float16", "bfloat16", "auto"] = "auto"
    device: Literal["auto", "cpu", "mps", "cuda"] = "auto"
    backend: Literal["auto", "vllm", "hf"] = "auto"
    max_new_tokens: int = Field(512, ge=1)
    temperatures: list[float] = [0.6, 1.0]
    samples_per_problem: int = Field(4, ge=1)
    seed: int = 1234
    trust_remote_code: bool = False
    attn_implementation: str | None = None
    problems: str | None = Field(
        None, description="a JSONL path or a Hugging Face dataset id of theorem statements"
    )
    problem_split: str | None = None
    max_problems: int | None = None
    batch_size: int = Field(1, ge=1, description="prompts per generate call")


class ActivationConfig(Strict):
    """Read-out settings for Appendix B.1."""

    model_id: str = "gpt2"
    traces: Path | None = Field(None, description="JSONL written by `onebigjump lean-verify`")
    device: Literal["auto", "cpu", "mps", "cuda"] = "auto"
    dtype: Literal["float32", "float16", "bfloat16", "auto"] = "bfloat16"
    max_tokens: int | None = Field(4096, description="skip traces longer than this")
    layer_fractions: list[float] = [0.25, 0.5, 0.75]
    statistics: list[Literal["raw", "whitened", "innovation"]] = ["raw", "whitened", "innovation"]
    shrinkage: float = Field(0.1, ge=0.0, le=1.0, description="Ledoit-Wolf-style ridge on Sigma")
    ridge_alpha: float = Field(1.0, gt=0, description="ridge for the innovation regression")
    calibration_split: Literal["verified_disjoint", "verified_all"] = "verified_disjoint"
    calibration_frac: float = Field(0.5, gt=0, lt=1)
    batch_size: int = Field(1, ge=1)
    out_dir: Path = Path("data/processed/activations")


class SyntheticConfig(Strict):
    """PrOntoQA-style first-order deduction."""

    chain_lengths: list[int] = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    n_problems_per_length: int = Field(40, ge=1)
    n_entities: int = Field(12, ge=3)
    n_distractor_rules: int = Field(6, ge=0)
    ontology_seed: int = 7
    use_fictional_names: bool = True
    out_dir: Path = Path("data/processed/synthetic")


class GrokkingConfig(Strict):
    p: int = Field(113, ge=5)
    d_model: int = Field(128, ge=8)
    n_heads: int = Field(4, ge=1)
    n_layers: int = Field(1, ge=1)
    d_mlp: int | None = None
    lr: float = 1e-3
    weight_decay: float = 1.0
    betas: tuple[float, float] = (0.9, 0.98)
    train_frac: float = Field(0.3, gt=0, lt=1)
    #: Train against a random permutation of the labels. The null for P4: nothing generalises, so
    #: any decline in the tail index cannot be attributed to the network finding an algorithm.
    shuffle_labels: bool = False
    steps: int = Field(40000, ge=100)
    checkpoint_every: int = Field(100, ge=1)
    seeds: list[int] = [0, 1, 2]
    device: Literal["auto", "cpu", "mps", "cuda"] = "auto"
    tail: TailEstimationConfig = TailEstimationConfig()
    out_dir: Path = Path("results/full/grokking")


class AnalysisConfig(Strict):
    """Inputs to the P1-P5 analysis commands."""

    deviations: Path | None = None
    layer: str | None = None
    statistic: Literal["raw", "whitened", "innovation"] = "whitened"
    tail: TailEstimationConfig = TailEstimationConfig()
    out_dir: Path = Path("results/full")
    thresholds_q: list[float] = [1e-2, 1e-3]
    permutation_resamples: int = Field(2000, ge=100)
    seed: int = 0
    localization_window: int = Field(3, ge=0)


class RunConfig(Strict):
    """Top-level config; every command reads one of these from YAML."""

    name: str
    kind: Literal["kesten", "lean", "generate", "activations", "analysis", "synthetic", "grokking"]
    description: str = ""
    seed: int = 0
    out_root: Path = Path("results")
    kesten: KestenConfig | None = None
    lean: LeanConfig | None = None
    model: ModelConfig | None = None
    activations: ActivationConfig | None = None
    synthetic: SyntheticConfig | None = None
    grokking: GrokkingConfig | None = None
    analysis: AnalysisConfig | None = None

    @field_validator("name")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not v or any(c in v for c in " /\\"):
            raise ValueError("name must be a non-empty slug without spaces or slashes")
        return v

    def section(self) -> Any:
        return getattr(self, self.kind if self.kind != "generate" else "model")


def load_config(path: str | Path) -> RunConfig:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"config must be a YAML mapping: {path}")
    return RunConfig.model_validate(raw)


def dump_config(cfg: RunConfig) -> dict[str, Any]:
    return cfg.model_dump(mode="json")
