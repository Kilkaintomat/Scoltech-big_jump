#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=64
#SBATCH --mem=96G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/statistical-fitness-v1"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"

python3 audit/revision_2026_09_13/statistical-fitness-v1/resource_guard.py bash "$E1_SNAPSHOT/scripts/campaign/run.sbatch" "$@"
