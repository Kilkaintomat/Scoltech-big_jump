#!/usr/bin/env bash
# One-shot setup on a fresh machine. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "installing uv into user space"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "== python environment =="
# vllm and flash-attn are deliberately excluded: both are Linux + CUDA only.
uv sync --python 3.11 --extra stats --extra viz --extra ml --extra dev

echo "== system report =="
uv run python scripts/doctor.py --write

echo "== smoke test =="
uv run onebigjump doctor
uv run pytest tests/unit -q

cat <<'MSG'

Next steps that need credentials or a toolchain, in order:
  1. gh auth login                          # to create and push the private repository
  2. scripts/setup_lean.sh                  # elan + Mathlib + the REPL (user space, no sudo)
  3. uv run onebigjump run configs/simulation/figure1.yaml
MSG
