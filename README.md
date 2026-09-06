# One Big Jump — experimental pipeline

Heavy tails in residual-stream reasoning trajectories: an order parameter for algorithmic
computation. Code for the experimental section of the ICLR 2027 submission.

**Private repository. No license is declared until the paper is public.**

## What this is

A reasoning trace is a trajectory of residual-stream states `X_t`. This repository estimates the
extreme value index `ξ = 1/α*` of the step deviations `Z_t = ‖X_t − X_{t−1}‖` and tests the five
predictions P1–P5 of the paper:

| | Prediction |
|---|---|
| P1 | Tail separation — refuted traces have a heavier tail than verified ones |
| P2 | Localization — the first rejected step is the largest jump |
| P3 | Overshoot — `Z_{t*}/τ` is Pareto-like, not concentrated at 1 |
| P4 | Order parameter — `ξ̂` drops when a circuit forms during grokking |
| P5 | Length law — `P(V_L=1) ≈ exp(−θ L F̄(τ))` |

## Start here

- [`docs/experimental_specification.md`](docs/experimental_specification.md) — every definition,
  estimator, protocol setting and paper placeholder this repository has to fill.
- [`docs/system_report.md`](docs/system_report.md) — hardware audit and what it makes feasible.
- [`STATUS.md`](STATUS.md) — what is done, running, or blocked.
- [`docs/running_on_a_gpu_server.md`](docs/running_on_a_gpu_server.md) — running the pipeline on
  a Linux + CUDA box, verified by resolving the lock against that platform.

## Setup

```bash
uv sync --extra stats --extra viz --extra ml --extra dev
uv run onebigjump --help
```

The full pipeline, once Lean is installed (`./scripts/setup_lean.sh`):

```bash
uv run onebigjump run configs/models/prover_sampling.yaml      # sample whole proofs
uv run onebigjump lean-verify data/raw/prover-sampling/samples.jsonl \
    --out-dir results/full/lean                                 # exact per-step labels
uv run onebigjump run configs/models/extract_activations.yaml  # trajectories, table, P1-P5
uv run onebigjump report
```

Stage 1 needs a GPU for the 7-8B provers the paper uses; the rest does not. See
[`docs/running_on_a_gpu_server.md`](docs/running_on_a_gpu_server.md).

The source paper draft is expected at `docs/onebigjumpdraft.pdf` and is deliberately git-ignored.

## Reproducibility

No result in this repository is hand-entered. Every number in `paper_outputs/` is produced by a
recorded run with a pinned seed and an environment fingerprint; see
[`docs/reproducibility.md`](docs/reproducibility.md).

A negative or inconclusive result is a valid outcome and is reported as one.
