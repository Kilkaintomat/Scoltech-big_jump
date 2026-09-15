#!/bin/bash
#SBATCH --job-name=lean-activate
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=audit/revision_2026_09_09/lean-activate-%j.log
set -euo pipefail
source scripts/slurm/common.sh
LEAN_GPFS=/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/lean_workspace
LEAN_BEFORE=/beegfs/home/denis.rakhmankin/lean-storage-before-20260909
mkdir -p "$LEAN_BEFORE"
# Keep tracked Lean project files in place; only ignored binary/cache directories move.
for item in mathlib_project/.lake/packages mathlib_project/.lake/build repl/.lake/build; do
  test -d "$LEAN_GPFS/$item"
  if [ ! -L "$REPO/lean_workspace/$item" ]; then
    destination="$LEAN_BEFORE/${item//\//_}"
    test ! -e "$destination"
    mv "$REPO/lean_workspace/$item" "$destination"
    ln -s "$LEAN_GPFS/$item" "$REPO/lean_workspace/$item"
  fi
done
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
source scripts/e1/stage_lean.sh
run_in_container bash -s <<'CHECK'
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump/lean_workspace/mathlib_project
lake env lean /beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_09/ImportProbe.lean
CHECK
