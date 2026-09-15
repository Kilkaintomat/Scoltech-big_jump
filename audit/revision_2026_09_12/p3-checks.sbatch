#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:15:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py -m ruff check --fix src/onebigjump/readiness/p3_diagnosis.py tests/unit/test_p3_diagnosis.py
py -m ruff format src/onebigjump/readiness/p3_diagnosis.py tests/unit/test_p3_diagnosis.py
py -m pytest tests/unit/test_p3_diagnosis.py -q -o cache_dir=/tmp/objp3-$SLURM_JOB_ID --junitxml=audit/revision_2026_09_12/p3-checks-$SLURM_JOB_ID.xml
