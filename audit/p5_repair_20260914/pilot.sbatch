#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/p5_repair_20260914/source"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
export PYTHONPATH="$E1_SNAPSHOT/src:$PWD/audit/p5_repair_20260914"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1

py audit/p5_repair_20260914/gpu_entry.py
for arm in unguided guided; do
    py audit/p5_repair_20260914/pipeline.py generate "$arm"
done
for arm in unguided guided; do
    for stage in verify extract measure analyze gate; do
        py audit/p5_repair_20260914/pipeline.py "$stage" "$arm"
    done
done
py audit/p5_repair_20260914/pipeline.py summary
