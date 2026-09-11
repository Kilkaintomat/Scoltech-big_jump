#!/usr/bin/env bash
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$(cat audit/readiness_2026_09_11/source-path.txt)"
export PYTHONIOENCODING=utf-8
exec python3 "$E1_SNAPSHOT/scripts/readiness/dispatch.py" runs/expansion_20260911 --validation 8464485 >> runs/expansion_20260911/controller/console.log 2>&1
