#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
export PYTHONIOENCODING=utf-8
/usr/bin/python3 /beegfs/home/denis.rakhmankin/onebigjump/audit/scheduler_fit_20260914_v1/fit.py
