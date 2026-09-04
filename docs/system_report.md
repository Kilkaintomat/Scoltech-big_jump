# System report

Generated: 2026-09-04T13:59:02Z on `MacBook-Pro-den.local`.
Regenerate with `uv run python scripts/doctor.py --write-report`.

## Platform

```
uname -a           : Darwin MacBook-Pro-den.local 24.5.0 Darwin Kernel Version 24.5.0: Tue Apr 22 19:54:43 PDT 2025; root:xnu-11417.121.6~2/RELEASE_ARM64_T8132 arm64
sw_vers            : ProductName:		macOS ProductVersion:		15.5 BuildVersion:		24F74 
arch               : arm64
cpu                : Apple M4
physical cores     : 10
logical cores      : 10
RAM bytes          : 17179869184
```

## Disk

```
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   926Gi    14Gi   559Gi     3%    426k  4.3G    0%   /
```

## Toolchain

```
python3      /opt/homebrew/Caskroom/miniconda/base/envs/myenv/bin/python3
git          /usr/bin/git
uv           /opt/homebrew/Caskroom/miniconda/base/bin/uv
cmake        NOT FOUND
ninja        NOT FOUND
gh           /opt/homebrew/bin/gh
elan         NOT FOUND
lean         NOT FOUND
lake         NOT FOUND
sbatch       NOT FOUND
srun         NOT FOUND
sinfo        NOT FOUND
docker       NOT FOUND
apptainer    NOT FOUND
singularity  NOT FOUND
nvidia-smi   NOT FOUND
nvcc         NOT FOUND
```

## Versions

```
python3 : Python 3.11.11
git     : git version 2.39.5 (Apple Git-154)
uv      : uv 0.11.24 (5e04460c0 2026-06-23 aarch64-apple-darwin)
gh      : gh version 2.95.0 (2026-06-17)
cmake   : (eval):40: command not found: cmake
```

## Project Python environment

```
python  : 3.11.15 arm64
numpy         : 2.3.5
scipy         : 1.17.1
pandas        : 3.0.5
pyarrow       : 25.0.1
pydantic      : 2.13.5
yaml          : 6.0.3
typer         : 0.27.2
rich          : ?
sklearn       : 1.9.0
statsmodels   : 0.15.0
matplotlib    : 3.11.1
seaborn       : 0.13.2
torch         : 2.13.0
transformers  : 5.16.1
accelerate    : 1.14.0
datasets      : 5.0.1
tokenizers    : 0.23.2
safetensors   : 0.8.0
einops        : 0.8.2

torch.cuda.is_available       : False
torch.backends.mps.is_available: True
torch.backends.mps.is_built    : True
```

## Credentials

```
gh auth status : You are not logged into any GitHub hosts. To log in, run: gh auth login
HF token file  : absent
HF_TOKEN env   : unset
```

## Verdict

| Resource | Status |
|---|---|
| OS | macOS 15.5 (Darwin 24.5.0), arm64 |
| CPU | Apple M4, 10 cores |
| RAM | 16 GiB unified |
| Free disk | 559 GiB |
| GPU | Apple integrated (Metal). **No NVIDIA, no CUDA, no `nvidia-smi`/`nvcc`.** |
| GPU RAM | shared with system RAM (16 GiB total) |
| NVIDIA driver | n/a |
| CUDA runtime | n/a |
| Slurm | **absent** (`sbatch`/`srun`/`sinfo` not found) — no partitions to query |
| Containers | **absent** (no docker/apptainer/singularity) |
| GitHub CLI | present (2.95.0), **not authenticated** |
| Hugging Face credentials | **absent** |
| Lean | **absent** (`elan`/`lean`/`lake` not found) |
| Torch backend | MPS available and built; CUDA unavailable |

### Consequences for the protocol

1. **`vllm` cannot be installed** — it is Linux+CUDA only. It is declared as an optional extra with
   an `sys_platform == 'linux'` marker and is deliberately excluded from `--all-extras` here.
   Sampling, where it happens at all on this machine, uses HuggingFace `generate`.
2. **`flash-attn` cannot be installed** — CUDA only. Not declared.
3. **No Slurm** ⇒ `scripts/slurm/` holds submission scripts for a future cluster but nothing is
   dispatched locally; all runs are driven by the CLI.
4. **16 GiB unified memory** is the binding constraint for the 7–8B prover experiments of
   Section 5.1: an 8B model in bf16 is ~16 GB of weights alone, before activations and the KV cache.
   Teacher-forced activation extraction over thousands of proofs is not tractable here.
   See `docs/experimental_specification.md` §8 for the resulting execution order.
5. **`cmake`/`ninja` absent** — not needed for the pure-Python path; would be needed only for a
   source build of a CUDA extension, which is out of scope on this machine.
6. Lean 4 + Mathlib **is** feasible: `elan` installs into user space and Mathlib ships a binary cache,
   so the REPL step-replay pipeline of Appendix B.2 can run on CPU.
