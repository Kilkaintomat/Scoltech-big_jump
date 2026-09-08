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
# Compute nodes mount home read-only, and every layer of the torch stack wants to write a cache
# into it: torch.compile, inductor, triton, and vLLM's own compiled-graph store. vLLM dies
# outright on this -- `OSError: [Errno 30] Read-only file system: ~/.cache` inside dynamo, which
# surfaces as "Engine core initialization failed" with the real cause buried in the traceback.
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/gpfs/gpfs0/$USER/cache}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-$XDG_CACHE_HOME/vllm}"
export TRITON_CACHE_DIR="${TRITON_CACHE_DIR:-$XDG_CACHE_HOME/triton}"
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-$XDG_CACHE_HOME/inductor}"
mkdir -p "$XDG_CACHE_HOME" "$VLLM_CACHE_ROOT" "$TRITON_CACHE_DIR" "$TORCHINDUCTOR_CACHE_DIR" 2>/dev/null || true

# vLLM's telemetry thread writes to ~/.config and throws a traceback into the log when it cannot.
# Harmless -- it runs in a background thread -- but it looks exactly like a real failure in a job
# log someone is scanning for one.
export VLLM_NO_USAGE_STATS="${VLLM_NO_USAGE_STATS:-1}"
export DO_NOT_TRACK="${DO_NOT_TRACK:-1}"

export ELAN_HOME="${ELAN_HOME:-$HOME/.elan}"
export PATH="$ELAN_HOME/bin:$HOME/.local/bin:$PATH"

# The container has no `git`, so a run inside it cannot read its own commit however clean the
# checkout outside is -- and until this existed every cluster manifest recorded a null commit.
# Read it on the host and hand it in; `git_info` labels this `source: environment`, because an
# exported variable is weaker evidence than asking git directly and should not pretend otherwise.
# `git -C` is deliberately not used. The GPU nodes run git 1.8.3.1 (CentOS 7 stock), which
# predates `-C` (added in 1.8.5) and answers `Unknown option: -C` -- so every GPU run silently
# took the else branch and recorded `commit: null`, while the same code on a CPU node with git
# 2.43 recorded it correctly. That is how a whole set of cluster results came to have no
# provenance while the launcher appeared to be working. A subshell `cd` works on both.
if (cd "$REPO" && git rev-parse HEAD) >/dev/null 2>&1; then
    export ONEBIGJUMP_GIT_ROOT="$REPO"
    export ONEBIGJUMP_GIT_COMMIT="$(cd "$REPO" && git rev-parse HEAD)"
    export ONEBIGJUMP_GIT_BRANCH="$(cd "$REPO" && git rev-parse --abbrev-ref HEAD)"
    export ONEBIGJUMP_GIT_DESCRIBE="$(cd "$REPO" && git describe --always --dirty 2>/dev/null || true)"
    export ONEBIGJUMP_GIT_STATUS="$(cd "$REPO" && git status --porcelain)"
    export ONEBIGJUMP_GIT_REMOTE="$(cd "$REPO" && git config --get remote.origin.url || true)"
    echo "provenance: $ONEBIGJUMP_GIT_COMMIT on $ONEBIGJUMP_GIT_BRANCH (git $(git --version | awk '{print $3}'))" >&2
    if [ -n "$ONEBIGJUMP_GIT_STATUS" ]; then
        echo "WARNING: $REPO is dirty; results will be recorded as unreproducible." >&2
    fi
else
    # Say what is actually wrong. The previous message claimed "not a git checkout", which sent
    # the investigation after a missing .git that was there all along.
    echo "WARNING: cannot read the commit of $REPO with $(command -v git || echo 'no git')" >&2
    echo "         ($(git --version 2>&1 | head -1)). Manifests will carry no commit." >&2
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
