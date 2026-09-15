#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py -m ruff check src tests scripts
py -m ruff format --check src tests scripts/campaign
py -m ruff check src tests scripts
py -m ruff format --check src tests
py -m mypy src
py -m pytest tests/unit/test_campaign.py tests/unit/test_e1.py tests/unit/test_e1_revision.py -q --junitxml="runs/lean_all_20260909/final-checks-$SLURM_JOB_ID.xml"
for script in scripts/campaign/*.sbatch; do bash -n "$script"; done
git diff --check
