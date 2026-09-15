"""The heuristic-mixture stochastic recurrence of Theorem 5, and the closed form it satisfies.

    E_t = a_t E_{t-1} + B_t,   a_t iid > 0,   B_t iid ~ N(0, sigma^2 I_d),   (a_t) independent of (B_t)

`E_t` is the representational error, the gap between the state the model is in and the state the
rule map would have produced. A heuristic applied on its support contracts the error
(`a = rho < 1`); applied off its support it may expand it (`a = kappa > 1`), and the off-support
rate `p` is the physical knob. Theorem 5(v) says the step deviations `Z_t = ||E_t - E_{t-1}||`
are then regularly varying with `alpha(p)` the unique positive root of

    (1 - p) rho^alpha + p kappa^alpha = 1,        0 < p < p_c = log(1/rho) / log(kappa/rho),

so the order parameter `xi(p) = 1/alpha(p)` is a closed-form function of `p`, not a fitted one.
At `p = 0` the map is uniformly contractive, no root exists, and Theorem 5(iii) gives a Gaussian
bound: the tail is empty and `xi = 0`. This module is the ground truth against which the
estimators of `onebigjump.stats` are calibrated, because here the answer is known exactly.

The paper writes the closed form as `(1-p) rho^alpha + p gamma^alpha = 1` in the caption of
Figure 1(c); that `gamma` is a typo for `kappa`, and it is `kappa` that is implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import optimize

from ..config import KestenConfig

__all__ = [
    "KestenTraces",
    "alpha_two_heuristics",
    "lyapunov_exponent",
    "p_critical",
    "simulate",
    "stationary_step_scale",
    "xi_two_heuristics",
]


def p_critical(rho: float, kappa: float) -> float:
    """`p_c = log(1/rho) / log(kappa/rho)`: where `E log a = 0` and the error stops being stationary."""
    if not 0 < rho < 1:
        raise ValueError(f"rho must lie in (0, 1); got {rho}")
    if kappa <= 1:
        raise ValueError(f"kappa must exceed 1; got {kappa}")
    return float(np.log(1.0 / rho) / np.log(kappa / rho))


def lyapunov_exponent(p: float, rho: float, kappa: float) -> float:
    """`E log a = (1-p) log rho + p log kappa`; a stationary solution needs this to be negative."""
    return float((1.0 - p) * np.log(rho) + p * np.log(kappa))


def alpha_two_heuristics(p: float, rho: float = 0.7, kappa: float = 2.5) -> float:
    """The unique positive root of `(1-p) rho^a + p kappa^a = 1` (Theorem 5(v)).

    Returns `inf` at `p = 0`, where the map is uniformly contractive and no root exists: that is
    the light-tailed case `xi = 0` of Theorem 5(iii), not a numerical failure. Returns `0.0` at
    and beyond `p_c`, where `alpha(p) -> 0`.
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must lie in [0, 1]; got {p}")
    if p == 0.0:
        return float("inf")
    if p >= p_critical(rho, kappa):
        return 0.0

    def moment_equation(a: float) -> float:
        return (1.0 - p) * rho**a + p * kappa**a - 1.0

    # moment_equation(0) = 0 and the derivative at 0 is E log a < 0, so the function dips below
    # zero and comes back up; the root is bracketed once the upper end has turned positive.
    hi = 1.0
    while moment_equation(hi) < 0.0:
        hi *= 2.0
        if hi > 1e6:  # pragma: no cover - unreachable for p < p_c
            raise RuntimeError(f"no root bracketed for p={p}, rho={rho}, kappa={kappa}")
    lo = 1e-12
    return float(optimize.brentq(moment_equation, lo, hi, xtol=1e-14, rtol=1e-15))


def xi_two_heuristics(p: float, rho: float = 0.7, kappa: float = 2.5) -> float:
    """The order parameter `xi(p) = 1/alpha(p)`; `0` at `p = 0`, increasing, diverging at `p_c`."""
    a = alpha_two_heuristics(p, rho, kappa)
    if not np.isfinite(a):
        return 0.0
    return float("inf") if a <= 0 else float(1.0 / a)


def stationary_step_scale(rho: float) -> float:
    """Std-dev multiplier of a step deviation in the contractive case, `sqrt(2/(1+rho))`.

    With `a = rho` deterministic, `E_t - E_{t-1} = (rho-1) E_{t-1} + B_t` and the stationary
    `E_{t-1}` has covariance `Sigma/(1-rho^2)`, so the increment has covariance
    `Sigma * 2/(1+rho)`. Theorem 5(iii)'s bound `s_rho^2 = (2-rho^2)/(1-rho^2)` is the looser
    envelope that also covers a random `a`; this is the exact value used to check the simulation.
    """
    return float(np.sqrt(2.0 / (1.0 + rho)))


