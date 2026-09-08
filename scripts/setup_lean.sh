#!/usr/bin/env bash
# Lean 4 + Mathlib + the REPL, entirely in user space. No sudo, no system packages.
#
# Appendix B.2 of the paper needs three things from the toolchain:
#   1. compile a whole proof against Mathlib      -> lake build
#   2. replay tactics one at a time, in tactic mode, against the proof state left by 1..t-1
#   3. distinguish an elaboration error from a timeout, and from a whole-proof parse error
# Only the REPL gives (2), so it is installed alongside Mathlib rather than as an optional extra.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
WS="$REPO/lean_workspace"

export ELAN_HOME="${ELAN_HOME:-$HOME/.elan}"
export PATH="$ELAN_HOME/bin:$PATH"

if ! command -v elan >/dev/null 2>&1; then
  echo "== installing elan (user space) =="
  curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y --no-modify-path
  export PATH="$ELAN_HOME/bin:$PATH"
fi
echo "elan  $(elan --version)"

mkdir -p "$WS"

if [ ! -f "$WS/mathlib_project/lakefile.toml" ] && [ ! -f "$WS/mathlib_project/lakefile.lean" ]; then
  echo "== creating the Mathlib project =="
  cd "$WS"
  # `lake new <name> math` wires up the Mathlib dependency and pins a toolchain that matches it.
  lake +leanprover-community/mathlib4:lean-toolchain new mathlib_project math \
    || lake new mathlib_project math
fi

cd "$WS/mathlib_project"
echo "== toolchain: $(cat lean-toolchain) =="

# elan resolves toolchain *names* through https://release.lean-lang.org, which some networks
# cannot reach -- on Zhores it times out from every node while github.com answers instantly, and
# elan then hangs on a lock file with no error at all. Pre-installing the toolchain from its
# GitHub release makes the name resolvable locally, so elan never has to ask.
# The check must not go through elan: asking it anything about an unresolved toolchain is what
# hangs, so `elan run ... --version` as a probe blocks exactly where the probe was meant to help.
# Look on disk instead.
TC="$(cat lean-toolchain)"
TC_DIR="$ELAN_HOME/toolchains/$(echo "$TC" | sed 's|/|--|g; s|:|---|g')"
if [ ! -x "$TC_DIR/bin/lean" ]; then
  echo "== toolchain not on disk; installing it from GitHub =="
  bash "$REPO/scripts/install_lean_toolchain.sh" "$TC"
fi
# Point lake and lean at it directly, so no command has to resolve the name over the network.
export PATH="$TC_DIR/bin:$PATH"
export ELAN_TOOLCHAIN="$TC"

# `lake update` is deliberately NOT run when a manifest is already committed. The manifest pins
# Mathlib at the exact revision the step labels were produced against, but several of its
# dependencies are pinned to `main`; re-resolving would silently move them and verify future
# proofs against a different Mathlib than the recorded one. The manifest is only written when the
# project is created for the first time, which is where `lake new` above left it.
if [ -f lake-manifest.json ]; then
  echo "== using the committed lake-manifest.json (mathlib pinned) =="
else
  echo "== no manifest: resolving dependencies for the first time =="
  lake update
fi

echo "== fetching the Mathlib binary cache (this is the slow step) =="
lake exe cache get

echo "== building =="
lake build

if [ ! -d "$WS/repl" ]; then
  echo "== cloning the Lean REPL =="
  git clone --depth 1 https://github.com/leanprover-community/repl "$WS/repl"
fi

echo "== building the REPL against the same toolchain =="
cp "$WS/mathlib_project/lean-toolchain" "$WS/repl/lean-toolchain"
cd "$WS/repl"
lake build

echo
echo "Lean is ready."
echo "  toolchain : $(cat "$WS/mathlib_project/lean-toolchain")"
echo "  project   : $WS/mathlib_project"
echo "  repl      : $WS/repl"
echo
echo "Verify with:  uv run onebigjump lean-doctor"
