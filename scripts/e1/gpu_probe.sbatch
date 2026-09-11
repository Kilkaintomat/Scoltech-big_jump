#!/usr/bin/env bash
#SBATCH --job-name=e1-gpu-probe
#SBATCH --partition=ais-gpu
#SBATCH --account=rsollmrs
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --output=runs/e1_20260908T171727Z/logs/gpu-probe-%j.log
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1
py - <<'PY'
from pathlib import Path
from onebigjump.e1.artifacts import digest, environment, write_once
from transformers import AutoTokenizer
import torch
root = Path('runs/e1_20260908T171727Z/checks')
p = Path('/gpfs/gpfs0/denis.rakhmankin/hf_cache/hub/models--deepseek-ai--DeepSeek-Prover-V2-7B/snapshots/a8d9e14432b2e8dd9df2a4d4e70f1ba9bc8d9b7b')
tok = AutoTokenizer.from_pretrained(str(p), local_files_only=True)
print(environment(), flush=True)
print('CUDA', torch.cuda.is_available(), 'TOKENIZER', tok.backend_tokenizer.decoder, flush=True)
write_once(root / 'gpu-environment.json', environment())
write_once(root / 'model-digests.json', {x.name: digest(x) for x in sorted(p.iterdir()) if x.is_file()})
write_once(root / 'container-digest.json', {'path': '/gpfs/gpfs0/denis.rakhmankin/containers/pytorch26.sif', 'sha256': digest('/gpfs/gpfs0/denis.rakhmankin/containers/pytorch26.sif')})
PY
