#!/bin/bash
#SBATCH --job-name=revision-checks
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=audit/revision_2026_09_09/checks-%j.log
set -uo pipefail
source scripts/slurm/common.sh
cd "$REPO"
set +e
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 HF_HUB_OFFLINE=1
py -m ruff check src tests scripts
py -m ruff format --check src tests
py -m mypy src
py -m pytest tests -m 'not lean' -n 4 --dist=loadscope --junitxml="audit/revision_2026_09_09/baseline-$SLURM_JOB_ID.xml"
