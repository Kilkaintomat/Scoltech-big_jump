#!/bin/bash
#SBATCH --job-name=obj-revision-final
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=audit/revision_2026_09_08/final-%j.log
set -euo pipefail
source scripts/slurm/common.sh
cd "$REPO"
export PYTHONPATH="$REPO/src"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 HF_HUB_OFFLINE=1
py -m pytest tests/ -m "not lean" -o addopts= -q -ra --junitxml=audit/revision_2026_09_08/server-tests.xml -p no:cacheprovider > audit/revision_2026_09_08/server-tests.log 2>&1
tail -n 5 audit/revision_2026_09_08/server-tests.log
py scripts/revision_diagnostics.py --archive audit/revision_2026_09_08/baseline --out audit/revision_2026_09_08/server-diagnostics
py audit/revision_2026_09_08/check_report.py
