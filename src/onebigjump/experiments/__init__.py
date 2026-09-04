"""The five predictions of Section 5, each testable against the surrogate and against real traces."""

from .dataset import COLUMNS, SUBSETS, from_kesten, from_traces, subset, validate_table
from .p1_tail_separation import P1Result, run_p1, tail_separation
from .p2_localization import P2Result, localization_rates, run_p2
from .p3_overshoot import P3Result, run_p3
from .p5_length_law import LengthLawFit, P5Result, fit_length_law, run_p5

__all__ = [
    "COLUMNS",
    "SUBSETS",
    "LengthLawFit",
    "P1Result",
    "P2Result",
    "P3Result",
    "P5Result",
    "fit_length_law",
    "from_kesten",
    "from_traces",
    "localization_rates",
    "run_p1",
    "run_p2",
    "run_p3",
    "run_p5",
    "subset",
    "tail_separation",
    "validate_table",
]
