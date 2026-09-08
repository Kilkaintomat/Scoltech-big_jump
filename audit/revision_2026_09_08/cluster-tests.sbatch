#!/bin/bash
#SBATCH --job-name=obj-revision-tests
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=audit/revision_2026_09_08/cluster-%j.log
set -euo pipefail
source scripts/slurm/common.sh
cd "$REPO"
export PYTHONPATH="$REPO/src"
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export HF_HUB_OFFLINE=1
py -m pytest tests/ -m "not lean" -o addopts= -q -ra --junitxml=audit/revision_2026_09_08/cluster-tests.xml -p no:cacheprovider
