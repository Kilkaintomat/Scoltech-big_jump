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

## What will run, and whether the GPU helps

| Command | Runs? | Does the GPU help? |
|---|---|---|
| `make figure1` | yes | no -- pure NumPy, ~6 min |
| `uv run onebigjump analyse-kesten` | yes | no |
| `make lean-verify` | yes | no -- the Lean kernel is CPU-bound |
| `make p4` | yes | somewhat: 20-35 min per seed on an M4; a GPU shaves it, but this is a `d=128` one-layer model |
| `make test-all` | yes | no |

**So a GPU buys almost nothing on what exists today.** That is not an accident of tuning: the
stages that need one are the stages that were never written, because they could not be tested on
the machine this was built on.

## What is missing before the GPU is worth having

The paper's GPU-bound work is Section 5.1 (prover traces) and Section 5.2 (synthetic deduction on
7-8B models). Neither can run yet.

| Missing | What it would have to do |
|---|---|
| `src/onebigjump/models/generation.py` | sample whole proofs from a prover with vLLM or HF `generate`, and write the JSONL that `onebigjump lean-verify` already reads |
| Benchmark acquisition | nothing in the repository mentions miniF2F, ProofNet or PutnamBench; the theorem statements have to come from somewhere |
| An extraction driver | load the model onto the device, teacher-force each labelled trace, fit the calibration on a **disjoint** verified split, and build the table. The pieces exist and are tested (`extract_trajectory`, `fit_calibration`, `from_traces`); what is absent is the loop that wires them together |
| `configs/models/`, `configs/synthetic/` | empty |
| CLI dispatch for `generate`, `activations`, `synthetic` | declared in `config.py` as valid `kind` values but not wired in `cli.py`, so `onebigjump run` on such a config exits with code 2 |

Everything downstream of that is done and tested: verification, the three deviation statistics,
P1-P5, the tables, the figures and the report.

## Memory, once those exist

An 8B model in bfloat16 is about 16 GB of weights, so a 24 GB card is the practical floor for
Section 5.1 and 40 GB is comfortable. The activations themselves are negligible: three read-out
layers times `(L+1)` positions times `d` in float32 is a few megabytes per trace. The binding
constraint is the model, not the extraction -- which is why `hooks.py` keeps only the requested
token positions rather than whole `(batch, seq, d)` tensors.

## Reproducibility on the new machine

Run from a **clean** working tree. Every run records the commit and whether the tree was dirty,
and a figure produced from a dirty tree cannot be regenerated from any commit; the report marks
those. See [`reproducibility.md`](reproducibility.md).
