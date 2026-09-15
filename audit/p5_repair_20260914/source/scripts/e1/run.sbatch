#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 HF_HUB_OFFLINE=1 VLLM_USE_V1=0
if [[ "${1:-}" == smoke || "${1:-}" == verify ]]; then source "$E1_SNAPSHOT/scripts/e1/stage_lean.sh"; fi
py "$E1_SNAPSHOT/scripts/e1/run.py" "$@" 
