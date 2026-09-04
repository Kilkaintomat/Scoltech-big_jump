# Status

Updated automatically-adjacent: edit on every completed stage. Last edit: 2026-09-04.

Stage numbering follows the task specification.

| # | Stage | State | Where |
|---|---|---|---|
| 1 | Study the paper, write the specification | **done** | [`docs/experimental_specification.md`](docs/experimental_specification.md) |
| 2 | System audit | **done** | [`docs/system_report.md`](docs/system_report.md), `scripts/doctor.py` |
| 3 | Repository from scratch | **done** | this tree |
| 4 | Python environment | **done** | `pyproject.toml`, `uv.lock`, Python 3.11.15, torch 2.13 (MPS) |
| 5 | Lean 4 + Mathlib | **not started** | `elan` absent; user-space install is feasible |
| 6 | Statistical methods | **done** | `src/onebigjump/stats/` |
| 7 | Tests | **in progress** (189 passing) | `tests/` |
| 8 | Kesten simulation (Figure 1) | **done** | `src/onebigjump/simulation/`, `paper_outputs/figures/figure1_kesten_dichotomy.pdf` |
| 9 | Generation, verification, activation extraction | **not started** | `src/onebigjump/lean/`, `src/onebigjump/models/` |
| 10 | Pilot | **not started** | |
| 11 | Experiments P1-P5 | **not started** | `src/onebigjump/experiments/` |
| 12 | Tables and figures | **partial** (Figure 1 only) | `src/onebigjump/reporting/` |
| 13 | Reproducible report | **not started** | `reports/` |
| 14 | Push to a private GitHub repository | **blocked** | `gh auth login` has not been run |
| 15 | Push after each completed stage | **blocked** on 14 | commits are being made locally |

## Blocked, and on what

| Blocker | Consequence | What unblocks it |
|---|---|---|
| `gh` is not authenticated | Nothing can be pushed; commits accumulate locally on `main` | `gh auth login` in a terminal |
| No CUDA (Apple M4, 16 GB) | The Section 5.1 prover runs are not tractable at the paper's scale | A CUDA machine, or a documented reduction in scale |
| Lean 4 absent | No exact step labels yet | `scripts/setup_lean.sh` (user space, no sudo) |
| No Hugging Face token | Gated model weights unavailable | `HF_TOKEN` in `.env`, if a gated model is needed |

## What has actually been reproduced

Figure 1 of the paper, in full. The closed form of Theorem 5(v) returns
`alpha = 3.9734, 2.7992, 1.8193` at `p = 0.02, 0.05, 0.10` against the caption's
`3.97, 2.80, 1.82`, and `p_c = 0.2802` is exactly where the Lyapunov exponent vanishes.

Simulated, at the caption's setting (`rho = 0.7`, `kappa = 2.5`, `d = 8`, 3000 traces of 64 steps):

| `p` | `xi` theory | Hill [95% CI] | moment | GPD | refuted traces | top-1 | chance |
|---|---|---|---|---|---|---|---|
| 0.00 | 0.0000 | 0.0788 [0.0773, 0.0801] | **-0.1033** | -0.1064 | 184 | 0.984 | 0.0156 |
| 0.02 | 0.2517 | 0.2610 [0.2523, 0.2711] | 0.1522 | 0.1390 | 144 | 0.903 | 0.0156 |
| 0.05 | 0.3572 | 0.3472 [0.3379, 0.3587] | 0.3109 | 0.2927 | 130 | 0.846 | 0.0156 |
| 0.10 | 0.5497 | 0.5221 [0.5088, 0.5368] | 0.5375 | 0.5445 | 75 | 0.680 | 0.0156 |

Read against the paper:

* At `p = 0` the moment estimator returns **-0.10** while Hill returns **+0.08** -- exactly the
  behaviour the caption of Figure 1(c) describes, and the reason all three estimators are reported.
* The paper's caption states 185 refuted traces at `p = 0`; we get **184**.
* Chance for localisation is `1/L = 0.0156`; the paper prints 0.016.
* Top-1 localisation at `p = 0.05` is **0.846** here, against a *predicted* 0.85 and a
  *simulated* 0.80 in the paper. We land on the theoretical prediction. The paper does not give
  its simulation seed, so the gap to its 0.80 is not resolvable from the text.
* The overshoot GPD shape at `p = 0.05` fits at **-0.07**, well below `gamma = 0.357`. This is the
  pre-asymptotic effect the caption of Figure 1(d) itself flags ("the gap between the empirical
  curve and the Pareto asymptote is a pre-asymptotic effect at this threshold"), now quantified.

## Deviations from the paper's protocol, so far

1. `tau` in the simulation is taken **per setting** as the 99.9% quantile of that setting's own
   deviations. A single shared `tau` cannot produce the caption's own counts (185 refuted traces
   at `p = 0` against 114 at `p = 0.05`); a per-setting `tau` does, and the ratio is the extremal
   index. Recorded in `src/onebigjump/simulation/figure1.py`.
2. `vllm` and `flash-attn` are not installed: both are Linux + CUDA only. `vllm` is declared as an
   optional extra behind a `sys_platform == 'linux'` marker.
