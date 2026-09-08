#!/bin/bash
#SBATCH --job-name=obj-lean
#SBATCH --partition=ais-htc
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --array=0-3
#SBATCH --output=%x-%A_%a.out
#
# Stage 2: exact per-step labels from the Lean 4 kernel. CPU-bound and usually the slowest stage,
# so it runs as an array over disjoint shards. Lean runs on the host, not in the container.
source "$HOME/onebigjump/scripts/slurm/common.sh"
cd "$REPO"

SAMPLES="${SAMPLES:-data/raw/prover-sampling/samples.jsonl}"
OUT="${OUT:-results/full/lean}"

"$REPO/.venvc/bin/onebigjump" lean-verify "$SAMPLES" \
    --out-dir "$OUT" \
    --shard "${SLURM_ARRAY_TASK_ID:-0}" \
    --n-shards "${SLURM_ARRAY_TASK_COUNT:-1}"
