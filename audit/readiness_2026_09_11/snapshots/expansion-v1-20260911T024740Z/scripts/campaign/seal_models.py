"""Independently verify cached model files from frozen source before campaign preparation."""

import sys
from pathlib import Path

from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once

campaign = Path(sys.argv[1]).resolve()
source = Path(__file__).resolve().parents[2] / "source-manifest.json"
verify_manifest(source)
for name in ("deepseek", "goedel", "kimina"):
    directory = campaign / "models" / name
    ready = read_json(directory / "ready.json")
    pin = read_json(directory / "pin.json")
    if pin["revision"] != ready["revision"] or pin["model_id"] != ready["model_id"]:
        raise ValueError("model identity mismatch")
    model = Path(ready["model_path"])
    expected = read_json(directory / "model-digests.json")
    actual = {p.name: digest(p) for p in model.iterdir() if p.is_file()}
    if actual != expected:
        raise ValueError("cached model files changed")
    index = read_json(model / "model.safetensors.index.json")
    if not set(index["weight_map"].values()) <= actual.keys():
        raise ValueError("missing weight shards")
    receipt = write_once(
        directory / "sealed/check.json",
        {"passed": True, "ready": ready, "files": len(actual), "hashes": actual},
    )
    finish(
        directory / "sealed",
        stage="independent-model-cache-verification",
        context={"source": digest(source)},
        inputs=[source, directory / "pin.json"],
        outputs=[receipt, directory / "ready.json", directory / "model-digests.json"],
        metrics={"passed": True, "model_id": ready["model_id"], "revision": ready["revision"]},
    )
    print("SEALED", name, flush=True)
