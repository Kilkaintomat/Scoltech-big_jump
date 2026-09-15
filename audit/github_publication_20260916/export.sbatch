#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
set -euo pipefail
pub=/beegfs/home/denis.rakhmankin/onebigjump-publish-20260916
export REPO=/beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$pub"
export PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export SINGULARITY_BIND="$pub"
source "$pub/scripts/slurm/common.sh"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PYTHONPATH="$pub/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
cd "$pub"
py "$pub/audit/github_publication_20260916/export_results.py"
