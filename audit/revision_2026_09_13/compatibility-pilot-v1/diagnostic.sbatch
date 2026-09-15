#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=64
#SBATCH --mem=96G
#SBATCH --time=00:30:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export E1_GUARD_MIN_WORKERS=1
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"

python3 audit/revision_2026_09_13/statistical-fitness-v1/resource_guard.py bash "$PWD/audit/revision_2026_09_13/compatibility-pilot-v1/body.sh"
