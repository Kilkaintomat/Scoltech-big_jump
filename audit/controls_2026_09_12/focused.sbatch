#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:30:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_12/snapshots/lean-runtime-v3"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
files=(src/onebigjump/readiness/diagnostics.py src/onebigjump/readiness/controls.py scripts/readiness/dispatch.py scripts/readiness/run.py tests/unit/test_control_diagnostics.py tests/unit/test_readiness_dispatch_priority.py)
py -m ruff check --fix "${files[@]}"
py -m ruff format "${files[@]}"
py -m mypy src/onebigjump/readiness/diagnostics.py
py -m pytest tests/unit/test_control_diagnostics.py tests/unit/test_readiness_dispatch_priority.py tests/unit/test_readiness.py -m "not ml" -q --junitxml="audit/controls_2026_09_12/focused-$SLURM_JOB_ID.xml"