@dataclass
class KestenTraces:
    """Simulated traces for one off-support rate `p`, in the shape the estimators consume."""

    p: float
    z: np.ndarray  # (n_traces, n_steps) step deviations
    a: np.ndarray  # (n_traces, n_steps) realised multipliers, for mechanism diagnostics
    rho: float
    kappa: float
    d: int
    sigma: float
    seed: int
    alpha_theory: float
    xi_theory: float
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def n_traces(self) -> int:
        return int(self.z.shape[0])

    @property
    def n_steps(self) -> int:
        return int(self.z.shape[1])

    def pooled(self) -> tuple[np.ndarray, np.ndarray]:
        """`(z, trace_id)` flattened for `estimate_tail`, which resamples whole traces."""
        m, ell = self.z.shape
        return self.z.ravel(), np.repeat(np.arange(m), ell)

    def tolerance(self, quantile: float) -> float:
        """`tau`, the tolerance of Hypothesis 1, as a quantile of this setting's own deviations."""
        return float(np.quantile(self.z, quantile))

    def first_exceedance(self, tau: float) -> np.ndarray:
        """`t*` per trace, or `-1` for a trace that never exceeds `tau` (a "verified" trace).

        Under Hypothesis 1, `v_t = 1{Z_t <= tau}` up to and including the first rejected step,
        so the first exceedance *is* the first rejected step and chain failure is `M_L > tau`.
        """
        over = self.z > tau
        any_over = over.any(axis=1)
        return np.where(any_over, over.argmax(axis=1), -1)

    def argmax_step(self) -> np.ndarray:
        """`T^max`, the smallest index attaining the per-trace maximum (Theorem 4)."""
        return self.z.argmax(axis=1)


def simulate(
    p: float,
    cfg: KestenConfig | None = None,
    *,
    seed: int | None = None,
    rho: float | None = None,
    kappa: float | None = None,
    d: int | None = None,
    n_traces: int | None = None,
    n_steps: int | None = None,
    burn_in: int | None = None,
    sigma: float | None = None,
) -> KestenTraces:
    """Draw `n_traces` independent trajectories of the recurrence at off-support rate `p`.

    Traces are burnt in for `burn_in` steps so that `E_0` is drawn from the stationary law of
    Theorem 5(i) rather than from an arbitrary start; without that the first steps carry a
    transient that the tail estimators would read as structure.
    """
    cfg = cfg or KestenConfig()
    rho = cfg.rho if rho is None else rho
    kappa = cfg.kappa if kappa is None else kappa
    d = cfg.d if d is None else d
    m = cfg.n_traces if n_traces is None else n_traces
    ell = cfg.n_steps if n_steps is None else n_steps
    burn = cfg.burn_in if burn_in is None else burn_in
    sigma = cfg.sigma if sigma is None else sigma
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must lie in [0, 1]; got {p}")

    # One generator per (config, p) so that settings are independent but each is reproducible.
    base = cfg.seed if seed is None else seed
    rng = np.random.default_rng([int(base), round(float(p) * 1e6)])

    e = rng.normal(scale=sigma, size=(m, d))
    for _ in range(burn):
        a = np.where(rng.random(m) < p, kappa, rho)[:, None]
        e = a * e + rng.normal(scale=sigma, size=(m, d))

    z = np.empty((m, ell), dtype=np.float64)
    a_rec = np.empty((m, ell), dtype=np.float64)
    for t in range(ell):
        a = np.where(rng.random(m) < p, kappa, rho)
        a_rec[:, t] = a
        e_next = a[:, None] * e + rng.normal(scale=sigma, size=(m, d))
        z[:, t] = np.linalg.norm(e_next - e, axis=1)
        e = e_next

    return KestenTraces(
        p=float(p),
        z=z,
        a=a_rec,
        rho=float(rho),
        kappa=float(kappa),
        d=int(d),
        sigma=float(sigma),
        seed=int(base),
        alpha_theory=alpha_two_heuristics(p, rho, kappa),
        xi_theory=xi_two_heuristics(p, rho, kappa),
        meta={
            "burn_in": int(burn),
            "p_critical": p_critical(rho, kappa),
            "lyapunov": lyapunov_exponent(p, rho, kappa),
        },
    )
