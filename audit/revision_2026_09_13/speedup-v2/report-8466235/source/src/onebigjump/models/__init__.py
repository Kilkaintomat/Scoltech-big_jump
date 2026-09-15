"""Residual-stream trajectory extraction: hooks, token alignment, deviation statistics."""

from .activations import (
    Calibration,
    Trajectory,
    deviations,
    extract_trajectory,
    fit_calibration,
    ledoit_wolf_intensity,
    shrinkage_target,
)
from .extraction import (
    ExtractionResult,
    extract_table,
    load_extraction_model,
    read_traces,
    stratified_calibration_split,
)
from .generation import Backend, HFBackend, Sample, VLLMBackend, generate, make_backend
from .hooks import LayerCapture, ResidualRecorder, block_modules, layer_indices, record_residuals
from .token_alignment import StepSpan, TokenAlignment, align_steps, line_offsets, step_char_spans

__all__ = [
    "Backend",
    "Calibration",
    "ExtractionResult",
    "HFBackend",
    "LayerCapture",
    "ResidualRecorder",
    "Sample",
    "StepSpan",
    "TokenAlignment",
    "Trajectory",
    "VLLMBackend",
    "align_steps",
    "block_modules",
    "deviations",
    "extract_table",
    "extract_trajectory",
    "fit_calibration",
    "generate",
    "layer_indices",
    "ledoit_wolf_intensity",
    "line_offsets",
    "load_extraction_model",
    "make_backend",
    "read_traces",
    "record_residuals",
    "shrinkage_target",
    "step_char_spans",
    "stratified_calibration_split",
]
