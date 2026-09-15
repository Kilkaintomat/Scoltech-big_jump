#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 HF_HUB_OFFLINE=1 VLLM_USE_V1=0
if [[ "$1" == calibration || "$1" == deduction-analyze ]]; then
    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
fi
py "$E1_SNAPSHOT/scripts/readiness/run.py" "$@"
