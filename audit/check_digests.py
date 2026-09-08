"""Do the recorded digests still match the files on disk?

The manifest's whole purpose is that a figure can be traced to the run that made it. If a digest
no longer matches, the artefact on disk is not the artefact the manifest describes.
"""

import hashlib
import json
import pathlib

ROOT = pathlib.Path(".")
mans = sorted(ROOT.glob("results/**/manifest.json")) + sorted(ROOT.glob("data/**/manifest.json"))

print("{:<58} {:>9}  {}".format("artefact", "verdict", "run that claims it"))
print("-" * 110)
bad = ok = missing = 0
for m in mans:
    d = json.loads(m.read_text())
    for o in d.get("outputs", []):
        p = ROOT / o["path"]
        rec = (o.get("digest") or "").split(":", 1)[-1]
        if not p.exists():
            print("{:<58} {:>9}  {}".format(o["path"][:58], "MISSING", d.get("name")))
            missing += 1
            continue
        now = hashlib.sha256(p.read_bytes()).hexdigest()
        if now == rec:
            ok += 1
        else:
            bad += 1
            print("{:<58} {:>9}  {}".format(o["path"][:58], "CHANGED", d.get("name")))
print("-" * 110)
print("matches: {}   changed: {}   missing: {}".format(ok, bad, missing))
