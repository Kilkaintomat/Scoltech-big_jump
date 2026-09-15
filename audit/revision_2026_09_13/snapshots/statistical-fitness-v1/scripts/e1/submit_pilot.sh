#!/usr/bin/env bash
# Launch only the implemented real-prover development pilot, after revision checks pass.
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
E1_ROOT="${1:-$PWD/runs/e1_20260908T171727Z}"
E1_VALIDATION_JOB="${2:?pass the successful final validation job ID}"
# Slurm forgets completed jobs after MinJobAge; afterok cannot refer to an old passed job.
# Validate completed prerequisite receipts in accounting before submitting any new work.
for prerequisite in "$E1_VALIDATION_JOB" ${3:+"$3"}; do
  case "$prerequisite" in ""|*[!0-9]*) echo "Invalid prerequisite job ID" >&2; exit 2;; esac
  state="$(sacct -n -X -j "$prerequisite" --format=JobID,State,ExitCode -P | awk -F'|' -v id="$prerequisite" '$1 == id { print $2 "|" $3 }')"
  if [ "$state" != "COMPLETED|0:0" ]; then
    echo "Prerequisite $prerequisite has not completed successfully: $state" >&2
    exit 1
  fi
done
test -f "$E1_ROOT/pilot/protocol.json"
export E1_SNAPSHOT
E1_SNAPSHOT="$(python3 scripts/e1/snapshot.py "$E1_ROOT" pilot)"
E1_LOGS="$E1_ROOT/logs"
E1_SCRIPT="$E1_SNAPSHOT/scripts/e1/run.sbatch"
generation="$(sbatch --parsable \
 --partition=ais-gpu --gres=gpu:1 --job-name=e1-generation --output="$E1_LOGS/generate-%j.log" \
 "$E1_SCRIPT" generate "$E1_ROOT")"
verification="$(sbatch --parsable --kill-on-invalid-dep=yes --dependency="afterok:$generation" \
 --partition=ais-htc --exclude=cn69 --job-name=e1-verification --output="$E1_LOGS/verify-%j.log" \
 "$E1_SCRIPT" verify "$E1_ROOT")"
extraction="$(sbatch --parsable --kill-on-invalid-dep=yes --dependency="afterok:$verification" \
 --partition=ais-gpu --gres=gpu:1 --job-name=e1-extraction --output="$E1_LOGS/extract-%j.log" \
 "$E1_SCRIPT" extract "$E1_ROOT")"
measurement="$(sbatch --parsable --kill-on-invalid-dep=yes --dependency="afterok:$extraction" \
 --partition=ais-htc --exclude=cn69 --job-name=e1-measurement --output="$E1_LOGS/measure-%j.log" \
 "$E1_SCRIPT" measure "$E1_ROOT")"
analysis="$(sbatch --parsable --kill-on-invalid-dep=yes --dependency="afterok:$measurement" \
 --partition=ais-htc --exclude=cn69 --job-name=e1-analysis --output="$E1_LOGS/analyze-%j.log" \
 "$E1_SCRIPT" analyze "$E1_ROOT")"
python3 - "$E1_ROOT" "$E1_SNAPSHOT" "$generation" "$verification" "$extraction" "$measurement" "$analysis" <<'PY'
import json
import sys
from pathlib import Path
root, source = sys.argv[1:3]
jobs = dict(zip(("generation", "verification", "extraction", "measurement", "analysis"), sys.argv[3:]))
payload = {"root": root, "source": source, "jobs": jobs}
out = Path(root)/"pilot"/("submission-" + jobs["generation"] + ".json")
with out.open("x", encoding="utf-8") as stream:
    json.dump(payload, stream, indent=2)
    stream.write("\n")
print(json.dumps(payload, indent=2))
PY
