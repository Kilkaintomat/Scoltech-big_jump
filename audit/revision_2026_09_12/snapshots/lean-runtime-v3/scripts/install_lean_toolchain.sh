#!/usr/bin/env bash
# Install a Lean toolchain from GitHub, for networks where elan's own index is unreachable.
#
# elan resolves a toolchain name by asking https://release.lean-lang.org, a Cloudflare Pages site.
# On Zhores that host times out from both the login and the compute nodes while github.com,
# raw.githubusercontent.com and huggingface.co all answer in under a second -- so `elan` hangs
# forever on a lock file with no error and no output, which looks exactly like a slow download.
#
# The toolchains themselves are published as ordinary GitHub releases, which are reachable. This
# fetches the tarball directly and unpacks it into elan's toolchain directory, after which elan,
# lake and lean behave normally: elan only consults the index to *resolve* a name, not to use a
# toolchain already on disk.
#
# Usage:  scripts/install_lean_toolchain.sh [toolchain]
#         toolchain defaults to whatever lean_workspace/mathlib_project/lean-toolchain pins.
set -euo pipefail
cd "$(dirname "$0")/.."

TOOLCHAIN="${1:-$(cat lean_workspace/mathlib_project/lean-toolchain 2>/dev/null || echo "")}"
[ -n "$TOOLCHAIN" ] || { echo "no toolchain given and none pinned" >&2; exit 1; }

# `leanprover/lean4:v4.34.0-rc2` -> version `v4.34.0-rc2`
VERSION="${TOOLCHAIN##*:}"
# elan's on-disk name replaces `/` with `--` and `:` with `---`
DIRNAME="$(echo "$TOOLCHAIN" | sed 's|/|--|g; s|:|---|g')"

export ELAN_HOME="${ELAN_HOME:-$HOME/.elan}"
TARGET="$ELAN_HOME/toolchains/$DIRNAME"

if [ -x "$TARGET/bin/lean" ]; then
  echo "already installed: $TARGET"
  "$TARGET/bin/lean" --version
  exit 0
fi

case "$(uname -m)" in
  x86_64)  ASSET="lean-${VERSION#v}-linux" ;;
  aarch64) ASSET="lean-${VERSION#v}-linux_aarch64" ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

URL="https://github.com/leanprover/lean4/releases/download/${VERSION}/${ASSET}.tar.zst"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/leantc.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

echo "== fetching $URL =="
# --fail so a 404 is an error rather than an HTML page unpacked as a tarball.
curl -fSL --retry 3 --retry-delay 5 -o "$TMP/lean.tar.zst" "$URL"

echo "== unpacking =="
# tar --zstd is not in every build; fall back to piping through unzstd.
if tar --zstd -tf "$TMP/lean.tar.zst" >/dev/null 2>&1; then
  tar --zstd -xf "$TMP/lean.tar.zst" -C "$TMP"
elif command -v unzstd >/dev/null 2>&1; then
  unzstd -c "$TMP/lean.tar.zst" | tar -xf - -C "$TMP"
elif command -v zstd >/dev/null 2>&1; then
  zstd -dc "$TMP/lean.tar.zst" | tar -xf - -C "$TMP"
else
  echo "no zstd available to unpack the toolchain" >&2
  exit 1
fi

ROOT="$(find "$TMP" -maxdepth 2 -type d -name bin -exec dirname {} \; | head -1)"
[ -n "$ROOT" ] || { echo "unpacked archive has no bin/ directory" >&2; exit 1; }

mkdir -p "$ELAN_HOME/toolchains"
rm -rf "$TARGET"
mv "$ROOT" "$TARGET"

echo "== installed =="
"$TARGET/bin/lean" --version
echo "$TARGET"
