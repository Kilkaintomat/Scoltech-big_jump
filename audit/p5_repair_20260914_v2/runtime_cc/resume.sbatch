#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-gpu
#SBATCH --nodelist=gn35
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export SINGULARITY_BIND="/beegfs/shared/opt/rh:/beegfs/shared/opt/rh:ro"
export CC="$PWD/audit/p5_repair_20260914_v2/runtime_cc/cc-wrapper.sh"
export SINGULARITYENV_CC="$CC"
export TRITON_CACHE_DIR="$PWD/audit/p5_repair_20260914_v2/runtime_cc/cache/triton"
export E1_SNAPSHOT="$PWD/audit/p5_repair_20260914_v2/source"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PYTHONPATH="$E1_SNAPSHOT/src:$PWD/audit/p5_repair_20260914_v2"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1 VLLM_USE_V1=1
py audit/p5_repair_20260914_v2/gpu_entry.py
py audit/p5_repair_20260914_v2/runtime_cc/gpu_mask.py
# The original immutable wrapper skips the completed unguided generation.
bash audit/p5_repair_20260914_v2/pilot.sbatch
py audit/p5_repair_20260914_v2/review_pilot.py
