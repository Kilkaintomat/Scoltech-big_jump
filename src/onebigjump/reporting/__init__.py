"""Figures and tables. Everything here is rendered from a metrics file."""

from .plots import figure_grokking, figure_one, hill_plot_figure
from .style import ESTIMATOR, INK, P_RAMP, apply_style, p_colour
from .tables import (
    PLACEHOLDER,
    render_table1,
    render_table2,
    to_latex,
    to_markdown,
    write_table,
)

__all__ = [
    "ESTIMATOR",
    "INK",
    "PLACEHOLDER",
    "P_RAMP",
    "apply_style",
    "figure_grokking",
    "figure_one",
    "hill_plot_figure",
    "p_colour",
    "render_table1",
    "render_table2",
    "to_latex",
    "to_markdown",
    "write_table",
]
