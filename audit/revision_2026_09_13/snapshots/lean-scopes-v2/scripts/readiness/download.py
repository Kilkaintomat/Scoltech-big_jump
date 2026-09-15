"""Pin and download the first preregistered general-purpose deduction model."""
import sys
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from onebigjump.e1.artifacts import digest, finish, read_json, write_once

root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=True)
pin_path = root / "pin.json"
if not pin_path.exists():
    info = HfApi().model_info("Qwen/Qwen2.5-7B-Instruct", files_metadata=True)
    write_once(pin_path, {"model_id": info.id, "revision": info.sha})
pin = read_json(pin_path)
path = Path(snapshot_download(repo_id=pin["model_id"], revision=pin["revision"],
    allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.jinja", "README.md"], max_workers=4))
files = sorted(p for p in path.rglob("*") if p.is_file())
record = write_once(root / "model.json", {**pin, "model_path": str(path), "files": {str(p): digest(p) for p in files}})
finish(root, stage="deduction-model-download", context=pin, inputs=[pin_path,Path(__file__)],
       outputs=[record], metrics={"files": len(files), "revision": pin["revision"]})
print(record, flush=True)
