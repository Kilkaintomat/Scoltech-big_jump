#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONIOENCODING=utf-8
py audit/revision_2026_09_11/parser-check.py
