#!/usr/bin/env bash
# Source inside a Slurm job: network storage is unsuitable for Lean's random mmap reads.
set -euo pipefail
: "${SLURM_JOB_ID:?Lean staging requires a Slurm allocation}"
E1_LEAN_ARCHIVE=/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/lean-runtime.tar
(cd "$(dirname "$E1_LEAN_ARCHIVE")" && sha256sum -c lean-runtime.tar.sha256)
export E1_LOCAL_LEAN
E1_LOCAL_LEAN="$(mktemp -d "${SLURM_TMPDIR:-/tmp}/onebigjump-lean-XXXXXXXX")"
trap 'rm -rf -- "${E1_LOCAL_LEAN:?}"' EXIT
tar -xf "$E1_LEAN_ARCHIVE" -C "$E1_LOCAL_LEAN"
echo "Lean runtime staged on node storage: $E1_LOCAL_LEAN"
