# Shared settings for every Zhores batch job. Sourced, not run.
#
# Everything runs inside a Singularity container. Not for isolation but out of necessity: the
# nodes are CentOS 7 with glibc 2.17, and pyarrow, contourpy and torch itself no longer publish
# wheels for it. The container supplies glibc 2.35; the host supplies the driver.
#
# torch is pinned to 2.6.0+cu124 by the driver, not by preference. Driver 550.54 caps CUDA at
# 12.4, and cu126 builds need 560. 2.6.0 is also the last release with manylinux1 wheels, so the
# two constraints happen to agree.
set -euo pipefail

# `realpath` because the compute nodes reach home through a different mount than the login
# nodes, and singularity resolves the path it is given rather than following the symlink.
REPO="$(cd "${REPO:-$HOME/onebigjump}" && pwd -P)"
SIF="${SIF:-/gpfs/gpfs0/$USER/containers/pytorch26.sif}"
export HF_HOME="${HF_HOME:-/gpfs/gpfs0/$USER/hf_cache}"
# The compute nodes mount home read-only for dotfile creation, so matplotlib cannot build its
# font cache in the default place and falls back to /tmp on every import.
export MPLCONFIGDIR="${MPLCONFIGDIR:-/gpfs/gpfs0/$USER/mplconfig}"
mkdir -p "$MPLCONFIGDIR" "$HF_HOME" 2>/dev/null || true
export ELAN_HOME="${ELAN_HOME:-$HOME/.elan}"
export PATH="$ELAN_HOME/bin:$HOME/.local/bin:$PATH"

# The container has no `git`, so a run inside it cannot read its own commit however clean the
# checkout outside is -- and until this existed every cluster manifest recorded a null commit.
# Read it on the host and hand it in; `git_info` labels this `source: environment`, because an
# exported variable is weaker evidence than asking git directly and should not pretend otherwise.
if git -C "$REPO" rev-parse HEAD >/dev/null 2>&1; then
    export ONEBIGJUMP_GIT_COMMIT="$(git -C "$REPO" rev-parse HEAD)"
    export ONEBIGJUMP_GIT_BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
    export ONEBIGJUMP_GIT_DESCRIBE="$(git -C "$REPO" describe --always --dirty)"
    export ONEBIGJUMP_GIT_STATUS="$(git -C "$REPO" status --porcelain)"
    export ONEBIGJUMP_GIT_REMOTE="$(git -C "$REPO" config --get remote.origin.url || true)"
    if [ -n "$ONEBIGJUMP_GIT_STATUS" ]; then
        echo "WARNING: $REPO is dirty; results will be recorded as unreproducible." >&2
    fi
else
    echo "WARNING: $REPO is not a git checkout. Manifests will carry no commit." >&2
fi

# `--bind /gpfs` because home is small and the caches, containers and results live on GPFS.
run_in_container() {
    singularity exec --nv \
        --bind /gpfs --bind /trinity --bind "$REPO" --bind "$HF_HOME" \
        "$SIF" "$@"
}

# The Lean kernel runs on the host, not in the container: elan is installed in user space and the
# REPL is a native binary built against the host toolchain.
py() { run_in_container "$REPO/.venvc/bin/python" "$@"; }
obj() { run_in_container "$REPO/.venvc/bin/onebigjump" "$@"; }
