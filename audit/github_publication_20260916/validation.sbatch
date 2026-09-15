#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
set -euo pipefail
pub=/beegfs/home/denis.rakhmankin/onebigjump-publish-20260916
export REPO=/beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$pub"
export PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export SINGULARITY_BIND="$pub"
source "$pub/scripts/slurm/common.sh"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PYTHONPATH="$pub/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
source "$pub/scripts/e1/stage_lean.sh"
export HF_HUB_OFFLINE=1
cd "$pub"
# Exact commands from make test / make test-all, using the pinned installed runtime instead of uv syncing it.
py -m ruff check src tests scripts
py -m ruff format --check src tests
py -m mypy src
py -m pytest tests -m "not lean and not ml" -q --junitxml="$pub/audit/github_publication_20260916/fast-$SLURM_JOB_ID.xml"
py -m pytest tests -q -n 2 --dist loadscope --junitxml="$pub/audit/github_publication_20260916/full-$SLURM_JOB_ID.xml"
