# Status

Last edit: 2026-09-04. Stage numbering follows the task specification.

## Stages

| # | Stage | State | Where |
|---|---|---|---|
| 1 | Study the paper, write the specification | **done** | [`docs/experimental_specification.md`](docs/experimental_specification.md) (430 lines) |
| 2 | System audit | **done** | [`docs/system_report.md`](docs/system_report.md), `scripts/doctor.py` |
| 3 | Repository from scratch | **done** | this tree |
| 4 | Python environment | **done** | Python 3.11.15, torch 2.13 (MPS), `uv.lock` pinned |
| 5 | Lean 4 + Mathlib | **done** | Lean 4.34.0-rc2, Mathlib `85e3a25e`, REPL built; 8.0 GB in `lean_workspace/` |
| 6 | Statistical methods | **done** | `src/onebigjump/stats/` (8 modules) |
| 7 | Tests | **done for what exists** | 325 tests: 294 pure, 18 driving the real Lean kernel, 13 driving real GPT-2 |
| 8 | Kesten simulation (Figure 1) | **done** | `paper_outputs/figures/figure1_kesten_dichotomy.pdf` |
| 9 | Generation / verification / extraction | **2 of 3** | verification and extraction done; **generation not written** |
| 10 | Pilot | **not started** | needs stage 9's generation half |
| 11 | Experiments P1-P5 | **4 of 5** | P1, P2, P3, P5 done and validated; **P4 (grokking) not written** |
| 12 | Tables and figures | **partial** | Figure 1 only; `reporting/tables.py` not written |
| 13 | Reproducible report | **not started** | `reports/` is empty |
| 14 | Push to a private GitHub repository | **blocked** | `gh auth login` has not been run |
| 15 | Push after each completed stage | **blocked on 14** | 6 commits waiting locally |

## What is missing, precisely

| Item | Why it is missing |
|---|---|
| `models/generation.py` | Sampling proofs needs a prover model; the smallest in the paper is 7B and does not fit in 16 GB. Writing an untested sampler would be a stub. |
| `experiments/p4_grokking.py` | Feasible here (one-layer transformer, `d=128`, `p=113`) but not yet written. **This is the largest remaining piece of real science.** |
| `reporting/tables.py` | Table 1 and Table 2 exist as records; only their LaTeX/Markdown rendering is absent. |
| `configs/{grokking,lean,models,synthetic}/` | Empty; only `configs/simulation/figure1.yaml` exists. |
| `AGENTS.md`, `Makefile`, `analysis_plan.yaml` | Requested in the tree, not written. |
| `docs/data_schema.md`, `docs/bootstrap_report.md` | Requested, not written. The schema is documented in `experiments/dataset.py` instead. |
| `src/onebigjump/schemas.py` | The requested top-level module; its content lives in `lean/schemas.py` and `experiments/dataset.py`. |

## Blocked, and on what

| Blocker | Consequence | What unblocks it |
|---|---|---|
| `gh` is not authenticated | 6 commits sit on local `main`; stages 14 and 15 cannot start | `gh auth login` in a terminal |
| No CUDA (Apple M4, 16 GB) | Section 5.1 prover runs are not tractable at the paper's scale | a CUDA machine, or a documented reduction in scale |
| No Hugging Face token | gated weights unavailable (not currently binding) | `HF_TOKEN` in `.env` |

## What has actually been reproduced or measured

### Figure 1, in full

The closed form of Theorem 5(v) returns `alpha = 3.9734, 2.7992, 1.8193` at `p = 0.02, 0.05, 0.10`
against the caption's `3.97, 2.80, 1.82`, and `p_c = 0.2802` is exactly where the Lyapunov
exponent vanishes. At the caption's setting (`rho = 0.7`, `kappa = 2.5`, `d = 8`, 3000 traces of
64 steps):

| `p` | `xi` theory | Hill [95% CI] | moment | GPD | refuted | top-1 | chance |
|---|---|---|---|---|---|---|---|
| 0.00 | 0.0000 | 0.0788 [0.0773, 0.0801] | **-0.1033** | -0.1064 | 184 | 0.984 | 0.0156 |
| 0.02 | 0.2517 | 0.2610 [0.2523, 0.2711] | 0.1522 | 0.1390 | 144 | 0.903 | 0.0156 |
| 0.05 | 0.3572 | 0.3472 [0.3379, 0.3587] | 0.3109 | 0.2927 | 130 | 0.846 | 0.0156 |
| 0.10 | 0.5497 | 0.5221 [0.5088, 0.5368] | 0.5375 | 0.5445 | 75 | 0.680 | 0.0156 |

