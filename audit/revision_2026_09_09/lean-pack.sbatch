#!/bin/bash
#SBATCH --job-name=lean-runtime-pack
#SBATCH --partition=ais-htc
#SBATCH --account=rsollmrs
#SBATCH --nodelist=cn70
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --output=audit/revision_2026_09_09/lean-pack-%j.log
set -euo pipefail
source scripts/slurm/common.sh
E1_PACK_SOURCE="$(cat "$REPO/audit/revision_2026_09_09/local-lean-8462776.path")"
E1_PACK_TARGET=/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools
test -d "$E1_PACK_SOURCE/mathlib_project"
mkdir -p "$E1_PACK_SOURCE/repl/.lake/build/bin"
cp "$E1_PACK_TARGET/lean_workspace/repl/.lake/build/bin/repl" "$E1_PACK_SOURCE/repl/.lake/build/bin/repl"
test ! -e "$E1_PACK_TARGET/lean-runtime.tar"
tar -C "$E1_PACK_SOURCE" -cf "$E1_PACK_TARGET/lean-runtime.tar.tmp" .
mv "$E1_PACK_TARGET/lean-runtime.tar.tmp" "$E1_PACK_TARGET/lean-runtime.tar"
cd "$E1_PACK_TARGET"
sha256sum lean-runtime.tar > lean-runtime.tar.sha256
chmod a-w lean-runtime.tar lean-runtime.tar.sha256
cat lean-runtime.tar.sha256
du -h lean-runtime.tar
