#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
source scripts/e1/stage_lean.sh
export PYTHONPATH="$REPO/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1
py -m ruff check --fix src/onebigjump/lean src/onebigjump/e1/verification.py tests/unit/test_e1_revision_0912.py tests/integration/test_lean_revision_0912.py
py -m ruff format src/onebigjump/lean src/onebigjump/e1/verification.py tests/unit/test_e1_revision_0912.py tests/integration/test_lean_revision_0912.py
py -m pytest tests/unit/test_e1_revision_0912.py tests/unit/test_e1_revision.py tests/unit/test_e1_revision_0911.py tests/unit/test_lean_segmentation.py tests/integration/test_lean_revision_0912.py -q -o cache_dir=/tmp/obj0912-$SLURM_JOB_ID --junitxml=audit/revision_2026_09_12/checks-$SLURM_JOB_ID.xml
