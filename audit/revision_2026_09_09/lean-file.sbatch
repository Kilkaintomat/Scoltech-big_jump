#!/bin/bash
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=audit/revision_2026_09_09/lean-file-%j.log
set -euo pipefail
source scripts/slurm/common.sh
export PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
run_in_container bash -s <<'PROBE'
set -x
echo "$ELAN_HOME"
command -v lake
lake --version
cd /beegfs/home/denis.rakhmankin/onebigjump/lean_workspace/mathlib_project
lake env lean /beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_09/ImportProbe.lean
PROBE
