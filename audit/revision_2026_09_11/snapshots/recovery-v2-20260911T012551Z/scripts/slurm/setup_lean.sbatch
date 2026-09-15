#!/bin/bash
#SBATCH --job-name=obj-lean
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --output=obj-lean-%j.out
#
# Stage 0 for everything that needs exact step labels: Lean 4 + Mathlib + the REPL.
#
# This runs on the host, NOT inside the Singularity image. elan ships its own statically-linked
# toolchain and the REPL is built against it, so the container's newer glibc buys nothing here --
# and `lake` needs the network, which the container binds are not set up for.
#
# The slow step is `lake exe cache get`: a few GB of precompiled .olean files. Building Mathlib
# from source instead takes hours, so a cache miss is worth noticing rather than waiting out.
source "$HOME/onebigjump/scripts/slurm/common.sh"
cd "$REPO"

echo "toolchain pinned to: $(cat lean_workspace/mathlib_project/lean-toolchain)"
bash scripts/setup_lean.sh

echo
echo "== does the REPL answer? =="
obj lean-doctor || true
