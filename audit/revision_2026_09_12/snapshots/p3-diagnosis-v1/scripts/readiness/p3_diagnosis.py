"""Run the independent P3 audit from an immutable source tree."""
import argparse
from pathlib import Path
from onebigjump.e1.artifacts import verify_manifest
from onebigjump.readiness.p3_diagnosis import run, summarize

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
parser.add_argument("--shard", type=int)
a = parser.parse_args()
source = Path(__file__).resolve().parents[2] / "source-manifest.json"
verify_manifest(source)
protocol = a.root / "protocol.json"
if a.shard is None:
    summarize(a.root / "summary", a.root, protocol, source)
else:
    run(a.root / f"shard-{a.shard:03d}", protocol, source, a.shard)
