"""Run an implemented E1 pilot stage from a verified immutable snapshot."""

import argparse
from pathlib import Path

from onebigjump.e1.artifacts import verify_manifest

parser = argparse.ArgumentParser()
parser.add_argument(
    "stage", choices=["generate", "verify", "extract", "measure", "analyze", "smoke"]
)
parser.add_argument("root", type=Path)
parser.add_argument("--phase", choices=["pilot", "main"], default="pilot")
parser.add_argument("--shard", type=int, default=0)
parser.add_argument("--n-shards", type=int, default=1)
a = parser.parse_args()
source = Path(__file__).resolve().parents[2] / "source-manifest.json"
verify_manifest(source)
if a.phase != "pilot":
    raise ValueError(
        "Main E1 is not released: complete the documented pilot/statistical gates first"
    )
if a.stage == "generate":
    from onebigjump.e1.generation import generate

    generate(a.root.resolve(), a.phase, source, a.shard, a.n_shards)
elif a.stage == "smoke":
    from onebigjump.e1.smoke import run

    run(a.root.resolve(), source)
else:
    if a.shard != 0 or a.n_shards != 1:
        raise ValueError("downstream stages consume all completed generation shards")
    if a.stage == "verify":
        from onebigjump.e1.stages import verify as stage
    elif a.stage == "extract":
        from onebigjump.e1.extraction import extract as stage
    elif a.stage == "measure":
        from onebigjump.e1.measurement import measure as stage
    else:
        from onebigjump.e1.analysis import analyze as stage
    stage(a.root.resolve(), a.phase, source)
