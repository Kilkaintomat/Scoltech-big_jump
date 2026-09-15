from pathlib import Path
import os,json,zipfile
import pymupdf
from artifact_bridge import finish_artifact
from stage_support import digest
O=Path("/beegfs/home/denis.rakhmankin/onebigjump/runs/followthrough_recovery_20260916_v2/latex")
log=(O/"REPORT.log").read_text(encoding="utf-8",errors="replace")
assert "Missing character:" not in log
assert "Overfull" not in log
p=pymupdf.open(O/"REPORT.pdf");text="\n".join(page.get_text() for page in p)
assert "One Big Jump" in text and "Состояние" not in text[:5]
assert "2000" in text and "6672" in text and "ProofNet" in text
(O/"pdf-text.txt").write_text(text,encoding="utf-8")
for i in range(min(len(p),3)):p[i].get_pixmap(matrix=pymupdf.Matrix(1.1,1.1)).save(str(O/("preview-"+str(i+1)+".png")))
with zipfile.ZipFile(O/"REPORT-latex.zip","w",zipfile.ZIP_DEFLATED) as z:
 for name in ["REPORT.tex","REPORT.pdf","REPORT.md","metrics.json"]:z.write(O/name,name)
 for f in (O/"fonts").iterdir():z.write(f,"fonts/"+f.name)
m={"pages":len(p),"missing_glyphs":False,"overfull_boxes":False,"scientific_metrics_unchanged":digest(O/"metrics.json")==digest(O.parent/"report_v2/metrics.json")}
(O/"pdf-checks.json").write_text(json.dumps(m,indent=2))
finish_artifact(O,stage="status-report-latex-pdf",context={},inputs=[O.parent/"report_v2/manifest.json",Path(__file__),Path(__file__).parent/"render_status_latex.py"],outputs=[O/n for n in ["REPORT.tex","REPORT.pdf","REPORT.md","REPORT.html","metrics.json","REPORT-latex.zip","pdf-checks.json"]],metrics=m)
print(json.dumps(m))
