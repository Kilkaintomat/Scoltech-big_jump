#!/bin/bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-cpu
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=/beegfs/home/denis.rakhmankin/onebigjump/runs/goedel_no_tactic_length_state_20261115_v1/%x-%j.log
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1
export ONEBIGJUMP_GIT_COMMIT="$(git rev-parse HEAD)" ONEBIGJUMP_GIT_STATUS="$(git status --porcelain)"
script="$1"; shift
set +e
py "$REPO/experiments/goedel_no_tactic_length_state_20261115_v1/$script" "$@"
status=$?
set -e
if [ "$status" -eq 75 ] && [ "$script" = pool_warm.py ]; then
  next=$(sbatch --parsable --dependency="afterany:${SLURM_JOB_ID}" --job-name="${SLURM_JOB_NAME}-cont" "$0" "$script" "$@")
  printf 'CONTINUATION_JOB %s\n' "$next"
  exit 0
fi
exit "$status"
