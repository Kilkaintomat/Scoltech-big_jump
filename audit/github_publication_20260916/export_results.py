"""Export compact immutable experiment evidence; large states and generated proof corpora stay on Zhores."""
import os,json,hashlib,shutil,datetime,re,collections
from pathlib import Path
SOURCE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
PUB=Path("/beegfs/home/denis.rakhmankin/onebigjump-publish-20260916")
OUT=PUB/"results/campaign_20260916"
OUT.mkdir(exist_ok=False)
entries=[]
def copy_file(src,dst):
 data=src.read_bytes();dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
 entries.append({"path":str(dst.relative_to(PUB)),"source":str(src),"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
def tree(label,relative,recursive=True):
 base=SOURCE/relative
 assert base.is_dir(),str(base)
 for p in (base.rglob("*") if recursive else base.iterdir()):
  if not p.is_file() or p.is_symlink() or any(x in {"fonts","__pycache__","states"} for x in p.relative_to(base).parts):continue
  if p.suffix.lower() not in {".json",".md",".pdf",".html",".csv",".tsv",".xml",".png",".svg",".tex",".txt"}:continue
  if p.stat().st_size>4*1024*1024:continue
  if p.name.startswith('preview-') or p.name in {"REPORT.aux","REPORT.toc","pdf-text.txt"}:continue
  copy_file(p,OUT/label/p.relative_to(base))
def selected(label,relative,names):
 base=SOURCE/relative
 for n in names:
  p=base/n
  if p.is_file():copy_file(p,OUT/label/n)
tree("main-review","runs/result_review_20260914_v1/report_v3")
tree("independent-design-and-audit","runs/followthrough_20260915_v1/followthrough_report_v2")
tree("status-0139-msk","runs/followthrough_recovery_20260916_v2/report_v3")
selected("status-0139-msk","runs/followthrough_recovery_20260916_v2/latex_final",["REPORT.pdf","REPORT.tex","render-receipt.json","pdf-checks.json"])
selected("p5-final","runs/followthrough_20260915_v1/p5_analysis",["metrics.json","manifest.json","assigned-attempts.json","localization-T0.6.json","localization-T1.json"])
for arm in ["calibration","evaluation"]:
 for stage in ["generation/shard-000-of-001","verification","extraction"]:
  selected("p5-"+arm+"/"+stage,"runs/followthrough_20260915_v1/p5_"+arm+"/main/"+stage,["manifest.json"])
 selected("p5-"+arm,"runs/followthrough_20260915_v1/p5_"+arm,["protocol.json","calibration_gate/metrics.json","calibration_gate/manifest.json"])
for label,path in [("p3-original-validation","runs/p3_validation_20260913/summary"),("p3-constrained-candidate","runs/p3_constrained_validation_20260913"),("p3-selection-candidate","runs/p3_selection_validation_20260913"),("monte-carlo","runs/expansion_20260911/calibration-summary"),("segmentation-quality","runs/segmentation_quality_20260914_v1"),("kimina-cleanup","runs/kimina_post_completion_20260914_v1/comparison")]:
 selected(label,path,["metrics.json","summary.json","manifest.json","REPORT.md","protocol.json"])
# P4 report, code and diagnostics are preserved with the audit sources; select compact generated metrics.
selected("p4-audit","audit/p4_audit_20260914",["metrics.json","manifest.json","REPORT_RU.md","REPORT.md","REPORT_RU.pdf","summary-audit.json","full-tail.json","artifact-manifest.json","checks.json","provenance.json","forward-reconstruction.json","windows.json","original-paired-summary.json","runs.json","fourier-mask-controls.json","sensitivity.json","configs.json"])
selected("runtime-recovery","runs/followthrough_recovery_20260916_v2",["submissions-current.json","inspection-final.json","preflight/metrics.json","preflight/manifest.json","gpu-preflight-8468362/metrics.json","gpu-preflight-8468362/manifest.json"])
selected("integrity-check-0206-msk","runs/status_check_20260916_0205",["metrics.json","manifest.json"])
selected("live-state-snapshot","runs/followthrough_20260915_v1/flow",["latest.json","jobs.json"])
selected("p2-prospective","runs/followthrough_20260915_v1/p2_pipeline",["metrics.json","manifest.json","task-population.json","deepseek-config.json","goedel-config.json","deepseek-requests.json","goedel-requests.json"])
for model in ["deepseek","goedel"]:
 for role in ["pilot","evaluation"]:
  selected("p2-prospective/"+model+"/"+role,"runs/followthrough_20260915_v1/p2_pipeline/"+model+"/"+role+"/generation",["progress.json","metrics.json","manifest.json"])
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
meta={"exported_utc":now,"source_repository":str(SOURCE),"base_commit":"bf0bdbe21c00fb9bd677da5a0318eac83f1c8f98","entries":entries,"scope":"Exact-byte compact evidence export. P2 is an ongoing fixed-population campaign; snapshots are dated, not final results. Original manifests retain server paths and describe heavy artifacts not shipped in Git."}
(OUT/"export-manifest.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
p5=json.loads((OUT/"p5-final/metrics.json").read_text(encoding="utf-8"))
cal=json.loads((OUT/"p5-calibration/verification/manifest.json").read_text(encoding="utf-8"))["metrics"]
eva=json.loads((OUT/"p5-evaluation/verification/manifest.json").read_text(encoding="utf-8"))["metrics"]
readme=["# Experimental evidence snapshot — 2026-09-16", "Exported UTC: "+now,
"This folder contains compact reports, metrics, protocols and original manifests. All copied bytes are indexed in [export-manifest.json](export-manifest.json). Original manifest paths remain absolute Zhores paths; they are provenance, not a claim that omitted arrays or model weights are bundled here.",
"## Current evidence", "- [Completed three-model miniF2F review](main-review/REPORT_RU.md).", "- [Independent calibration, label audit and prospective ProofNet design](independent-design-and-audit/REPORT_RU.md).", "- [P5 independent evaluation and analysis](p5-final/metrics.json): completed.", "- [P2 fixed prospective protocol](../../audit/followthrough_20260915_v1/p2-confirmatory-protocol.json): acquisition ongoing at capture; no confirmatory P2 result is declared.",
"## P5 accounting", "| Split | Assigned attempts | Verified | Invalid inference |", "| --- | ---: | ---: | ---: |"]
for name,m in [("Calibration",cal),("Independent evaluation",eva)]:readme.append("| "+name+" | "+str(m["attempts"])+" | "+str(m["categories"]["verified"])+" | "+str(m["categories"]["invalid_inference"])+" |")
readme += ["Calibration/evaluation task overlap: "+str(p5["calibration_evaluation_task_overlap"])+".", "The length predictor and jump localization are separate endpoints. A length trend alone does not identify a heavy-tail mechanism. All assigned attempts are retained in denominators.",
"## Reproduction", "Use the code and frozen source/protocol manifests under `audit/`, plus the current `src/`, `scripts/` and `tests/`. Cluster entrypoints contain explicit Zhores paths. Rehydrating original execution requires the pinned model weights, benchmark inputs, Lean runtime and retained source/data stores; these are not Git objects. Do not rewrite original historical manifests after relocating files.",
"The small dated status PDF predates the final P5 result; `p5-final/metrics.json` and the table above supersede its in-progress P5 status. Earlier reviews remain dated historical evidence.",
"Model weights, activation matrices, large proof journals, runtime binaries, caches and credentials are intentionally not part of this source-and-evidence commit."]
rendered="\n\n".join(readme)+"\n"
rendered=re.sub(r"(?m)^(\|[^\n]*\|)\n\n(?=\|)",r"\1\n",rendered)
(OUT/"README.md").write_text(rendered,encoding="utf-8")
for e in entries:assert hashlib.sha256((PUB/e["path"]).read_bytes()).hexdigest()==e["sha256"]
print(json.dumps({"exported_files":len(entries),"megabytes":sum(x["bytes"] for x in entries)/1048576,"p5_calibration":cal,"p5_evaluation":eva,"p2_ongoing":True},ensure_ascii=False),flush=True)
