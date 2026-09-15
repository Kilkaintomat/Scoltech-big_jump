"""Pin and download the paper's three Lean provers; run on a Slurm CPU node."""

import json
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from onebigjump.e1.artifacts import digest, finish, read_json, write_once

root = Path(sys.argv[1]).resolve()
models = {
    "deepseek": ("deepseek-ai/DeepSeek-Prover-V2-7B", "a8d9e14432b2e8dd9df2a4d4e70f1ba9bc8d9b7b"),
    "goedel": ("Goedel-LM/Goedel-Prover-V2-8B", None),
    "kimina": ("AI-MO/Kimina-Prover-Distill-8B", None),
}
api = HfApi()
for name, (model_id, revision) in models.items():
    directory = root / "models" / name
    pin_path = directory / "pin.json"
    if pin_path.exists():
        pin = read_json(pin_path)
    else:
        info = api.model_info(model_id, revision=revision, files_metadata=True)
        pin = {
            "model_id": model_id,
            "revision": info.sha,
            "tokenizer_revision": info.sha,
            "files": [{"name": f.rfilename, "size": f.size} for f in info.siblings],
        }
        write_once(pin_path, pin)
    print("DOWNLOAD", name, pin["revision"], flush=True)
    path = Path(
        snapshot_download(
            repo_id=model_id,
            revision=pin["revision"],
            allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.jinja", "README.md"],
            max_workers=4,
        )
    )
    config = read_json(path / "config.json")
    index = read_json(path / "model.safetensors.index.json")
    for shard in set(index["weight_map"].values()):
        if not (path / shard).is_file():
            raise FileNotFoundError(shard)
    hashes = {p.name: digest(p) for p in path.iterdir() if p.is_file()}
    manifest = write_once(directory / "model-digests.json", hashes)
    result = write_once(
        directory / "ready.json",
        {
            "model_id": model_id,
            "revision": pin["revision"],
            "model_path": str(path),
            "layers": config["num_hidden_layers"],
            "hidden_size": config["hidden_size"],
            "model_type": config["model_type"],
            "bytes": sum(p.stat().st_size for p in path.iterdir() if p.is_file()),
        },
    )
    if not (directory / "manifest.json").exists():
        finish(
            directory,
            stage="model-download",
            context={"slurm_job_id": os.getenv("SLURM_JOB_ID")},
            inputs=[Path(__file__), pin_path],
            outputs=[manifest, result],
            metrics=read_json(result),
        )
    print("READY", json.dumps(read_json(result)), flush=True)
