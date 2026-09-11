#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONIOENCODING=utf-8
export READINESS_ACCOUNTING="$REPO/audit/readiness_2026_09_11/accounting-$SLURM_JOB_ID.tsv"
sacct -X -n -u "$USER" --starttime=2026-09-11 --format=JobID,JobName,State,ExitCode,Elapsed -P > "$READINESS_ACCOUNTING"
py audit/readiness_2026_09_11/report.py
