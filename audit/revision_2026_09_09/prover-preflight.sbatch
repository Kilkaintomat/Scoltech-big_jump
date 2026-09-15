#!/bin/bash
#SBATCH --job-name=prover-preflight
#SBATCH --partition=ais-gpu
#SBATCH --account=rsollmrs
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --output=audit/revision_2026_09_09/prover-preflight-%j.log
set -euo pipefail
source scripts/slurm/common.sh
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export HF_HUB_OFFLINE=1 VLLM_USE_V1=0
py audit/revision_2026_09_09/prover-preflight.py
