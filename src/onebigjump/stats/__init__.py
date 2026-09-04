"""Extreme-value statistics for pooled reasoning traces (Section 4 of the paper)."""

from .bootstrap import BootstrapResult, cluster_variance, effective_sample, group_bootstrap
from .diagnostics import (
    IdentifiedTail,
    hill_plot,
    identified_tail,
    mean_excess,
    pareto_qq,
    survival,
)
from .estimators import TailEstimate, estimate_tail, xi_from_gamma
from .extremal_index import ExtremalIndexEstimate, extremal_index, traces_from_groups
from .gpd import (
    FitComparison,
    GPDFit,
    compare_tail_models,
    exponential_fit,
    gpd_fit,
    gpd_from_order_statistics,
    weibull_fit,
)
from .hill import hill, hill_curve, log_moments, sorted_positive_desc
from .moment import moment, moment_curve
from .thresholds import KSelection, double_bootstrap_k, ks_distance_k, plateau_k, select_k

__all__ = [
    "BootstrapResult",
    "ExtremalIndexEstimate",
    "FitComparison",
    "GPDFit",
    "IdentifiedTail",
    "KSelection",
    "TailEstimate",
    "cluster_variance",
    "compare_tail_models",
    "double_bootstrap_k",
    "effective_sample",
    "estimate_tail",
    "exponential_fit",
    "extremal_index",
    "gpd_fit",
    "gpd_from_order_statistics",
    "group_bootstrap",
    "hill",
    "hill_curve",
    "hill_plot",
    "identified_tail",
    "ks_distance_k",
    "log_moments",
    "mean_excess",
    "moment",
    "moment_curve",
    "pareto_qq",
    "plateau_k",
    "select_k",
    "sorted_positive_desc",
    "survival",
    "traces_from_groups",
    "weibull_fit",
    "xi_from_gamma",
]
