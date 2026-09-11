"""Run immutable campaign stages, leaving the original E1 pilot launcher unchanged."""

import argparse
from pathlib import Path

from onebigjump.e1.artifacts import verify_manifest

parser = argparse.ArgumentParser()
parser.add_argument(
    "stage",
    choices=[
        "generate",
        "verify",
        "extract",
        "measure",
        "analyze",
        "smoke",
        "gate",
        "gather-verification",
        "gather-extraction",
    ],
)
parser.add_argument("root", type=Path)
parser.add_argument("--phase", choices=["pilot", "main"], default="pilot")
parser.add_argument("--shard", type=int, default=0)
parser.add_argument("--n-shards", type=int, default=1)
a = parser.parse_args()
source = Path(__file__).resolve().parents[2] / "source-manifest.json"
verify_manifest(source)
root = a.root.resolve()
if a.stage == "gate":
    from onebigjump.e1.campaign import collection_gate

    collection_gate(root, source)
elif a.stage.startswith("gather-"):
    from onebigjump.e1.campaign import gather

    gather(root, a.phase, source, a.stage.removeprefix("gather-"), a.n_shards)
elif a.stage == "smoke":
    from onebigjump.e1.smoke import run

    run(root, source)
elif a.stage == "generate":
    from onebigjump.e1.generation import generate

    generate(root, a.phase, source, a.shard, a.n_shards)
elif a.stage in {"verify", "extract"}:
    if a.stage == "verify":
        from onebigjump.e1.stages import verify as stage
    else:
        from onebigjump.e1.extraction import extract as stage
    stage(root, a.phase, source, a.shard, a.n_shards)
elif a.stage == "measure":
    from onebigjump.e1.measurement import measure

    measure(root, a.phase, source)
else:
    if a.phase == "pilot":
        from onebigjump.e1.analysis import analyze
    else:
        from onebigjump.e1.main_analysis import analyze
    analyze(root, a.phase, source)
