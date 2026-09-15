#!/bin/bash
#SBATCH --job-name=e1-pipeline-check
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --output=audit/revision_2026_09_09/pipeline-%j.log
set -euo pipefail
source scripts/slurm/common.sh
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
py audit/revision_2026_09_09/pipeline-fixture.py
