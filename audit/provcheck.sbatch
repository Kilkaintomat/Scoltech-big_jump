#!/bin/bash
#SBATCH --job-name=obj-prov
#SBATCH --partition=ais-gpu
#SBATCH --gres=gpu:1
#SBATCH --account=rsollmrs
#SBATCH --time=00:08:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=audit/provcheck-%j.out
source scripts/slurm/common.sh
echo "git on this node : $(git --version)"
echo "exported commit  : ${ONEBIGJUMP_GIT_COMMIT:-<unset>}"
py -c "
import sys; sys.path.insert(0, \"src\")
from onebigjump.reproducibility import git_info
g = git_info()
print(\"manifest would record: source=%s commit=%s dirty=%s\" % (g[\"source\"], g[\"commit\"], g[\"dirty\"]))
"
