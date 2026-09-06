# One Big Jump — experimental pipeline

Code for the experimental section of *One Big Jump: Heavy Tails in Residual-Stream Reasoning
Trajectories as an Order Parameter for Algorithmic Computation* (ICLR 2027 submission).

**Private repository. No license is declared until the paper is public.**

## What the paper claims, and what this measures

A reasoning trace is a trajectory of residual-stream states `X_t`. The paper's claim is that the
extreme value index of the step deviations `Z_t = ||X_t - X_{t-1}||`,

```
xi = 1/alpha*,    alpha* = sup{ s > 0 : E Z^s < inf },
```

is an *order parameter*: `xi = 0` when the model implements an algorithm, `xi > 0` when it stitches
together heuristics. This repository estimates it and tests the five predictions that follow.

| | Prediction | State |
|---|---|---|
| P1 | Tail separation — refuted traces have a heavier tail than verified ones | implemented, validated against the closed form |
| P2 | Localization — the first rejected step is the largest jump | implemented, reproduces the paper's numbers |
| P3 | Overshoot — `Z_{t*}/tau` is Pareto-like, not concentrated at 1 | implemented; **see the finding below** |
| P4 | Order parameter — `xi` drops when a circuit forms during grokking | **run for real, on three seeds** |
| P5 | Length law — `P(V_L=1) ≈ exp(-theta L Fbar(tau))` | implemented; **see the finding below** |

## Three things the measurements say that the paper does not

These are the substantive output of the work so far, and they are recorded with the runs that
produced them in [`STATUS.md`](STATUS.md) and [`reports/experimental_report.md`](reports/experimental_report.md).

1. **P3 as written measures the wrong thing when steps cluster.** On the Kesten surrogate at
   `p = 0.05`, where `gamma = 0.357` exactly, the 99.9% threshold gives shape **+0.454** for the
   unconditional overshoot of Proposition 1 and **+0.478** for the trace maximum, but only
   **+0.127** for the first exceedance `Z_{t*}` — which is what P3 specifies. Figure 1(d)'s caption
   attributes the gap to pre-asymptotics; raising the threshold across two decades leaves it at
   0.06–0.13, so it is not that. The extremal index there is `theta = 0.13`: exceedances arrive in
   clusters and conditioning on the *first* selects smaller overshoots. Theorem 4(ii) derives its
   limit under extremal independence, which Theorem 5's own model violates. At `p = 0`, where
   `theta = 1.000`, all three variants agree to within 0.05.
2. **P5's `(theta, tau)` is not identified.** The likelihood depends on them only through
   `c = theta * Fbar(tau)`, so the fit is one-parameter and the likelihood-ratio test has
   `n_lengths - 1` degrees of freedom, not `n_lengths - 2`. Fixed by fitting `c` and pinning
   `theta` from the extremal index.
3. **Under the coupling hypothesis, P1 is partly true by selection.** A "verified" trace is
   *defined* as one whose maximum stayed below `tau`, so its deviations are truncated above. This
   affects the surrogate, not the Lean experiments, where "verified" means the kernel accepted the
   proof.

## What has been reproduced

**Figure 1, in full.** The closed form of Theorem 5(v) returns `alpha = 3.9734, 2.7992, 1.8193` at
`p = 0.02, 0.05, 0.10` against the caption's `3.97, 2.80, 1.82`; `p_c = 0.2802` is exactly where
the Lyapunov exponent vanishes; 184 refuted traces at `p = 0` against the caption's 185; top-1
localisation 0.846 at `p = 0.05` against a predicted 0.85.

**P4, on three seeds.** `gamma_hat` rises to a transient peak, then falls on the *same checkpoint*
as the turn in Nanda et al.'s excluded loss, 800–900 steps **before** the generalization jump. That
is more specific than P4 as stated: the order parameter tracks circuit formation, not the accuracy
that follows it. The timing replicates on a seed whose transition is ten thousand steps earlier;
the amplitude does not (peaks of 0.175, 0.180, 0.069).

## Layout

| Path | What lives there |
|---|---|
| [`docs/experimental_specification.md`](docs/experimental_specification.md) | the paper transcribed into a contract: every definition, estimator, protocol setting and placeholder |
| [`STATUS.md`](STATUS.md) | what is done, what is not, what the measurements disagree with, and every deviation from the protocol |
| [`docs/running_on_a_gpu_server.md`](docs/running_on_a_gpu_server.md) | **what to run on a GPU box**, verified by resolving the lock against Linux + CUDA |
| [`analysis_plan.yaml`](analysis_plan.yaml) | the decision rule for each prediction, fixed before the numbers existed |
| `src/onebigjump/stats/` | Hill, moment and GPD estimators, `k` selection, trace bootstrap, extremal index |
| `src/onebigjump/simulation/` | the Kesten surrogate of Theorem 5 and Figure 1 |
| `src/onebigjump/lean/` | REPL driver, tactic segmentation, exact per-step labels |
| `src/onebigjump/models/` | sampling, hooks, token alignment, deviation statistics, the extraction driver |
| `src/onebigjump/experiments/` | P1–P5, all reading one table ([`docs/data_schema.md`](docs/data_schema.md)) |
| [`AGENTS.md`](AGENTS.md) | conventions for anyone extending the code |

## Quick start

```bash
uv sync --extra stats --extra viz --extra ml --extra dev
uv run onebigjump doctor          # what this machine can and cannot run
make test                         # lint, typecheck, and the tests needing no toolchain
make figure1                      # reproduce Figure 1, ~6 min
make p4                           # the grokking experiment, ~20-35 min per seed
```

`./scripts/setup_lean.sh` installs Lean 4, Mathlib and the REPL in user space (~8 GB, no sudo).

## The full pipeline

```bash
uv run onebigjump run configs/models/prover_sampling.yaml       # sample whole proofs
uv run onebigjump lean-verify data/raw/prover-sampling/samples.jsonl \
    --out-dir results/full/lean                                  # exact per-step labels
uv run onebigjump run configs/models/extract_activations.yaml   # trajectories, table, P1-P5
uv run onebigjump report
```

Stage 1 needs a GPU: the smallest prover the paper names is 7B. Stage 2 is CPU-bound in the Lean
kernel and is usually the wall-clock bottleneck. See
[`docs/running_on_a_gpu_server.md`](docs/running_on_a_gpu_server.md) before starting.

## Reproducibility

No number in `paper_outputs/` is typed by a human. Every figure and table is rendered from a
metrics file written by a run that leaves a manifest recording the config, the seed, the git
commit and **whether the tree was dirty**, package versions, hardware, and a SHA-256 of every
output. A figure produced from a dirty tree cannot be regenerated from any commit, and the report
marks it rather than shipping it quietly. See [`docs/reproducibility.md`](docs/reproducibility.md).

A negative or inconclusive result is a valid outcome and is reported as one. Where a stage could
not run, the placeholders it would have filled remain placeholders.

## Tests

429 tests: 18 drive the real Lean 4 kernel, 29 drive real transformer activations, the rest are
pure. Toolchain-dependent tests are **skipped**, never silently passed — a run that could not check
the kernel labels must not look like a run that checked them.

```bash
make test        # everything that needs no external toolchain
make test-all    # the above plus the live Lean and GPT-2 tests
```
