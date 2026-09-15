#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/p5_repair_20260914_v2/source"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PYTHONPATH="$E1_SNAPSHOT/src:$PWD/audit/p5_repair_20260914_v2:$PWD/audit/followthrough_20260915_v1"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1 VLLM_USE_V1=1
export SINGULARITY_BIND="/beegfs/shared/opt/rh:/beegfs/shared/opt/rh:ro"
export CC="$REPO/audit/p5_repair_20260914_v2/runtime_cc/cc-wrapper.sh"
export SINGULARITYENV_CC="$CC"
export TRITON_CACHE_DIR="$REPO/audit/p5_repair_20260914_v2/runtime_cc/cache/triton"
export PYTHONPATH="/beegfs/home/denis.rakhmankin/onebigjump/audit/followthrough_recovery_20260916_v2:$PYTHONPATH"
py "/beegfs/home/denis.rakhmankin/onebigjump/audit/followthrough_recovery_20260916_v2/mask_check.py"
py "/beegfs/home/denis.rakhmankin/onebigjump/audit/followthrough_recovery_20260916_v2/p5_resume.py" calibration
