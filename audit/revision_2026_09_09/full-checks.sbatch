#!/bin/bash
#SBATCH --job-name=revision-full
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=audit/revision_2026_09_09/full-%j.log
set -euo pipefail
source scripts/slurm/common.sh
cd "$REPO"
source scripts/e1/stage_lean.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 HF_HUB_OFFLINE=1
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PATH="$REPO/audit/revision_2026_09_08/bin:$REPO/.venvc/bin:$PATH"
export PYTEST_ADDOPTS="-n 4 --dist=loadscope --junitxml=audit/revision_2026_09_09/make-test-$SLURM_JOB_ID.xml"
make test > "audit/revision_2026_09_09/make-test-$SLURM_JOB_ID.log" 2>&1
tail -n 4 "audit/revision_2026_09_09/make-test-$SLURM_JOB_ID.log"
export PYTEST_ADDOPTS="-n 4 --dist=loadscope --junitxml=audit/revision_2026_09_09/make-test-all-$SLURM_JOB_ID.xml"
make test-all > "audit/revision_2026_09_09/make-test-all-$SLURM_JOB_ID.log" 2>&1
tail -n 6 "audit/revision_2026_09_09/make-test-all-$SLURM_JOB_ID.log"
git diff --check
for script in scripts/slurm/*.sh scripts/slurm/*.sbatch scripts/e1/*.sbatch scripts/e1/*.sh; do bash -n "$script"; done
