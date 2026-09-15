"""Validate Git's staged bytes against captured source/evidence manifests and JUnit receipts.

Run on the host after the Slurm validation job and final git add. This does no scientific
analysis: it checks the transport package. Generated receipts are intentionally not self-hashed.
"""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
JOB = "8468381"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=str(ROOT))


def staged_bytes(path):
    return git("show", ":" + path)


summaries = {}
for kind in ("fast", "full"):
    path = HERE / (kind + "-" + JOB + ".xml")
    suites = list(ET.parse(str(path)).getroot().iter("testsuite"))
    counts = {k: sum(int(s.attrib[k]) for s in suites) for k in ("tests", "errors", "failures", "skipped")}
    counts["seconds"] = sum(float(s.attrib["time"]) for s in suites)
    assert counts["tests"] > 0 and not any(counts[k] for k in ("errors", "failures", "skipped")), counts
    summaries[kind] = counts

log = (HERE / ("validation-" + JOB + ".log")).read_text(encoding="utf-8")
assert "All checks passed!" in log and "123 files already formatted" in log
assert "Success: no issues found in 71 source files" in log

inventory = json.loads((HERE / "source-inventory.json").read_text(encoding="utf-8"))
export = json.loads((ROOT / "results/campaign_20260916/export-manifest.json").read_text(encoding="utf-8"))
exceptions = {"README.md", "STATUS.md", ".gitattributes"}
checked_source = checked_evidence = 0
for record in inventory["files"]:
    if record["path"] in exceptions:
        continue
    assert hashlib.sha256(staged_bytes(record["path"])).hexdigest() == record["sha256"], record["path"]
    checked_source += 1
for record in export["entries"]:
    assert hashlib.sha256(staged_bytes(record["path"])).hexdigest() == record["sha256"], record["path"]
    checked_evidence += 1

# Scan only newly added/changed files. Never print candidate credentials.
paths = [p for p in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0") if p]
patterns = [rb"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----", rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})", rb"\bhf_[A-Za-z0-9]{30,}\b", rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}", rb"\bAKIA[0-9A-Z]{16}\b"]
for rel in paths:
    data = staged_bytes(rel)
    assert len(data) <= 10 * 1024 * 1024, "large staged file: " + rel
    assert not (ROOT / rel).is_symlink(), "staged symlink: " + rel
    assert not any(re.search(p, data) for p in patterns), "credential pattern in: " + rel
assert not git("diff", "--cached", "--name-only", "--", "paper_outputs").strip()
git("diff", "--cached", "--check", "--", ".gitattributes", "README.md", "STATUS.md", "docs", "configs", "src", "scripts", "tests")

receipt = {
    "validated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "base_commit": git("rev-parse", "HEAD").decode().strip(),
    "slurm_validation_job": JOB,
    "test_suites": summaries,
    "lint": {"ruff": "passed", "format_files": 123, "mypy_source_files": 71},
    "source_files_verified_in_git_index": checked_source,
    "evidence_files_verified_in_git_index": checked_evidence,
    "publication_documentation_exceptions": sorted(exceptions),
    "changed_files_scanned": len(paths),
    "credential_pattern_hits": 0,
    "paper_outputs_unchanged": True,
    "scope": "Current src/scripts/tests validated using pinned installed environment in isolated publication checkout. Historical snapshots retain original bytes and are not claimed to have been re-executed. Original REPO provides container and Lean assets; E1_SNAPSHOT/PYTHONPATH point to publication checkout. The environment's original dirty-tree provenance warning is retained, not retroactively relabeled.",
}
(HERE / "validation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = ["# Publication validation — 16 September 2026", "",
    "Validation ran on Zhores through Slurm job `" + JOB + "` in the isolated publication checkout.",
    "The commands in `validation.sbatch` implement the repository's `make test` and `make test-all`",
    "checks using the existing pinned environment rather than installing dependencies again.", "",
    "- Ruff lint and formatting: passed.", "- Mypy: passed."]
for kind in ("fast", "full"):
    c = summaries[kind]
    lines.append("- " + kind.capitalize() + " pytest suite: " + str(c["tests"]) + " passed; " + str(c["failures"]) + " failures, " + str(c["errors"]) + " errors, " + str(c["skipped"]) + " skips.")
lines += ["", "The full suite includes actual Lean and GPT-2 integration tests. JUnit XML files are retained beside this report.",
    "Source/evidence SHA-256 values were checked against Git's staged bytes, including CSV line endings.",
    "No paper-output numbers were edited. Frozen historical source snapshots remain byte-preserved;",
    "whitespace checks apply to current code and publication documentation.", "", receipt["scope"], "",
    "Model weights, large journals/activation arrays and installed third-party packages remain outside Git.",
    "See `source-inventory.json`, `validation.json` and `../../results/campaign_20260916/export-manifest.json` for machine-readable provenance.", ""]
(HERE / "VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
