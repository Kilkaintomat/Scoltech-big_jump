#!/usr/bin/env bash
#SBATCH --account=rsollmrs
#SBATCH --partition=ais-htc
#SBATCH --exclude=cn69
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
set -euo pipefail
cd /beegfs/home/denis.rakhmankin/onebigjump
export E1_SNAPSHOT="$PWD/audit/revision_2026_09_13/snapshots/lean-io-v9"
export PATH="$PWD/runs/e1_20260908T171727Z/tools/env/bin:$PATH"
source "$E1_SNAPSHOT/scripts/slurm/common.sh"
export PYTHONPATH="$REPO/audit/followthrough_20260915_v1:$E1_SNAPSHOT/src" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$REPO/audit/followthrough_20260915_v1:$REPO/audit/segmentation_extraction_20260914_v1:$REPO/audit/segmentation_v3_20260914/frozen:$E1_SNAPSHOT/src"
export HF_HUB_OFFLINE=1 VLLM_USE_V1=1
export PYTHONPATH="/beegfs/home/denis.rakhmankin/onebigjump/audit/followthrough_recovery_20260916_v2:/beegfs/home/denis.rakhmankin/onebigjump/audit/segmentation_extraction_repair_20260914_v3:$PYTHONPATH"
export SINGULARITY_BIND="/beegfs/home/denis.rakhmankin/onebigjump-inference-audit-20260911"
report_base="/beegfs/home/denis.rakhmankin/onebigjump-inference-audit-20260911/audit/process_report"
report_tools="$report_base/typesetting-tools"
report_out="$REPO/runs/followthrough_recovery_20260916_v2/latex"
py "$REPO/audit/followthrough_recovery_20260916_report/render_status_latex.py" "$REPO/runs/followthrough_recovery_20260916_v2/report_v2" "$report_out"
cd "$report_out"
export FONTCONFIG_FILE="$report_tools/fonts.conf" TECTONIC_CACHE_DIR="$report_tools/cache"
"$report_tools/tectonic" --bundle https://data1.fullyjustified.net/tlextras-2022.0r0.tar --keep-logs --keep-intermediates REPORT.tex > compile.txt 2>&1
export PYTHONPATH="$report_tools/pylibs:$PYTHONPATH"
py "$REPO/audit/followthrough_recovery_20260916_report/finalize_pdf.py"
