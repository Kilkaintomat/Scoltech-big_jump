#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-gpu
#SBATCH --constraint=a100
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=00:25:00
#SBATCH --nice=10000
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$REPO/audit/segmentation_controls_20260914_v1:$REPO/audit/segmentation_extraction_20260914_v1:$REPO/audit/segmentation_v3_20260914/frozen:$E1_SNAPSHOT/src"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1
py "$REPO/audit/segmentation_controls_20260914_v1/profile.py"
