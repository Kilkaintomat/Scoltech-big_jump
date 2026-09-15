#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1
cd "$E1_SNAPSHOT"
py -m ruff check src tests scripts --fix
py -m ruff format src tests
py -m ruff check src tests scripts
py -m ruff format --check src tests
py -m mypy src
cd "$REPO"
py audit/revision_2026_09_13/speedup-v2/freeze-io.py
source "$E1_SNAPSHOT/scripts/e1/stage_lean.sh"
cd "$E1_SNAPSHOT"
py -m pytest tests -q -n 2 --dist loadscope --junitxml="$REPO/audit/revision_2026_09_13/speedup-v2/io-tests-$SLURM_JOB_ID.xml"
