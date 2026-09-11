"""Fill Kimina's cache concurrently; the main downloader owns readiness receipts."""

import sys
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from onebigjump.e1.artifacts import read_json, write_once

root = Path(sys.argv[1])
model_id = "AI-MO/Kimina-Prover-Distill-8B"
pin_path = root / "models/kimina/pin.json"
if not pin_path.exists():
    info = HfApi().model_info(model_id, files_metadata=True)
    write_once(
        pin_path,
        {
            "model_id": model_id,
            "revision": info.sha,
            "tokenizer_revision": info.sha,
            "files": [{"name": f.rfilename, "size": f.size} for f in info.siblings],
        },
    )
pin = read_json(pin_path)
print("PREFETCH", pin["model_id"], pin["revision"], flush=True)
snapshot_download(
    repo_id=model_id,
    revision=pin["revision"],
    allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.jinja", "README.md"],
    max_workers=4,
)
print("CACHE COMPLETE; authoritative download job will verify all files", flush=True)
