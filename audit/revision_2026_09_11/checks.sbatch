#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
if [[ "${1:-}" == format ]]; then
  py -m ruff check src/onebigjump/lean/segmentation.py src/onebigjump/e1 src/onebigjump/stats/gpd.py src/onebigjump/stats/estimators.py src/onebigjump/experiments/p3_overshoot.py src/onebigjump/experiments/p4_grokking.py src/onebigjump/experiments/p5_length_law.py tests/unit/test_gpd.py tests/unit/test_e1_revision_0911.py scripts/campaign --fix
  py -m ruff format src/onebigjump/lean/segmentation.py src/onebigjump/e1 src/onebigjump/stats/gpd.py src/onebigjump/stats/estimators.py src/onebigjump/experiments/p3_overshoot.py src/onebigjump/experiments/p4_grokking.py src/onebigjump/experiments/p5_length_law.py tests/unit/test_gpd.py tests/unit/test_e1_revision_0911.py scripts/campaign
fi
py -m ruff check src tests scripts
py -m ruff format --check src tests
py -m mypy src
py -m pytest tests/ -m "not lean and not ml" -n 4 --dist=loadscope -q --junitxml="audit/revision_2026_09_11/checks-$SLURM_JOB_ID.xml"
for script in scripts/campaign/*.sbatch; do bash -n "$script"; done
git diff --check
