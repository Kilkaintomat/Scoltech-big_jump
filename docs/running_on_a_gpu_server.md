# Running this repository on a GPU server

What was checked, what works, and what is still missing. Verified by resolving the lockfile
against `x86_64-unknown-linux-gnu`, not by assumption.

## Setup

```bash
git clone <repo> && cd Scoltech-big_jump
curl -LsSf https://astral.sh/uv/install.sh | sh          # if uv is absent
uv sync --python 3.11 --extra stats --extra viz --extra ml --extra dev
uv run onebigjump doctor                                  # confirms CUDA is seen
./scripts/setup_lean.sh                                   # ~8 GB, no sudo, user space
uv run onebigjump lean-doctor
make test
```

Add `--extra inference` to install `vllm` for sampling. It is behind a
`sys_platform == 'linux'` marker and is the reason it is not in the default set.

## What was verified

| Check | Result |
|---|---|
| `uv sync --frozen --python-platform x86_64-unknown-linux-gnu` with `stats,viz,ml,dev` | resolves from the committed lock |
| CUDA stack pulled | 15 `nvidia-*` packages plus `triton`, i.e. the CUDA build of torch 2.13 |
| `--extra inference` (vllm) | resolves on the same platform |
| macOS-specific paths in `src/`, `scripts/`, `configs/`, `Makefile` | none |
| Device selection | `cuda` before `mps` before `cpu`; the MPS probe is guarded and is safe where the backend is absent |
| Lean toolchain | `elan` installs on Linux in user space; the toolchain and `lake-manifest.json` are committed, so the Mathlib revision is the one the labels were produced against |

### The one hard requirement to check before booking a machine

The lock pins the **CUDA 13** runtime (`nvidia-cuda-runtime==13.0.96`,
`nvidia-cudnn-cu13`, `nvidia-nccl-cu13`). That needs an NVIDIA driver of the 580 series or
newer. On an older driver the install succeeds and `torch.cuda.is_available()` then returns
false, so check it before anything else:

```bash
nvidia-smi --query-gpu=driver_version,memory.total --format=csv
uv run python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
```

If the driver is older, pin an earlier torch in `pyproject.toml` and re-lock; nothing else in the
repository depends on the torch version.

## The full pipeline

```bash
# 1. sample whole proofs -- no verifier in the loop (Section 2)
uv run onebigjump run configs/models/prover_sampling.yaml

# 2. label every tactic with the Lean 4 kernel (Appendix B.2)
uv run onebigjump lean-verify data/raw/prover-sampling/samples.jsonl \
    --out-dir results/full/lean

# 3. read the residual streams, build the table, run P1-P5 (Appendix B.1, Section 5)
uv run onebigjump run configs/models/extract_activations.yaml

# 4. assemble the report
uv run onebigjump report
```

Stage 1 is the only one that wants the GPU badly; stage 3 wants it too, but less. Stage 2 is
CPU-bound in the Lean kernel and is usually the wall-clock bottleneck for a large batch.

`configs/models/prover_sampling.yaml` points `problems` at a JSONL of theorem statements or a
Hugging Face dataset id. **Nothing here downloads a benchmark**: which of miniF2F-test, ProofNet
and PutnamBench the paper finally uses is one of its open placeholders, so the choice is left to
whoever runs it. The loader accepts the field spellings those datasets actually use
(`formal_statement`, `statement`, `goal`, `name`, `id`).

Prompts are per model family, not guessed: a prover fine-tuned on one template produces very
different output under another, and the mismatch surfaces as a wall of parse errors rather than
as an error message. Templates for the DeepSeek, Goedel and Kimina families are in
`lean/problems.py`; add yours there rather than editing the config.

## What runs without a GPU

| Command | GPU helps? |
|---|---|
| `make figure1` | no -- pure NumPy, ~6 min |
| `uv run onebigjump analyse-kesten` | no |
| `make lean-verify` | no -- the Lean kernel is CPU-bound |
| `make p4` | somewhat: 20-35 min per seed on an M4 |
| `make test-all` | no |

## Two things that will bite on a first real run

**The whitening needs a big calibration split.** `(mu, Sigma)` is fitted on verified traces of a
disjoint problem split, and a residual stream of width `d` needs on the order of `2d` increments
before the fit is determined. At `d = 4096` and ~10 steps per trace that is several hundred
verified traces in the *held-out* half alone. Below that the fit is refused, the run continues
with the raw statistic, and both the log and the manifest say so -- it does not silently return a
statistic with no spread left. If `whitened` and `innovation` are missing from your table, that
is why.

**A prover that proves nothing gives you no calibration.** The split prefers problems with at
least one verified trace, but if the model verifies nothing there is nothing to fit on. Check the
verified count from stage 2 before running stage 3.

## Memory

An 8B model in bfloat16 is about 16 GB of weights, so a 24 GB card is the practical floor for
Section 5.1 and 40 GB is comfortable. Sampling and extraction load the model separately, in two
runs, so they never have to share a card. The activations themselves are negligible: three read-out
layers times `(L+1)` positions times `d` in float32 is a few megabytes per trace. The binding
constraint is the model, not the extraction -- which is why `hooks.py` keeps only the requested
token positions rather than whole `(batch, seq, d)` tensors.

## Reproducibility on the new machine

Run from a **clean** working tree. Every run records the commit and whether the tree was dirty,
and a figure produced from a dirty tree cannot be regenerated from any commit; the report marks
those. See [`reproducibility.md`](reproducibility.md).
