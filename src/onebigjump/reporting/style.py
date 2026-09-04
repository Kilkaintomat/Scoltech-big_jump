"""Figure style: one palette, applied everywhere, chosen so the figures survive print.

Two palettes, both validated rather than eyeballed (OKLCH lightness band, chroma floor,
colour-vision-deficiency separation on all pairs, and contrast against a white page):

* `P_RAMP` -- a single-hue sequential ramp for the off-support rate `p`, because `p` is a
  magnitude, not an identity. It is ordered light to dark as `p` increases.
* `ESTIMATOR` -- three categorical hues for the three estimators of equation 3, which *are*
  identities.

`p = 0` is not a step of the ramp: it is the algorithmic control, the reference against which
everything else is read, so it wears neutral ink. Every series also carries a distinct dash
pattern and marker, so identity never rests on colour alone -- ICLR proceedings get printed,
photocopied and read on projectors.
"""

from __future__ import annotations

from typing import Any

__all__ = ["DASHES", "ESTIMATOR", "GRID", "INK", "MUTED", "P_RAMP", "RC", "apply_style", "p_colour"]

INK = "#1a1a1a"  # reference / control / theory lines
MUTED = "#6b6b6b"  # secondary annotation
GRID = "#d8d8d8"

# Sequential, light -> dark with increasing p. Validated: monotone L, dL >= 0.06, single hue.
P_RAMP = ["#6baed6", "#2171b5", "#08306b"]

# Categorical. Validated all-pairs: worst CVD dE 11.6 (deutan), worst normal-vision dE 18.8.
ESTIMATOR = {"hill": "#2171b5", "moment": "#d95f02", "gpd": "#1b9e77"}

DASHES: dict[str, Any] = {
    "solid": (None, None),
    "theory": (5, 2),
    "asymptote": (1, 2),
    "tolerance": (4, 1, 1, 1),
}

RC: dict[str, Any] = {
    "figure.dpi": 160,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 8,
    "axes.titlesize": 8.5,
    "axes.labelsize": 8,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.5,
    "grid.alpha": 0.8,
    "lines.linewidth": 1.3,
    "legend.frameon": False,
    "figure.constrained_layout.use": True,
}


def p_colour(p: float, positive_rates: list[float]) -> str:
    """Neutral ink for the `p = 0` control; a ramp step, ordered by `p`, for the rest."""
    if p <= 0:
        return INK
    rates = sorted(r for r in positive_rates if r > 0)
    idx = rates.index(p) if p in rates else 0
    if len(rates) <= 1:
        return P_RAMP[-1]
    pos = idx / (len(rates) - 1)
    return P_RAMP[min(round(pos * (len(P_RAMP) - 1)), len(P_RAMP) - 1)]


def apply_style() -> None:
    """Install the project rcParams on the global matplotlib state."""
    import matplotlib

    # rcParams keys are a typed Literal union; a plain dict of str keys does not match it.
    matplotlib.rcParams.update(RC)  # type: ignore[arg-type]
