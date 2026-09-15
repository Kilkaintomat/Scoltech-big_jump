#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$REPO/audit/segmentation_extraction_repair_20260914_v2:$REPO/audit/segmentation_extraction_20260914_v1:$REPO/audit/segmentation_v3_20260914/frozen:$E1_SNAPSHOT/src"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 HF_HUB_OFFLINE=1
models=(deepseek goedel kimina)
py "$REPO/audit/segmentation_extraction_repair_20260914_v2/extract.py" --model "${models[$SLURM_ARRAY_TASK_ID]}" --wave all
