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

echo "== fetching the Mathlib binary cache (this is the slow step) =="
lake update -R || lake update
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
