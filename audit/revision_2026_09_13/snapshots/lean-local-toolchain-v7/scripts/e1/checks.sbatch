#!/usr/bin/env bash
#SBATCH --job-name=e1-checks
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=audit/revision_2026_09_09/e1-checks-%j.log
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
py -m ruff check src tests scripts
py -m ruff format --check src tests
py -m mypy src
py -m pytest tests/unit/test_e1.py tests/unit/test_e1_revision.py -q --junitxml="audit/revision_2026_09_09/e1-$SLURM_JOB_ID.xml"
