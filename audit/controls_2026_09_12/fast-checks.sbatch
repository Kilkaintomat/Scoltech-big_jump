#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_12/snapshots/controls-v1-20260913"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1
py -c 'import os,pathlib;from onebigjump.e1.artifacts import verify_manifest;verify_manifest(pathlib.Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json")'
py -m ruff check --no-cache "$E1_SNAPSHOT/src" "$E1_SNAPSHOT/tests" "$E1_SNAPSHOT/scripts"
py -m ruff format --no-cache --check "$E1_SNAPSHOT/src" "$E1_SNAPSHOT/tests"
py -m mypy "$E1_SNAPSHOT/src"
py -m pytest "$REPO/tests" -m "not lean and not ml" -n 4 --dist=loadscope -q -o cache_dir=/tmp/obj-controls-$SLURM_JOB_ID --junitxml="$REPO/audit/controls_2026_09_12/fast-$SLURM_JOB_ID.xml"
py audit/revision_2026_09_12/updated_source_check.py
