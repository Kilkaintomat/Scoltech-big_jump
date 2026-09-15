#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/deduction-numbered-v2"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export HF_HUB_OFFLINE=1
py -m ruff check "$E1_SNAPSHOT/src/onebigjump/readiness/deduction.py"
py -m ruff format --check "$E1_SNAPSHOT/src/onebigjump/readiness/deduction.py"
py -m pytest "$E1_SNAPSHOT/tests/unit/test_development_protocols_0913.py" -q --junitxml="$REPO/audit/revision_2026_09_13/exact-preflight-$SLURM_JOB_ID.xml"
py audit/revision_2026_09_13/deduction_exact_preflight.py
