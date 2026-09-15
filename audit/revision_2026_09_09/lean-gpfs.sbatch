#!/bin/bash
#SBATCH --job-name=lean-gpfs
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=audit/revision_2026_09_09/lean-gpfs-%j.log
set -euo pipefail
source scripts/slurm/common.sh
LEAN_GPFS=/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/lean_workspace
mkdir -p "$LEAN_GPFS"
rsync -a --exclude='**/.lake/build/' --exclude='__pycache__/' "$REPO/lean_workspace/" "$LEAN_GPFS/"
export LEAN_GPFS
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
run_in_container bash -s <<'BUILD'
set -euo pipefail
export LAKE_NO_CACHE=1
export MATHLIB_CACHE_DIR=/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/mathlib-cache
cd "$LEAN_GPFS/mathlib_project"
lake exe cache get
lake build
cd "$LEAN_GPFS/repl"
lake build
cd "$LEAN_GPFS/mathlib_project"
lake env lean /beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_09/ImportProbe.lean
BUILD
