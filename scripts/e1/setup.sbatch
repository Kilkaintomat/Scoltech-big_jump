#!/usr/bin/env bash
#SBATCH --job-name=e1-lean-setup
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=runs/e1_20260908T171727Z/logs/setup-%j.log
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
source scripts/slurm/common.sh
E1_TOOLS="$REPO/runs/e1_20260908T171727Z/tools"
mkdir -p "$E1_TOOLS"
if [ ! -x "$E1_TOOLS/bin/micromamba" ]; then
 curl -fSL --retry 3 https://micro.mamba.pm/api/micromamba/linux-64/latest -o "$E1_TOOLS/micromamba.tar.bz2"
 tar xjf "$E1_TOOLS/micromamba.tar.bz2" -C "$E1_TOOLS" bin/micromamba
fi
export E1_TOOLS
mkdir -p "$E1_TOOLS/conda"
singularity exec --nv --bind /gpfs --bind /trinity --bind "$ELAN_HOME" --bind "$REPO" \
 --bind "$E1_TOOLS/conda:/trinity/home/$USER/.conda" \
 --bind "$E1_TOOLS/conda:/beegfs/home/$USER/.conda" "$SIF" bash -s <<'BUILD'
set -euo pipefail
export LAKE_NO_CACHE=1
cd /beegfs/home/denis.rakhmankin/onebigjump
export MAMBA_ROOT_PREFIX="$E1_TOOLS/mamba-root"
export CONDA_PKGS_DIRS="$E1_TOOLS/mamba-root/pkgs"
if [ ! -x "$E1_TOOLS/env/bin/curl" ]; then
 "$E1_TOOLS/bin/micromamba" create -y -p "$E1_TOOLS/env" -c conda-forge curl git make zstd
fi
export PATH="$E1_TOOLS/env/bin:$ELAN_HOME/toolchains/leanprover--lean4---v4.34.0-rc2/bin:$ELAN_HOME/bin:$PATH"
test "$(git -C lean_workspace/repl rev-parse HEAD)" = 5d5c49d13dfc0c1d2df43a27c3e56e02ad81b9c3
bash scripts/setup_lean.sh
BUILD
obj lean-doctor
