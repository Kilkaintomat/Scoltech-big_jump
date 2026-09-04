#!/usr/bin/env bash
# Lint, typecheck and test. Used by CI and before every commit.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== ruff =="
uv run ruff check src/ tests/ scripts/
uv run ruff format --check src/ tests/

echo "== mypy =="
uv run mypy src/

echo "== pytest =="
uv run pytest "$@"
