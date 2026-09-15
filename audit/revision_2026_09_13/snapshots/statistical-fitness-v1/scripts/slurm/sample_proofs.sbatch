#!/bin/bash
#SBATCH --job-name=obj-sample
#SBATCH --partition=ais-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=%x-%j.out
#
# Stage 1: sample whole proofs, no verifier in the loop. An A100-80GB holds a 7-8B prover in
# bfloat16 with room to spare, so no quantisation -- which matters, because quantisation perturbs
# the residual stream whose tail is the observable.
source "$HOME/onebigjump/scripts/slurm/common.sh"
cd "$REPO"

CONFIG="${CONFIG:-configs/models/prover_sampling.yaml}"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
obj run "$CONFIG"
