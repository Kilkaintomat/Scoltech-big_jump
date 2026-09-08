#!/bin/bash
#SBATCH --job-name=obj-p4
#SBATCH --partition=gpu_devel
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=08:00:00
#SBATCH --output=%x-%j.out
#
# P4: does the tail lighten when a circuit forms? Three seeds of the one-layer modular-addition
# transformer. Needs no Lean and no prover, so it is the first thing worth running here.
source "$(dirname "$(scontrol show job "$SLURM_JOB_ID" | grep -oP 'Command=\K[^ ]+')")/common.sh" 2>/dev/null \
  || source "$HOME/onebigjump/scripts/slurm/common.sh"
cd "$REPO"

nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
py -c "import torch; print('torch', torch.__version__, '| cuda', torch.cuda.is_available())"

for seed in 0 1 2; do
    echo "=== seed $seed ==="
    py -c "
from onebigjump.config import GrokkingConfig
from onebigjump.experiments.p4_grokking import run_p4
from onebigjump.logging import setup_logging
setup_logging('INFO')
run_p4(GrokkingConfig(steps=40000, checkpoint_every=100, device='cuda'), seed=$seed, full_every=20)
"
done
