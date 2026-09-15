#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py -m ruff format src/onebigjump/readiness scripts/readiness/run.py scripts/readiness/dispatch.py tests/unit/test_readiness.py
py -m ruff check --fix src/onebigjump/readiness scripts/readiness tests/unit/test_readiness.py
py -m mypy src/onebigjump/readiness
py -m pytest tests/unit/test_readiness.py -q --junitxml=audit/readiness_2026_09_11/new-tests.xml
