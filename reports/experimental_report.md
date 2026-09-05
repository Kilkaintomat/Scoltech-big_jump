# Experimental report

Generated 2026-09-05 17:55:16Z by `uv run onebigjump report`. Every number below is read from a metrics file written by a run; none is entered by hand.

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

| seed | grokking step | final test acc | `gamma` peak | `gamma` after | peak-to-trough |
|---|---|---|---|---|---|
| 0 | 23600 | 1.000 | 0.1753 at step 22700 | 0.0388 | 0.0907 |
| 1 | 23700 | 1.000 | 0.1801 at step 22700 | 0.0457 | 0.0750 |
| 2 | 13500 | 1.000 | 0.0691 at step 12100 | 0.0362 | 0.0126 |

**Where the drop sits** (seed 0). P4 names two references and they are not the same step:

| event | step |
|---|---|
| sharpest fall in `gamma_hat` | 22800 |
| excluded loss half-transition | 22800 |
| test accuracy half-transition | 23200 |
| test accuracy crosses 0.9 | 23600 |
| restricted loss half-transition | 23700 |

The fall in `gamma_hat` lands on the **same checkpoint** as the turn in the excluded loss, and leads the generalization jump by 800 steps.

That ordering is the substantive part: the order parameter tracks circuit formation, which is what the progress measures detect, rather than the downstream accuracy that follows it.

Run `p4-grokking-seed2` at commit `ab2384be` (clean), 2088s, status `ok`.

## What could not be run here, and why

The machine is an Apple M4 with 16 GB of unified memory: no CUDA, no Slurm. See `docs/system_report.md`, which is generated from the machine rather than written.

| Stage | Status |
|---|---|
| Kesten simulation, Figure 1 | run |
| Estimators, bootstrap, tests | run |
| Lean 4 + Mathlib step replay | run |
| Modular-addition grokking (P4) | run |
| Prover traces from DeepSeek-Prover-V2-7B, Goedel-8B, Kimina-8B | **not run**: an 8B model in bfloat16 is ~16 GB of weights alone, before activations and the KV cache |
| Synthetic deduction on 7-8B general models | **not run**: same constraint; `vllm` is Linux + CUDA only |

No result from those stages is estimated, extrapolated or filled in. The placeholders in `docs/experimental_specification.md` section 7 that they would have filled remain placeholders.
