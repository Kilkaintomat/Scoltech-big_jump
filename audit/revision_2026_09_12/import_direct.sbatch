#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:30:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
source scripts/e1/stage_lean.sh
export PYTHONPATH="$REPO/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
run_in_container bash -c 'cd "$1/lean_workspace/mathlib_project"; lake env lean "$1/audit/revision_2026_09_12/import_file.lean"' bash "$REPO"
