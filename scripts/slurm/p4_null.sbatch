#!/bin/bash
#SBATCH --job-name=obj-p4null
#SBATCH --partition=ais-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=%x-%j.out
#
# P4's null: the same run with the labels permuted, so nothing generalises. If the tail index
# declines here as steeply as in the real run, P4's surviving claim is about optimisation rather
# than about algorithmic structure, and goes the same way as the transient peak did.
#
# CUDA, not MPS: the peak this experiment used to report was an MPS artefact, and the null is only
# comparable to runs made on a backend whose arithmetic is trusted.
source "$HOME/onebigjump/scripts/slurm/common.sh"
cd "$REPO"

nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
obj run configs/grokking/shuffled_null.yaml
