#!/bin/bash
#SBATCH --job-name=obj-tests
#SBATCH --partition=ais-htc
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=%x-%j.out
#
# The cluster rules forbid calculations on the login nodes, and these are calculations: the
# bootstrap and double-bootstrap tests are minutes of CPU each. Thread counts are pinned because
# numpy otherwise opens one BLAS thread per visible core and spends its time contending -- on the
# shared login node it ran 96 threads and made no progress for forty minutes.
source "$HOME/onebigjump/scripts/slurm/common.sh"
cd "$REPO"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
py -m pytest tests/ -m "not lean" -q --no-header -p no:cacheprovider
