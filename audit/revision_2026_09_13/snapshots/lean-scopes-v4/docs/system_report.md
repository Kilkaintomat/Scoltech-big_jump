# System report

Generated: 2026-09-04T14:29:09Z on `MacBook-Pro-den.local`.
Regenerate with `uv run python scripts/doctor.py --write`.

## Platform

```
platform       : macOS-15.5-arm64-arm-64bit
machine        : arm64
cpu cores      : 10
RAM (GB)       : 17.18
python         : 3.11.15
```

## Toolchain

```
python3        /Users/den/work/Scoltech-big_jump/.venv/bin/python3
git            /usr/bin/git
uv             /opt/homebrew/Caskroom/miniconda/base/bin/uv
cmake          NOT FOUND
ninja          NOT FOUND
gh             /opt/homebrew/bin/gh
elan           NOT FOUND
lean           NOT FOUND
lake           NOT FOUND
sbatch         NOT FOUND
srun           NOT FOUND
sinfo          NOT FOUND
docker         NOT FOUND
apptainer      NOT FOUND
singularity    NOT FOUND
nvidia-smi     NOT FOUND
nvcc           NOT FOUND
```

## Project Python environment

```
accelerate     1.14.0
datasets       5.0.1
matplotlib     3.11.1
numpy          2.3.5
pandas         3.0.5
pyarrow        25.0.1
pydantic       2.13.5
scikit-learn   1.9.0
scipy          1.17.1
statsmodels    0.15.0
tokenizers     0.23.2
torch          2.13.0
transformers   5.16.1

torch.cuda.is_available        : False
torch.backends.mps.is_available: True
GPUs                           : []
```

## Credentials

```
gh auth status : -
HF token file  : absent
```

## Verdict

| Resource | Status |
|---|---|
| OS | macOS-15.5-arm64-arm-64bit |
| CPU | 10 cores |
| RAM | 17.2 GB |
| GPU / CUDA | **no CUDA** |
| MPS | True |
| Slurm | **absent** |
| Lean | **absent** |
| GitHub CLI | present |

### What this machine can run

| Stage | Feasible | Note |
|---|---|---|
| Kesten simulation and Figure 1 | yes | pure NumPy |
| Tail estimators, bootstrap, tests | yes | CPU |
| Lean 4 + Mathlib step replay | **no** | install elan in user space |
| Modular-addition grokking (P4) | yes | small model; MPS or CPU |
| Synthetic deduction on 7-8B models | **no** | 16 GB is marginal for bf16 |
| Lean prover traces from 7-8B provers | **no** | needs CUDA at the paper's scale |
| Slurm dispatch | **no** |  |
