#!/bin/bash
#SBATCH --job-name=lean-local-probe
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=audit/revision_2026_09_09/lean-local-%j.log
set -euo pipefail
source scripts/slurm/common.sh
E1_LEAN_SOURCE=/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/lean_workspace
E1_LOCAL_PROBE="$(mktemp -d /tmp/e1-lean-local-XXXXXXXX)"
export E1_LEAN_SOURCE E1_LOCAL_PROBE
printf '%s\n' "$E1_LOCAL_PROBE" > "$REPO/audit/revision_2026_09_09/local-lean-$SLURM_JOB_ID.path"
rsync -a --exclude='**/.lake/build/' "$E1_LEAN_SOURCE/" "$E1_LOCAL_PROBE/"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
singularity exec --nv --bind /gpfs --bind /trinity --bind "$ELAN_HOME" --bind "$REPO" --bind "$E1_LOCAL_PROBE" "$SIF" bash -s <<'CHECK'
set -euo pipefail
export LAKE_NO_CACHE=1
export MATHLIB_CACHE_DIR=/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/mathlib-cache
cd "$E1_LOCAL_PROBE/mathlib_project"
lake env "$E1_LEAN_SOURCE/mathlib_project/.lake/packages/mathlib/.lake/build/bin/cache" unpack
date -Is
lake env lean /beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_09/ImportProbe.lean
date -Is
CHECK
