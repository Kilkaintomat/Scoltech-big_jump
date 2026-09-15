#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=32
#SBATCH --mem=96G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/statistical-fitness-v1"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"

export E1_GUARD_MIN_WORKERS=2
export E1_GUARD_CHILD_MANIFEST="$PWD/audit/revision_2026_09_13/statistical-fitness-v1/benchmark-guarded/manifest.json"
python3 audit/revision_2026_09_13/statistical-fitness-v1/resource_guard.py bash audit/revision_2026_09_13/statistical-fitness-v1/guarded-benchmark-body.sh
