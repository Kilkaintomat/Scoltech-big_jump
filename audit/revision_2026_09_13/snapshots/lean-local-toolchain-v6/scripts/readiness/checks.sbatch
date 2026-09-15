#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export SINGULARITYENV_PREPEND_PATH="$REPO/runs/e1_20260908T171727Z/tools/env/bin:$ELAN_HOME/bin"
source "$E1_SNAPSHOT/scripts/e1/stage_lean.sh"
export PYTHONPATH="$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1
py -c 'import hashlib,json,os,pathlib; root=pathlib.Path("/beegfs/home/denis.rakhmankin/onebigjump"); snap=pathlib.Path(os.environ["E1_SNAPSHOT"]); m=json.loads((snap/"source-manifest.json").read_text()); assert all(hashlib.sha256((root/pathlib.Path(p).relative_to(snap)).read_bytes()).hexdigest()==h for p,h in m["outputs"].items()), "working files differ from frozen source snapshot"'
py -m ruff check --no-cache "$E1_SNAPSHOT/src" "$E1_SNAPSHOT/tests" "$E1_SNAPSHOT/scripts"
py -m ruff format --no-cache --check "$E1_SNAPSHOT/src" "$E1_SNAPSHOT/tests"
py -m mypy "$E1_SNAPSHOT/src"
py -m pytest "$REPO/tests" -m 'not lean and not ml' -n 4 --dist=loadscope -q -o cache_dir=/tmp/obj-fast-${SLURM_JOB_ID} --junitxml="$REPO/audit/readiness_2026_09_11/fast-$SLURM_JOB_ID.xml"
py -m pytest "$REPO/tests" -n 4 --dist=loadscope -q -o cache_dir=/tmp/obj-full-${SLURM_JOB_ID} --junitxml="$REPO/audit/readiness_2026_09_11/full-$SLURM_JOB_ID.xml"
for script in "$E1_SNAPSHOT"/scripts/readiness/*.sbatch "$E1_SNAPSHOT"/scripts/campaign/*.sbatch; do bash -n "$script"; done
python3 - "$E1_SNAPSHOT/scripts/readiness/dispatch.py" "$E1_SNAPSHOT/scripts/campaign/dispatch.py" <<'PY'
import ast, sys
for name in sys.argv[1:]:
    with open(name, encoding='utf-8') as stream:
        ast.parse(stream.read(), filename=name)
PY
