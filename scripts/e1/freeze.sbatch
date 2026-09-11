#!/usr/bin/env bash
#SBATCH --job-name=e1-freeze
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=runs/e1_20260908T171727Z/logs/freeze-%j.log
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8
py scripts/e1/freeze_protocol.py runs/e1_20260908T171727Z
