"""Render validation from actual JUnit and Slurm records; run inside the test container."""
from pathlib import Path
import json
import os
import sys
import xml.etree.ElementTree as ET

from onebigjump.e1.artifacts import environment, digest, write_once

root = Path("/beegfs/home/denis.rakhmankin/onebigjump")
out = root / "audit/revision_2026_09_09"
checks_job = sys.argv[1]
inputs = [Path(__file__), out / "slurm-accounting.tsv"]
runtime = Path("/gpfs/gpfs0/denis.rakhmankin/onebigjump-tools/lean-runtime.tar")
inputs += [runtime, runtime.with_suffix(".tar.sha256")]
gpu_path = root / "runs/e1_20260908T171727Z/checks/prover-preflight-8462759/manifest.json"
from onebigjump.e1.artifacts import verify_manifest
verify_manifest(gpu_path)
gpu = json.loads(gpu_path.read_text())
if not gpu["metrics"]["passed"]:
    raise RuntimeError("GPU preflight did not pass")
inputs.append(gpu_path)
results = []
for kind in ("make-test", "make-test-all"):
    path = out / (kind + "-" + checks_job + ".xml")
    tree = ET.parse(path)
    cases = list(tree.iter("testcase"))
    failures = sum(x.find("failure") is not None for x in cases)
    errors = sum(x.find("error") is not None for x in cases)
    skipped = sum(x.find("skipped") is not None for x in cases)
    row = {"check": kind, "tests": len(cases), "passed": len(cases)-failures-errors-skipped,
           "failures": failures, "errors": errors, "skipped": skipped,
           "lean_tests": sum("test_lean_verification" in x.get("classname","") for x in cases)}
    if errors or failures or (kind == "make-test-all" and (skipped or not row["lean_tests"])):
        raise RuntimeError("final validation is not fully successful: " + repr(row))
    results.append(row)
    inputs.append(path)
smokes = []
for path in sorted((root / "runs/e1_20260908T171727Z/checks").glob("lean-smoke-*/summary.json")):
    result = json.loads(path.read_text())
    if result["passed"]:
        smokes.append({"path":str(path), **result})
        inputs.append(path)
if not smokes:
    raise RuntimeError("successful live E1 smoke is required")
result = {"checks_job":checks_job,"checks":results,"live_smoke":smokes[-1],"gpu_preflight":gpu,"environment":environment()}
metrics = write_once(out / ("validation-" + checks_job + ".json"), result)
inputs.append(metrics)
lines = ["# Проверки ревизии 9 сентября 2026", "",
         "Отчёт создан программой из JUnit XML и результатов живых Lean-проверок.",
         "", "Slurm job полного прогона: `" + checks_job + "`.", "",
         "| Проверка | Passed | Failures | Errors | Skipped |", "|---|---:|---:|---:|---:|"]
for row in results:
    lines.append("| {check} | {passed} | {failures} | {errors} | {skipped} |".format(**row))
smoke = smokes[-1]
lines += ["", "Живые E1 fixtures: " + str(smoke["fixtures"]) + ", failed: " + str(len(smoke["failed"])) + ".",
          "Проверено исходных statements: " + str(smoke["source_statements"]) + ".",
          "Полные ответы Lean: `" + str(Path(smoke["path"]).parent) + "`.",
          "", "DeepSeek-Prover-7B: GPU engine preflight пройден; Slurm job " + gpu["environment"]["slurm_job_id"] + ".",
          "Slurm accounting: [slurm-accounting.tsv](slurm-accounting.tsv).",
          "", "Неуспешные прогоны сохранены отдельно. Ошибки чтения BeeGFS не считаются проверками kernel labels.",
          "", "Запуски эксперимента записываются в `runs/e1_20260908T171727Z/pilot/submission-*.json`.",
          "Это development pilot; подтверждающий main protocol ещё не завершён.", ""]
report = out / "VALIDATION.md"
report.write_text("\n".join(lines), encoding="utf-8")
manifest = {"stage":"code-revision-validation","config":{"checks_job":checks_job},
            "git_commit":os.getenv("ONEBIGJUMP_GIT_COMMIT"),
            "git_dirty":bool(os.environ["ONEBIGJUMP_GIT_STATUS"]) if "ONEBIGJUMP_GIT_STATUS" in os.environ else None,
            "environment":environment(),
            "inputs":{str(p):digest(p) for p in inputs},
            "outputs":{str(report):digest(report),str(metrics):digest(metrics)}}
write_once(out / ("validation-" + checks_job + "-manifest.json"),manifest)
print(report)
