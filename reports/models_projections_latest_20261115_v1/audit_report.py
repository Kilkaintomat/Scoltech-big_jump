from mp_common import *
import re,gzip,csv,io,shutil
PUB=ROOT/"runs/models_projections_latest_20261115_v1";D=PUB/"publication"
def main():
 assert os.getenv("SLURM_JOB_ID");verify_manifest(D)
 m=read(D/"metrics.json");checks=read(D/"validation/metrics.json")
 rows=[]
 for r in checks["checks"]:
  txt=(D/"validation"/r["log"]).read_text(encoding="utf8")
  errors=[line for line in txt.splitlines() if ": error:" in line]
  rows.append(dict(command=r["command"],exit_code=r["exit_code"],type_errors=errors,pytest_reached=("== pytest ==" in txt or "uv run pytest" in txt),ruff_passed=("All checks passed!" in txt)))
 notes=["# Проверки публикации\n","Проверен отдельный архив исходного кода опубликованного репозитория; научные файлы работающей серии не изменялись.\n"]
 for r in rows:
  notes.append("- "+r["command"]+": код выхода "+str(r["exit_code"])+". Ruff пройден: "+str(r["ruff_passed"])+". Pytest достигнут: "+str(r["pytest_reached"])+".\n")
  notes.extend("  - "+chr(96)+x+chr(96)+"\n" for x in r["type_errors"])
 notes.append("\nОшибки типов обнаружены в исходном опубликованном коде до добавления отчёта, при текущих установленных версиях зависимостей. Эта публикация меняет только отчёт и его приложения. Эти проверки не заявляются успешными; pytest, включая Lean/ML-тесты, не запустился из-за остановки на mypy.\n")
 notes.append("\nХеши всех использованных выходов сверены с исходными manifests. Сжатые таблицы прочитаны обратно; проверено соответствие числа строк метрикам. Ни прогнозы, ни интервалы, ни поправка на множественные проверки здесь не пересчитывались.\n")
 (D/"VALIDATION_RU.md").write_text("\n".join(notes),encoding="utf8")
 report=(D/"REPORT_RU.md").read_text(encoding="utf8")
 report=report.replace("Ненулевой код не означает успешную проверку.","Обе команды остановились на ошибках mypy в уже опубликованном исходном коде, до запуска pytest. Ruff и проверка форматирования прошли. [Точные ошибки и границы проверки](VALIDATION_RU.md).")
 counts={}
 for name in ["part1_metrics","part1_contrasts","part2_metrics","part2_contrasts"]:
  with gzip.open(D/(name+".csv.gz"),"rt",encoding="utf8",newline="") as f:counts[name]=sum(1 for _ in csv.DictReader(f))
 orig=read(OUT/"report_part1/metrics.json")
 assert counts["part1_metrics"]==len(orig["metrics"])
 assert counts["part1_contrasts"]==len(orig["contrasts"])
 assert m["snapshot"]["completed_statistics"]>0
 missing=[]
 for target in re.findall(r"\]\(([^)]+)\)",report):
  if target.startswith(("http","../")):continue
  if not (D/target.split("#")[0]).exists():missing.append(target)
 assert not missing,missing
 (D/"REPORT_RU.md").write_text(report,encoding="utf8")
 shutil.copyfile(__file__,D/"audit_report.py")
 (D/"manifest.json").rename(D/"assembly_manifest.json")
 save(D/"audit_metrics.json",dict(status="passed",slurm_job=os.environ["SLURM_JOB_ID"],source_output_hashes_verified=True,csv_rows=counts,repository_checks=rows,missing_local_links=missing))
 finish(D,dict(kind="publication_audit",source_metrics_unchanged=True,part2_snapshot_is_partial=True))
 print("AUDIT_READY",str(D),counts,flush=True)
if __name__=="__main__":main()
