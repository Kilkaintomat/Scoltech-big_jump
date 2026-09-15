"""Freeze model-specific protocols and compute exact pre-generation campaign accounting."""

import copy
import shutil
import sys
from collections import Counter
from pathlib import Path

from transformers import AutoConfig, AutoTokenizer

from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.generation import planned_requests
from onebigjump.models.generation import assert_tokenizer_roundtrips

campaign = Path(sys.argv[1]).resolve()
source = Path(__file__).resolve().parents[2] / "source-manifest.json"
verify_manifest(source)
base = Path("/beegfs/home/denis.rakhmankin/onebigjump/runs/e1_20260908T171727Z")
statement_checks = base / "checks/lean-smoke-smoke-20260909T142259Z/statement-checks.json"
verify_manifest(statement_checks.parent / "manifest.json")
bad = [
    r["problem_id"]
    for r in read_json(statement_checks)
    if not r["elaborates"] or r["already_imported"]
]
summary = {}
artifacts = []
for name in ("deepseek", "goedel", "kimina"):
    root = campaign / name
    root.mkdir(parents=True, exist_ok=True)
    ready = read_json(campaign / "models" / name / "ready.json")
    verify_manifest(campaign / "models" / name / "sealed/manifest.json")
    for folder in ("inputs", "checks", "main"):
        (root / folder).mkdir(exist_ok=True)
    for p in (base / "inputs").iterdir():
        if p.is_file():
            if name != "deepseek" and p.name in {
                "input-versions.json",
                "input-digests.json",
                "model-card.md",
            }:
                continue
            target = root / "inputs" / p.name
            if not target.exists():
                shutil.copy2(p, target)
            elif digest(target) != digest(p):
                raise ValueError("changed original inputs")
    if name != "deepseek":
        card = Path(ready["model_path"]) / "README.md"
        destination = root / "inputs/model-card.md"
        if not destination.exists():
            shutil.copy2(card, destination)
        elif digest(destination) != digest(card):
            raise ValueError("model card changed")
        versions = read_json(base / "inputs/input-versions.json")
        versions.update(
            model=ready["model_id"],
            model_revision=ready["revision"],
            tokenizer_revision=ready["revision"],
        )
        artifacts.append(write_once(root / "inputs/input-versions.json", versions))
        artifacts.append(
            write_once(
                root / "inputs/input-digests.json",
                {
                    p.name: digest(p)
                    for p in (root / "inputs").iterdir()
                    if p.is_file() and p.name != "input-digests.json"
                },
            )
        )
    if name == "deepseek":
        if not (root / "pilot").exists():
            (root / "pilot").symlink_to(base / "pilot", target_is_directory=True)
        for p in (base / "checks").glob("lean-smoke-*"):
            if not (root / "checks" / p.name).exists():
                (root / "checks" / p.name).symlink_to(p, target_is_directory=True)
    config = copy.deepcopy(read_json(base / "pilot/protocol.json"))
    config.update(
        model_id=ready["model_id"],
        revision=ready["revision"],
        tokenizer_revision=ready["revision"],
        model_path=ready["model_path"],
    )
    model_config = AutoConfig.from_pretrained(ready["model_path"], local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(ready["model_path"], local_files_only=True)
    assert_tokenizer_roundtrips(tokenizer, ready["model_id"])
    if model_config.num_hidden_layers != ready["layers"]:
        raise ValueError("model architecture differs from download metadata")
    layers = ready["layers"]
    config["layers"] = [layers // 4 - 1, layers // 2 - 1, 3 * layers // 4 - 1]
    config["primary_layer"] = layers // 2 - 1
    config["prompt_style"] = "kimina" if name == "kimina" else "deepseek"
    config["inputs"] = {k: digest(root / "inputs" / k) for k in config["inputs"]}
    if name != "deepseek":
        config["run_id"] = root.name
        config["version"] = "three-prover-development-v1"
        artifacts.append(write_once(root / "pilot/protocol.json", config))
    main = copy.deepcopy(config)
    main.update(
        version="three-prover-full-collection-v1",
        run_id=str(root),
        statement_checks=str(statement_checks),
        statement_exclusions=bad,
        n_shards=8,
        collection_only_gate=True,
    )
    main["statistics"]["permutations"] = 2000
    main["statistics"]["family_size"] = 9
    main["campaign_protocol_sha256"] = digest(source.parent / "docs/e1/CAMPAIGN.md")
    artifacts.append(write_once(root / "main/protocol.json", main))
    for label, origin in (
        ("model-digests.json", campaign / "models" / name / "model-digests.json"),
        ("container-digest.json", base / "checks/container-digest.json"),
    ):
        target = root / "checks" / label
        if not target.exists():
            shutil.copy2(origin, target)
        elif digest(target) != digest(origin):
            raise ValueError("changed model/container")
    # All new experiment data is written to GPFS; only receipts live in the working tree.
    for phase in ("main",) if name == "deepseek" else ("pilot", "main"):
        for stage in (
            "generation",
            "verification",
            "extraction",
            "measurement",
            "analysis",
            "collection-gate",
        ):
            destination = (
                Path("/gpfs/gpfs0/denis.rakhmankin/onebigjump-runs")
                / campaign.name
                / name
                / phase
                / stage
            )
            destination.mkdir(parents=True, exist_ok=True)
            link = root / phase / stage
            link.parent.mkdir(parents=True, exist_ok=True)
            if not link.exists():
                link.symlink_to(destination, target_is_directory=True)
    requests = planned_requests(root, "main", main)
    population = {r["problem_id"]: r["role"] for r in requests}
    shards = [len(planned_requests(root, "main", main, i, 8)) for i in range(8)]
    summary[name] = {
        **ready,
        "root": str(root),
        "main_attempts": len(requests),
        "problems_by_role": dict(Counter(population.values())),
        "shard_attempts": shards,
        "max_generated_tokens": len(requests) * main["max_new_tokens"],
        "pilot_attempts": len(planned_requests(root, "pilot", config)),
        "statement_exclusions": bad,
    }
path = write_once(campaign / "population.json", summary)
lines = [
    "# Three-model Lean campaign",
    "",
    "| Model | Calibration problems | Evaluation problems | Main attempts |",
    "|---|---:|---:|---:|",
]
for row in summary.values():
    lines.append(
        f"| {row['model_id']} | {row['problems_by_role'].get('calibration', 0)} | {row['problems_by_role'].get('evaluation', 0)} | {row['main_attempts']} |"
    )
lines += [
    "",
    "8 attempts per temperature; T=0.6 and T=1.0. Exact revisions and shard counts: population.json.",
    "Collection begins only after a complete technically valid pilot. A collection gate is not publication approval.",
    "No supported scientific claim before manual review and statistical calibration.",
]
report = campaign / "POPULATION.md"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
finish(
    campaign / "preparation",
    stage="freeze-three-model-campaign",
    context={"source": digest(source)},
    inputs=[
        source,
        statement_checks.parent / "manifest.json",
        *[
            campaign / "models" / n / "sealed/manifest.json"
            for n in ("deepseek", "goedel", "kimina")
        ],
    ],
    outputs=[*artifacts, path, report],
    metrics=summary,
)
print(summary, flush=True)
