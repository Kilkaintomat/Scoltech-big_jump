#!/bin/bash
#SBATCH --job-name=obj-precommit
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=audit/revision_2026_09_08/precommit-%j.log
set -euo pipefail
source scripts/slurm/common.sh
cd "$REPO"
export PYTHONPATH="$REPO/src"
export PATH="$REPO/audit/revision_2026_09_08/bin:$REPO/.venvc/bin:$PATH"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 HF_HUB_OFFLINE=1
export UV_PROJECT_ENVIRONMENT="$REPO/.venvc" UV_NO_SYNC=1 UV_CACHE_DIR="$XDG_CACHE_HOME/uv"
export PYTEST_ADDOPTS='-n 4 --dist=loadscope --junitxml=audit/revision_2026_09_08/server-make-test.xml'
make test > audit/revision_2026_09_08/server-make-test.log 2>&1
tail -n 4 audit/revision_2026_09_08/server-make-test.log
export PYTEST_ADDOPTS='-n 4 --dist=loadscope --junitxml=audit/revision_2026_09_08/server-make-test-all.xml'
make test-all > audit/revision_2026_09_08/server-make-test-all.log 2>&1
tail -n 4 audit/revision_2026_09_08/server-make-test-all.log
