"""What is in paper_outputs and results, and which run actually produced it?

Read-only. Cross-references every manifest against the artefacts it claims, verifies the recorded
digests still match, and reports where two different runs write the same published filename.
"""

import hashlib
import json
import pathlib

ROOT = pathlib.Path(".")


def digest(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


print("=" * 78)
print("A. MANIFESTS")
print("=" * 78)
mans = sorted(ROOT.glob("results/**/manifest.json")) + sorted(ROOT.glob("data/**/manifest.json"))
docs = []
for m in mans:
    d = json.loads(m.read_text())
    d["_path"] = str(m)
    docs.append(d)
    env = d.get("environment", {})
    g = env.get("git", {})
    hw = env.get("hardware", {})
    name = d.get("name")
    kind = d.get("kind")
    status = d.get("status")
    print()
    print(m)
    print("  name      : {}   kind={}  status={}".format(name, kind, status))
    print("  started   : {}  dur={}s".format(d.get("started_at"), d.get("duration_s")))
    print(
        "  git       : commit={} dirty={} source={}".format(
            g.get("commit"), g.get("dirty"), g.get("source", "<field absent>")
        )
    )
    print("  remote    : {}".format(g.get("remote")))
    print("  platform  : {}".format(str(hw.get("platform"))[:58]))
    print("  torch     : {}".format(env.get("packages", {}).get("torch")))
    print("  reproducible flag : {}".format(d.get("reproducible")))
    outs = d.get("outputs", [])
    print("  outputs   : {}".format(len(outs)))
    for o in outs:
        p = ROOT / o["path"]
        if not p.exists():
            print("      MISSING   {:9s} {}".format(o.get("role", "?"), o["path"]))
            continue
        recorded = o.get("digest") or ""
        now = digest(p)
        mark = "ok      " if recorded and now.startswith(recorded[:16]) else "MISMATCH"
        print("      {}  {:9s} {}".format(mark, o.get("role", "?"), o["path"]))

print()
print("=" * 78)
print("B. PUBLISHED-FILENAME COLLISIONS (paper_outputs)")
print("=" * 78)
claims: dict[str, list[str]] = {}
for d in docs:
    for o in d.get("outputs", []):
        if o["path"].startswith("paper_outputs/"):
            claims.setdefault(o["path"], []).append("{} ({})".format(d.get("name"), d["_path"]))
for path, names in sorted(claims.items()):
    uniq = sorted(set(names))
    flag = "   <-- WRITTEN BY MORE THAN ONE RUN" if len(uniq) > 1 else ""
    print("  {}{}".format(path, flag))
    for n in uniq:
        print("        {}".format(n))
if not claims:
    print("  (no manifest records a paper_outputs path)")

print()
print("=" * 78)
print("C. paper_outputs FILES WITH NO MANIFEST CLAIM")
print("=" * 78)
claimed = set(claims)
for p in sorted(ROOT.glob("paper_outputs/**/*")):
    if p.is_file() and str(p) not in claimed:
        print("  unclaimed: {}".format(p))
