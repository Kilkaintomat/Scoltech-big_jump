#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:30:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
files=(src/onebigjump/lean/environment.py scripts/e1/build_repl_runtime.py scripts/e1/activate_repl.py src/onebigjump/e1/smoke.py tests/unit/test_runtime_pin.py src/onebigjump/lean/verifier.py src/onebigjump/lean/lexical.py src/onebigjump/lean/segmentation.py src/onebigjump/e1/verification.py src/onebigjump/e1/stages.py src/onebigjump/readiness/p3_diagnosis.py tests/unit/test_e1_revision_0912.py tests/unit/test_p3_diagnosis.py tests/unit/test_reverification_campaign.py tests/integration/test_lean_revision_0912.py scripts/campaign/reverify.py scripts/campaign/verification_regression.py scripts/readiness/p3_diagnosis.py)
py -m ruff check --fix "${files[@]}"
py -m ruff format "${files[@]}"
py -m ruff check src scripts tests
py -m mypy src
py -m pytest tests/unit/test_runtime_pin.py tests/unit/test_e1_revision_0912.py tests/unit/test_reverification_campaign.py tests/unit/test_p3_diagnosis.py tests/unit/test_e1_revision.py -q -o cache_dir=/tmp/objformat-$SLURM_JOB_ID --junitxml=audit/revision_2026_09_12/format-$SLURM_JOB_ID.xml
