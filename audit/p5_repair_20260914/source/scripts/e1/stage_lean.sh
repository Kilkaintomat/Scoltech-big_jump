#!/usr/bin/env bash
# Source inside a Slurm job: network storage is unsuitable for Lean's random mmap reads.
set -euo pipefail
: "${SLURM_JOB_ID:?Lean staging requires a Slurm allocation}"
E1_LEAN_ARCHIVE=/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/lean-runtime.tar
(cd "$(dirname "$E1_LEAN_ARCHIVE")" && sha256sum -c lean-runtime.tar.sha256)
export E1_LOCAL_LEAN
E1_LOCAL_LEAN="$(mktemp -d "${SLURM_TMPDIR:-/tmp}/onebigjump-lean-XXXXXXXX")"
cleanup_local_lean() {
    rm -rf -- "${E1_LOCAL_LEAN:?}"
    if [ -n "${E1_LOCAL_ELAN:-}" ]; then rm -rf -- "$E1_LOCAL_ELAN"; fi
}
trap cleanup_local_lean EXIT
if [ -n "${E1_SNAPSHOT:-}" ] && [ -f "$E1_SNAPSHOT/configs/lean_toolchain_runtime.json" ]; then
    export E1_LOCAL_ELAN E1_ELAN_RUNTIME_MANIFEST
    E1_LOCAL_ELAN="$(mktemp -d "${SLURM_TMPDIR:-/tmp}/onebigjump-elan-XXXXXXXX")"
    E1_ELAN_RUNTIME_MANIFEST="$(python3 "$E1_SNAPSHOT/scripts/e1/activate_toolchain.py" "$E1_SNAPSHOT/configs/lean_toolchain_runtime.json" "$E1_LOCAL_ELAN")"
    echo "Pinned complete Lean toolchain staged on node storage: $E1_LOCAL_ELAN"
fi
tar -xf "$E1_LEAN_ARCHIVE" -C "$E1_LOCAL_LEAN"
echo "Lean runtime staged on node storage: $E1_LOCAL_LEAN"

# The immutable source snapshot pins any reviewed local REPL repair by binary and manifest hash.
if [ -n "${E1_SNAPSHOT:-}" ] && [ -f "$E1_SNAPSHOT/configs/repl_runtime.json" ]; then
    export E1_REPL_RUNTIME_MANIFEST
    E1_REPL_RUNTIME_MANIFEST="$(python3 "$E1_SNAPSHOT/scripts/e1/activate_repl.py" "$E1_SNAPSHOT/configs/repl_runtime.json" "$E1_LOCAL_LEAN/repl/.lake/build/bin/repl")"
    export ONEBIGJUMP_REPL_BINARY="$REPO/lean_workspace/repl/.lake/build/bin/repl"
    echo "Pinned REPL runtime manifest: $E1_REPL_RUNTIME_MANIFEST"
fi
