#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_12/snapshots/lean-runtime-v3"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py -m ruff check src/onebigjump/lean/verifier.py tests/unit/test_repl_process_cleanup.py tests/integration/test_lean_scoped_context.py --fix
py -m ruff format src/onebigjump/lean/verifier.py tests/unit/test_repl_process_cleanup.py tests/integration/test_lean_scoped_context.py
py -m mypy src/onebigjump/lean/verifier.py
py -m pytest tests/unit/test_repl_process_cleanup.py tests/unit/test_e1_revision_0912.py -q --junitxml=audit/revision_2026_09_13/unit-$SLURM_JOB_ID.xml
