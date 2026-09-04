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
from .hooks import LayerCapture, ResidualRecorder, block_modules, layer_indices, record_residuals
from .token_alignment import StepSpan, TokenAlignment, align_steps, line_offsets, step_char_spans

__all__ = [
    "Calibration",
    "LayerCapture",
    "ResidualRecorder",
    "StepSpan",
    "TokenAlignment",
    "Trajectory",
    "align_steps",
    "block_modules",
    "deviations",
    "extract_trajectory",
    "fit_calibration",
    "layer_indices",
    "ledoit_wolf_intensity",
    "line_offsets",
    "record_residuals",
    "shrinkage_target",
    "step_char_spans",
]
