#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-local-toolchain-v7"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export HF_HUB_OFFLINE=1
export REVIEW_HOST_STATUS="$PWD/audit/revision_2026_09_13/active_followthrough_v2/slurm-status-$SLURM_JOB_ID.txt"
squeue -u denis.rakhmankin -o "%.18i %.10T %.45j %.10M %.12R" > "$REVIEW_HOST_STATUS"
chmod 444 "$REVIEW_HOST_STATUS"
py audit/revision_2026_09_13/active_followthrough_v2/review.py
