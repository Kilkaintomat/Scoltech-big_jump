#!/bin/bash
#SBATCH --job-name=revision-format
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --output=audit/revision_2026_09_09/format-%j.log
set -euo pipefail
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py -m ruff check --fix src tests scripts
py -m ruff format src tests scripts/e1
py -m mypy src
py -m pytest tests/unit/test_e1.py tests/unit/test_e1_revision.py tests/unit/test_lean_segmentation.py tests/unit/test_thresholds.py -q --junitxml="audit/revision_2026_09_09/focused-$SLURM_JOB_ID.xml"
