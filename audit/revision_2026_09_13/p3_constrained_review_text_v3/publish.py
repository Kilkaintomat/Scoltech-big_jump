"""Render text corrections from completed metrics; no estimates or tests are rerun."""
from pathlib import Path
import json,os,shutil,zipfile
from onebigjump.e1.artifacts import read_json,verify_manifest,digest,finish,write_once
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
audit=base/"audit/revision_2026_09_13"
old=audit/"reviews/p3-constrained-validation-v1"
out=audit/"reviews/p3-constrained-validation-v3"
verify_manifest(old/"manifest.json")
out.mkdir(parents=True,exist_ok=False)
metrics=read_json(old/"metrics.json")
text=(old/"REPORT.md").read_text(encoding="utf-8")
cases=metrics["preflight"]["cases"]
points=metrics["fresh_point_checks"]
text=text.replace(f"До новых данных пройдены {cases} численных случаев:",
                  f"До генерации новых данных проверены численные контрольные случаи ({cases}):")
text=text.replace(f"После фиксации результата дополнительно проверены все {points} новые точечные оценки на плотной сетке.",
                  f"После фиксации результата проверка на плотной сетке охватила все новые точечные оценки ({points}).")
lines=text.splitlines()
for i,line in enumerate(lines):
    if line.startswith("| ") and " | " in line:
        cells=line.split("|")
        if len(cells)==8 and cells[2].strip().startswith(("legacy/","constrained/")):
            for k in [5,6]:
                if cells[k].strip()!="NA":
                    cells[k]=" "+format(float(cells[k].strip()),".4f")+" "
            lines[i]="|".join(cells)
(out/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
for name in ["metrics.json","fresh-point-audit.json","coverage-availability.png","coverage-availability.pdf"]:
    shutil.copyfile(old/name,out/name)
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
here=Path(__file__).resolve().parent
outputs=sorted(out.iterdir())
finish(out,stage="constrained-gpd-review-text-rendering",context={"source":digest(source)},
       inputs=[source,old/"manifest.json",Path(__file__),here/"publish.sbatch"],
       outputs=outputs,metrics={"scientific_results_changed":False,"numerical_checks_rerun":False})
old_zip=audit/"review-packages/p3-constrained-validation-v1.zip"
with zipfile.ZipFile(old_zip) as z:
    old_index=json.loads(z.read("bundle-index.json"))
files={}
for name,record in old_index.items():
    files[name]=(out/name.removeprefix("review/")) if name.startswith("review/") else Path(record["server_path"])
for path in old.iterdir():
    if path.is_file():
        files["prior-review/"+path.name]=path
files["review-code/publish.py"]=Path(__file__)
files["review-code/publish.sbatch"]=here/"publish.sbatch"
index={name:{"sha256":digest(path),"server_path":str(path),"bytes":path.stat().st_size} for name,path in files.items()}
archive=audit/"review-packages/p3-constrained-validation-v3.zip"
with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as z:
    for name,path in files.items():z.write(path,name)
    z.writestr("bundle-index.json",json.dumps(index,sort_keys=True,indent=2)+"\n")
write_once(archive.with_suffix(".json"),{"archive_sha256":digest(archive),"files":len(index),"bytes":archive.stat().st_size,"report_manifest_sha256":digest(out/"manifest.json")})
print("REVIEW_TEXT_COMPLETE",archive,flush=True)
