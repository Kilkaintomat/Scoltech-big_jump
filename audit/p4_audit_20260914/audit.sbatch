#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:20:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export P4_SNAPSHOT="$PWD/audit/readiness_2026_09_11/snapshots/expansion-v1-20260911T024740Z"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$P4_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$P4_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1
py "$REPO/audit/p4_audit_20260914/audit.py"
