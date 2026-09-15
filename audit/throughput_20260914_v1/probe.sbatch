#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --nodes=2
#SBATCH --nodelist=cn55,cn56
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=256M
#SBATCH --time=00:02:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
srun python3 audit/throughput_20260914_v1/probe.py
