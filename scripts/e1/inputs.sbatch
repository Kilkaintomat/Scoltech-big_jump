#!/usr/bin/env bash
#SBATCH --job-name=e1-inputs
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=runs/e1_20260908T171727Z/logs/inputs-%j.log
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8
py scripts/e1/prepare_inputs.py runs/e1_20260908T171727Z/inputs
