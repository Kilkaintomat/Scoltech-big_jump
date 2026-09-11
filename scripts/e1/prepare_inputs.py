"""Freeze original benchmark files and record every pre-generation eligibility decision."""

import hashlib
import json
import platform
import sys
import urllib.request
from pathlib import Path

from onebigjump.lean.problems import (
    has_declaration,
    header_directives,
    modernise_binders,
    open_for_tactics,
)

ROOT = Path(sys.argv[1])
ROOT.mkdir(parents=True, exist_ok=True)
REV = "70a1249ce240667f6bcdd1ccd62f847f0e065d57"
MODEL_REV = "a8d9e14432b2e8dd9df2a4d4e70f1ba9bc8d9b7b"


def dump(name, obj):
    p = ROOT / name
    if p.exists():
        raise FileExistsError(p)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get(url, name):
    p = ROOT / name
    if p.exists():
        raise FileExistsError(p)
    data = urllib.request.urlopen(url, timeout=90).read()
    p.write_bytes(data)
    return data


rows = []
for split, filename in [("test", "test.jsonl"), ("validation", "valid.jsonl")]:
    raw = get(
        f"https://huggingface.co/datasets/cat-searcher/minif2f-lean4/resolve/{REV}/{filename}",
        f"original-{filename}",
    )
    for index, line in enumerate(raw.decode("utf-8").splitlines()):
        if not line.strip():
            continue
        record = json.loads(line)
        statement = record.get("formal_statement", "").strip()
        pid = str(record.get("id", f"{split}-{index}"))
        eligible = bool(statement) and has_declaration(statement)
        rows.append(
            {
                "problem_id": pid,
                "split": split,
                "original_row": index,
                "original_statement": statement,
                "original_header": record.get("header", ""),
                "eligible": eligible,
                "exclusion": None if eligible else "source_has_no_live_declaration",
                "statement": modernise_binders(open_for_tactics(statement)) if eligible else None,
                "directives": header_directives(record.get("header", "")),
                "informal_statement": record.get("informal_statement", ""),
                "task_family": pid.split("_")[0],
                "record_sha256": hashlib.sha256(line.encode()).hexdigest(),
            }
        )
dump("benchmark-inventory.json", rows)
dump(
    "input-versions.json",
    {
        "dataset": "cat-searcher/minif2f-lean4",
        "dataset_revision": REV,
        "model": "deepseek-ai/DeepSeek-Prover-V2-7B",
        "model_revision": MODEL_REV,
        "tokenizer_revision": MODEL_REV,
        "python": platform.python_version(),
    },
)
get(
    f"https://huggingface.co/deepseek-ai/DeepSeek-Prover-V2-7B/raw/{MODEL_REV}/README.md",
    "model-card.md",
)
dump(
    "input-digests.json",
    {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file()},
)
print(
    json.dumps(
        {
            "counts": {
                s: {
                    "original": sum(r["split"] == s for r in rows),
                    "eligible": sum(r["split"] == s and r["eligible"] for r in rows),
                }
                for s in ["test", "validation"]
            },
            "excluded": [r for r in rows if not r["eligible"]],
        },
        ensure_ascii=False,
        indent=2,
    )
)
