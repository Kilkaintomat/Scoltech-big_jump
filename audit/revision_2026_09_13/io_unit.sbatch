#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:15:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-scopes-v4"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py -m ruff format src/onebigjump/lean/verifier.py tests/unit/test_repl_io_errors.py scripts/e1/activate_toolchain.py
py -m ruff check src tests scripts
py -m pytest tests/unit/test_repl_io_errors.py tests/unit/test_repl_kernel_status.py tests/unit/test_repl_process_cleanup.py -q --junitxml="$PWD/audit/revision_2026_09_13/io-unit-$SLURM_JOB_ID.xml"
