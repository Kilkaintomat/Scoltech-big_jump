#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=32
#SBATCH --mem=96G
#SBATCH --time=12:00:00
set -euo pipefail
export E1_SNAPSHOT=/beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_13/snapshots/statistical-fitness-v1
export E1_VERIFY_WORKERS=4
exec bash "$E1_SNAPSHOT/scripts/campaign/run.sbatch" "$@"
