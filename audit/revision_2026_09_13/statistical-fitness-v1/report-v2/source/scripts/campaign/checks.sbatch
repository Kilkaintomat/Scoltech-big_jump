#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py -m ruff check src tests scripts
py -m ruff format --check src tests scripts/campaign
py -m mypy src
py -m pytest tests/ -m "not lean and not ml" -q --junitxml="runs/lean_all_20260909/checks-$SLURM_JOB_ID.xml"