The paper's caption states 185 refuted traces at `p = 0`; we get 184. Chance is `1/L = 0.0156`
against its printed 0.016. Top-1 at `p = 0.05` is 0.846 against a *predicted* 0.85 and a
*simulated* 0.80 in the paper.

### Three things the measurements say that the paper does not

1. **P3 as written does not measure the Pareto index when steps cluster.** At `p = 0.05`, where
   `gamma = 0.357` exactly, the 99.9% threshold gives shape **+0.454** for the unconditional
   overshoot of Proposition 1 and **+0.478** for the trace maximum, but only **+0.127** for the
   first exceedance `Z_{t*}`, which is what P3 specifies. Figure 1(d)'s caption attributes the
   gap to pre-asymptotics; raising the threshold across two decades leaves it at 0.06-0.13, so it
   is not that. The extremal index at those thresholds is `theta = 0.41` and `0.13`: exceedances
   arrive in clusters, and conditioning on the *first* one selects smaller overshoots.
   Theorem 4(ii) derives its limit under extremal independence, which Theorem 5's own model
   violates. At `p = 0`, where `theta = 1.000`, all three variants agree to within 0.05.

2. **P5's `(theta, tau)` is not identified.** The likelihood depends on them only through
   `c = theta * Fbar(tau)`, so the fit is one-parameter: a free search returned
   `theta = 0.178, tau = 4.385` where the labelling threshold was `7.871`. The likelihood-ratio
   test therefore has `n_lengths - 1` degrees of freedom, not `n_lengths - 2`. Fixed by fitting
   `c` and pinning `theta` from the extremal index.

3. **Under the coupling hypothesis, P1 is partly true by selection.** A "verified" trace is
   *defined* as one whose maximum stayed below `tau`, so its deviations are truncated above and
   its tail is light for reasons unrelated to the mechanism. This affects the surrogate, not the
   Lean experiments, where "verified" means the kernel accepted the proof.

### Bugs found by running against real systems, not by reading

| Where | What |
|---|---|
| Lean REPL | A tactic failing on a type mismatch returns a top-level `{"message": ...}` with **no** `proofState`, not a `messages` array. Reading only `messages` marked the step valid and replayed the rest against a stale state, turning refuted proofs into verified ones. |
| GPT-2 whitening | 12 increments in 768 dimensions gave whitened deviations 3.249, 3.249, 3.267, 3.269 -- a statistic with no variance left to have a tail. Now refused rather than silently flattening P1. |
| Shrinkage target | Shrinking towards `tr(S)/d * I` inflates low-variance coordinates under the massive-activation anisotropy whitening exists to remove: at 2500:1, an optimal intensity of 0.0011 left the whitened covariance at 0.81 instead of 1. Target is now `diag(S)`. |
| GPD profile fit | The search bracket scaled by the mean collapses as the mean diverges at `gamma -> 1`; it returned 0.74 for a true 0.90. Now bracketed in units of the median, where the optimum sits at `2^gamma - 1`. |
| P1 bootstrap | Resampling prompts collapses the interval to a point when there is one prompt, reading as impossible precision. Falls back to traces below 20 prompts. |
| `write_json` | `numpy.float64` subclasses `float`, so `json.dumps` wrote bare `NaN` tokens past the default hook, producing files no strict JSON reader accepts. |

## Deviations from the paper's protocol

1. `tau` in the simulation is per setting, not shared. A single `tau` cannot produce the caption's
   own counts (185 refuted at `p = 0` against 114 at `p = 0.05`); a per-setting `tau` does, and
   the ratio is the extremal index.
2. `vllm` and `flash-attn` are not installed: both are Linux + CUDA only.
3. The Lean REPL environment snapshot (`pickleTo`) was implemented, measured at 126.7s to restore
   against 129.0s to import, and removed. Timeouts now resynchronise by waiting for the late
   reply instead of restarting.
