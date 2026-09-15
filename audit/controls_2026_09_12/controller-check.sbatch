#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:20:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_12/snapshots/lean-runtime-v3"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export OBJ_DISPATCH_CANDIDATE="$PWD/audit/controls_2026_09_12/dispatch-candidate.py"
py -m ruff check "$OBJ_DISPATCH_CANDIDATE"
py -m pytest tests/unit/test_readiness_dispatch_priority.py -q --junitxml="audit/controls_2026_09_12/controller-$SLURM_JOB_ID.xml"
python3 -c 'import ast,os; ast.parse(open(os.environ["OBJ_DISPATCH_CANDIDATE"]).read())'
