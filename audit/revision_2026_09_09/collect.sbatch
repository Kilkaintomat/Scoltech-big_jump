#!/bin/bash
#SBATCH --job-name=revision-report
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --output=audit/revision_2026_09_09/report-%j.log
set -euo pipefail
source scripts/slurm/common.sh
export PYTHONPATH="$REPO/src" PYTHONIOENCODING=utf-8
sacct -j "$1",8462796,8462759,8462778,8462781 --format=JobID,JobName,State,ExitCode,NodeList,Elapsed,Start,End -P > "$REPO/audit/revision_2026_09_09/slurm-accounting.tsv"
py audit/revision_2026_09_09/collect_validation.py "$1"
