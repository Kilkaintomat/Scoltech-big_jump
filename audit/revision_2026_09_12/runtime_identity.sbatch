#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"

export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1
py audit/revision_2026_09_12/runtime_identity.py
