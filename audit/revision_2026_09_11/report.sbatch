#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONIOENCODING=utf-8
export AUDIT_ACCOUNTING_PATH="$REPO/audit/revision_2026_09_11/accounting-$SLURM_JOB_ID.tsv"
sacct -u denis.rakhmankin -S 2026-09-09 -X --format=JobID,JobName%45,State,ExitCode,Elapsed,Start,End,NodeList -P > "$AUDIT_ACCOUNTING_PATH"
py audit/revision_2026_09_11/report.py
