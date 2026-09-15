#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=24:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PYTHONPATH="$REPO/audit/segmentation_v3_20260914/frozen:$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
source "$E1_SNAPSHOT/scripts/e1/stage_lean.sh"
cp -f "$REPO/audit/segmentation_v3_20260914/frozen/repl-observer" "$E1_LOCAL_LEAN/repl/.lake/build/bin/repl"
py "$REPO/audit/segmentation_v3_20260914/frozen/campaign_worker.py" --root "$REPO/runs/segmentation_20260914_v3" --task "$SLURM_ARRAY_TASK_ID"
