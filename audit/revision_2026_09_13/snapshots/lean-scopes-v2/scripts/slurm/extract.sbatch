#!/bin/bash
#SBATCH --job-name=obj-extract
#SBATCH --partition=ais-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=%x-%j.out
#
# Stage 3: teacher-force the labelled traces, read the residual streams, build the table and run
# P1-P5. The calibration split is disjoint by problem, which the driver enforces.
source "$HOME/onebigjump/scripts/slurm/common.sh"
cd "$REPO"

obj run "${CONFIG:-configs/models/extract_activations.yaml}"
obj report
