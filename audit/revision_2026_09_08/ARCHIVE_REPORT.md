> Historical archive rendered on Zhores with the corrected reporter. See REPORT.md for limitations.

# Experimental report

Generated 2026-09-08 14:56:31Z by `uv run onebigjump report`. Every number below is read from a metrics file written by a run; none is entered by hand.

A negative or inconclusive result is reported as one. Sections whose run has not happened say so rather than being omitted.

## Figure 1 -- the dichotomy on the heuristic mixture

Setting from the caption: `rho = 0.7`, `kappa = 2.5`, `d = 8`, 3000 traces of 64 steps, tolerance at the 99.9% quantile. `p_c = 0.2802`.

| `p` | `alpha` theory | `xi` theory | Hill [95% CI] | moment | GPD | refuted | top-1 | chance |
|---|---|---|---|---|---|---|---|---|
| 0.00 | inf | 0.0000 | 0.0788 [0.0773, 0.0801] | -0.1033 | -0.1064 | 184 | 0.984 | 0.0156 |
| 0.02 | 3.9734 | 0.2517 | 0.2610 [0.2523, 0.2711] | +0.1522 | +0.1390 | 144 | 0.903 | 0.0156 |
| 0.05 | 2.7992 | 0.3572 | 0.3472 [0.3379, 0.3587] | +0.3109 | +0.2927 | 130 | 0.846 | 0.0156 |
| 0.10 | 1.8193 | 0.5497 | 0.5221 [0.5088, 0.5368] | +0.5375 | +0.5445 | 75 | 0.680 | 0.0156 |
| 0.15 | 1.1788 | 0.8483 | 0.8500 [0.8127, 0.8913] | +0.8415 | +0.8471 | 48 | 0.646 | 0.0156 |
| 0.20 | 0.6745 | 1.4825 | 1.5356 [1.4625, 1.6206] | +1.5309 | +1.5354 | 15 | 0.200 | 0.0156 |

Run `figure1-kesten` at commit `905d85c1` (clean), 385s, status `ok`.

## Lean 4 verification -- exact step labels

### `lean`

Toolchain `leanprover/lean4:v4.34.0-rc2`, Mathlib `85e3a25e`.

| category | count |
|---|---|
| n_traces | 10 |
| verified | 4 |
| refuted | 5 |
| parse_error_discarded | 1 |
| timeout | 0 |
| repl_failure | 0 |
| n_steps_total | 15 |
| mean_trace_length | 1.667 |
| mean_t_star | 0.600 |
| elapsed_s | 0.439 |

Whole-proof compilation and step replay disagree on **0** traces. Appendix B.2 requires them to agree by construction; `sorry` is the one documented exception and is excluded from the count.

Run `lean-verify-pilot` at commit `b22446a9` (clean), 211s, status `ok`.

## P4 -- the order parameter across the grokking transition

Signed gamma is the moment estimate; xi = max(gamma, 0). Hill is a diagnostic.

Archived gamma_* summaries may use Hill and are not used below. The presence of training metrics does not establish P4 or certify their provenance.

### `grokking/p4_grokking_seed0.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 0 | 23600 | 1.000 | -0.0443 | -0.1955 | 0.0404 |

Maximum estimated xi: 0.0772. Positive at 30/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

_No manifest found for this run._

### `grokking/p4_grokking_seed1.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 1 | 23700 | 1.000 | +0.0479 | -0.1611 | 0.0329 |

Maximum estimated xi: 0.0479. Positive at 4/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

_No manifest found for this run._

### `grokking/p4_grokking_seed2.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 2 | 13500 | 1.000 | +0.0015 | -0.1751 | 0.0257 |

Maximum estimated xi: 0.0015. Positive at 1/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

Run `p4-grokking-seed2` at commit `ab2384be` (clean), 2088s, status `ok`.

### `grokking_cpu/p4_grokking_seed0.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 0 | 18800 | 1.000 | -0.0443 | -0.1259 | 0.0318 |

Maximum estimated xi: 0.1182. Positive at 5/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

Run `p4-grokking-seed0` at commit `unknown` (**unknown provenance -- reproducibility unverified**), 1669s, status `ok`.

### `grokking_cuda/p4_grokking_seed0.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 0 | 21900 | 1.000 | -0.0443 | -0.1359 | 0.0282 |

Maximum estimated xi: 0.1182. Positive at 5/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

_No manifest found for this run._

### `grokking_cuda/p4_grokking_seed1.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 1 | 21300 | 1.000 | +0.0479 | -0.2990 | 0.0208 |

Maximum estimated xi: 0.0496. Positive at 6/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

_No manifest found for this run._

### `grokking_cuda/p4_grokking_seed2.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 2 | 15100 | 1.000 | +0.0015 | -0.2069 | 0.0310 |

Maximum estimated xi: 0.0015. Positive at 1/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

Run `p4-grokking-seed2` at commit `unknown` (**unknown provenance -- reproducibility unverified**), 512s, status `ok`.

### `grokking_null/p4_grokking_seed0.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 0 | **never** | 0.009 | -0.0443 | -0.2228 | 0.0370 |

Maximum estimated xi: 0.0000. Positive at 0/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

_No manifest found for this run._

### `grokking_null/p4_grokking_seed1.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 1 | **never** | 0.011 | +0.0479 | -0.1371 | 0.0395 |

Maximum estimated xi: 0.0479. Positive at 6/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

_No manifest found for this run._

### `grokking_null/p4_grokking_seed2.json`

| seed | grokking step | final test acc | moment first | moment last | Hill last |
|---|---|---|---|---|---|
| 2 | **never** | 0.009 | +0.0015 | -0.1652 | 0.0428 |

Maximum estimated xi: 0.0015. Positive at 1/401 checkpoints.

Legacy progress losses: require recomputation after the Fourier-mask correction.

Run `p4-grokking-seed2` at commit `unknown` (**unknown provenance -- reproducibility unverified**), 335s, status `ok`.

## What could not be run here, and why

Run availability below is inferred from saved artifacts. Hardware must be read from each run manifest; a local machine report does not describe the cluster.

| Stage | Status |
|---|---|
| Kesten simulation, Figure 1 | run |
| Estimators, bootstrap, tests | **not run** |
| Lean 4 + Mathlib step replay | run |
| Modular-addition grokking (P4) | run |
| Prover traces from DeepSeek-Prover-V2-7B, Goedel-8B, Kimina-8B | **not run** |
| Synthetic deduction on 7-8B general models | **not run**: the synthetic deduction pipeline is not implemented |

No result from those stages is estimated, extrapolated or filled in. The placeholders in `docs/experimental_specification.md` section 7 that they would have filled remain placeholders.
