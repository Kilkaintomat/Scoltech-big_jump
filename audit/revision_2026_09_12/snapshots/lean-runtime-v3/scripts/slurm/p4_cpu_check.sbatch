#!/bin/bash
#SBATCH --job-name=obj-p4cpu
#SBATCH --partition=ais-htc
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=%x-%j.out
#
# One seed of P4 in float32 on CPU, to decide whether the transient peak in gamma_hat seen on
# Apple MPS is a property of the model or of the backend. CUDA does not show it; if CPU agrees
# with CUDA, the peak is an MPS artefact and the finding has to be withdrawn.
source "$HOME/onebigjump/scripts/slurm/common.sh"
cd "$REPO"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export MKL_NUM_THREADS="$OMP_NUM_THREADS" OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"

py -c "
from onebigjump.config import GrokkingConfig
from onebigjump.experiments.p4_grokking import run_p4
from onebigjump.logging import setup_logging
setup_logging('INFO')
run_p4(GrokkingConfig(steps=40000, checkpoint_every=100, device='cpu',
                      out_dir='results/full/grokking_cpu'),
       seed=0, full_every=0, out_dir='results/full/grokking_cpu')
"
