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
# Generation uses the exact installed Lean fingerprint in the pilot gate as well.
case "$1" in smoke|verify|generate) source "$E1_SNAPSHOT/scripts/e1/stage_lean.sh";; esac
if [[ "$1" == analyze ]]; then export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1; fi
if [[ -n "${SLURM_ARRAY_TASK_ID:-}" ]]; then
    py "$E1_SNAPSHOT/scripts/campaign/run.py" "$@" --shard "$SLURM_ARRAY_TASK_ID" --n-shards 8
else
    py "$E1_SNAPSHOT/scripts/campaign/run.py" "$@"
fi
