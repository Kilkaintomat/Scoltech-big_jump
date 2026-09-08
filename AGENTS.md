# Working in this repository

Notes for anyone -- human or model -- extending this code.

## The one rule

**No number in `paper_outputs/` is typed by a human.** Every figure and table is rendered from a
metrics file, and every metrics file is written by a run that leaves a manifest beside it
recording the config, the git commit, whether the tree was dirty, package versions, hardware, and
a digest of every file produced. If you find yourself about to write a number into a table, stop
and write the run that produces it instead.

A negative or inconclusive result is a valid outcome and is reported as one. Do not tune until a
prediction comes out true.

## Where things are

| Path | What lives there |
|---|---|
| `docs/experimental_specification.md` | the paper, transcribed into a contract; read this first |
| `src/onebigjump/stats/` | the three estimators, `k` selection, trace bootstrap, extremal index |
| `src/onebigjump/simulation/` | the Kesten surrogate of Theorem 5 and Figure 1 |
| `src/onebigjump/lean/` | REPL driver, tactic segmentation, per-step labels |
| `src/onebigjump/models/` | hooks, token alignment, deviation statistics, the grokking model |
| `src/onebigjump/experiments/` | P1-P5, all reading one long table (`experiments/dataset.py`) |
| `src/onebigjump/reporting/` | figures and tables, rendered from metrics files |
| `STATUS.md` | what is done, what is not, and what the measurements disagree with |

## Conventions that are not negotiable

* **The paper's `xi` is not its `xi_t`.** The paper writes `xi` for both the increment
  `X_t - X_{t-1}` and the order parameter `1/alpha*`. Here the increment is `increment` and the
  order parameter is `xi` or `gamma`. Never overload.
* **`xi = max(gamma, 0)`.** A negative extreme value index means bounded support, which is still
  `xi = 0`: algorithmic. Do not clip the estimate before reporting it -- a negative moment
  estimate is the positive evidence for `H_alg`.
* **Report all three estimators.** Hill is the most efficient under `H_heur` but cannot return a
  nonpositive value; only the moment and GPD estimators can reject `H_heur`.
* **Traces are the resampling unit**, prompts when several traces share one -- but not below 20
  distinct prompts, where the interval collapses to a point.
* **Labels are absorbing.** After `t*` every label is 0 and every step is marked `unreached`,
  because it was never run. `dataset.validate_table` enforces this.

## Before committing

```bash
make test        # ruff, mypy, and the tests that need no external toolchain
make test-all    # the above plus the live Lean and GPT-2 tests
```

Tests that need Lean or torch are **skipped**, never silently passed: a run that could not check
the kernel labels must not look like a run that checked them.

## What is deliberately not here

* `vllm` and `flash-attn`: Linux + CUDA only.
* Sampling from a prover model: the smallest in the paper is 7B and does not fit in 16 GB. See
  `docs/system_report.md` for what this machine can and cannot run.

## Working environment (user instruction, 2026-09-08)

The working repository is on Zhores at `/beegfs/home/denis.rakhmankin/onebigjump`.
Perform all further edits and tests on the server. Do not run local experiments or tests.
Use the existing `zhores` SSH alias without changing SSH/VPN settings.
Submit tests and computation through Slurm; keep login-node work to file and job management.
