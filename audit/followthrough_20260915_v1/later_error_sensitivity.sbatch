#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --job-name=ft15-later-error
#SBATCH --output=/beegfs/home/denis.rakhmankin/onebigjump/runs/followthrough_20260915_v1/later_error_sensitivity/slurm-%j.out
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$REPO/audit/followthrough_20260915_v1:$E1_SNAPSHOT/src"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py "$REPO/audit/followthrough_20260915_v1/later_error_sensitivity.py"
