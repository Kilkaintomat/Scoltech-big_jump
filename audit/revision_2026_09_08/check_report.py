from pathlib import Path
from onebigjump.reporting.report import build_report, _provenance
from onebigjump.manifests import run_manifest
from onebigjump.reproducibility import file_digest
out=Path("audit/revision_2026_09_08")
with run_manifest("revision-server-report", "audit", out, config={"archive_digest":file_digest(out/"zhores-baseline.tar.gz")}) as man:
    for git in ({}, {"commit":None,"dirty":False}, {"commit":"a"*40,"dirty":None}):
        assert "unknown provenance" in _provenance({"environment":{"git":git}})
    assert "(clean)" in _provenance({"environment":{"git":{"commit":"a"*40,"dirty":False}}})
    assert "dirty working tree" in _provenance({"environment":{"git":{"commit":"a"*40,"dirty":True}}})
    text=build_report(out/"baseline")
    assert "grokking_null" in text
    assert "commit `unknown` (clean)" not in text
    path=out/"ARCHIVE_REPORT.md"
    path.write_text("> Historical archive rendered on Zhores with the corrected reporter. See REPORT.md for limitations.\n\n"+text)
    man.add_metric("provenance_cases_passed",5)
    man.add_output(path,"audit-report")
    man.add_output(out/"server-tests.xml","test-evidence")
    man.add_output(out/"server-tests.log","test-evidence")
print("Server report checks passed.")
