#!/bin/bash
#SBATCH --job-name=obj-gitprobe
#SBATCH --partition=ais-gpu
#SBATCH --account=rsollmrs
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --gres=gpu:1
#SBATCH --output=audit/gitprobe-%j.out
echo "node: $(hostname)"
echo "git binary: $(command -v git || echo MISSING)"
echo "git version: $(git --version 2>&1 | head -1)"
for d in /beegfs/home/$USER/onebigjump /trinity/home/$USER/onebigjump; do
  echo "--- $d"
  echo "    exists: $([ -d $d ] && echo yes || echo no)"
  echo "    .git  : $([ -e $d/.git ] && echo yes || echo no)"
  echo "    rev   : $(git -C $d rev-parse HEAD 2>&1 | head -1)"
done
