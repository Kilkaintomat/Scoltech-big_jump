#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
py -m ruff check src tests scripts
py -m ruff format scripts/campaign
py -m compileall -q scripts/campaign
for script in scripts/campaign/*.sbatch; do bash -n "$script"; done
