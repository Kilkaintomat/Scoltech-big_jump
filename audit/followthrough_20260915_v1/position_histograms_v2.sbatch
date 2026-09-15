#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --job-name=ft15-position-layout
#SBATCH --output=/beegfs/home/denis.rakhmankin/onebigjump/runs/followthrough_20260915_v1/position_histograms_v2/slurm-%j.out
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$REPO/audit/followthrough_20260915_v1:$E1_SNAPSHOT/src"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MPLBACKEND=Agg
export MPLCONFIGDIR="$REPO/runs/followthrough_20260915_v1/position_histograms_v2/matplotlib_cache"
py "$REPO/audit/followthrough_20260915_v1/position_histograms_v2.py"
