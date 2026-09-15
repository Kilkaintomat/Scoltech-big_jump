"""Original-ID model measurements with independent hook checks and complete attempt accounting."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from .artifacts import Journal, digest, finish, identity
from .spans import SourceExclusion, align
from .stages import check_model, completed, configuration, generation_inputs, rows


def extract(root: Path, phase: str, source: Path, shard: int = 0, n_shards: int = 1) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from ..models.hooks import record_residuals

    config = configuration(root, phase)
    directory = root / phase / "extraction"
    if n_shards != 1:
        directory = directory / f"shard-{shard:03d}-of-{n_shards:03d}"
    if completed(directory):
        return
    samples, manifests = generation_inputs(root, phase)
    labels_path = root / phase / "verification"
    if not completed(labels_path):
        raise ValueError("verification must complete before extraction")
    labels = {r["trace_id"]: r for r in rows(labels_path / "labels.jsonl")}
    if set(labels) != {s["trace_id"] for s in samples}:
        raise ValueError("labels do not account for every generation attempt")
    if any(r["unexplained_disagreement"] for r in labels.values()):
        raise ValueError("unexplained verifier disagreement")
    from .generation import planned_requests

    selected = {r["trace_id"] for r in planned_requests(root, phase, config, shard, n_shards)}
    samples = [r for r in samples if r["trace_id"] in selected]
    check_model(root, config)
    if not torch.cuda.is_available():
        raise RuntimeError("real-prover extraction requires an allocated GPU")
    model = (
        AutoModelForCausalLM.from_pretrained(
            config["model_path"],
            torch_dtype=torch.bfloat16,
            local_files_only=True,
            attn_implementation="sdpa",
        )
        .to("cuda")
        .eval()
    )
    tokenizer = AutoTokenizer.from_pretrained(config["model_path"], local_files_only=True)
    context = {
        "source": digest(source),
        "config": digest(root / phase / "protocol.json"),
        "verification": digest(labels_path / "manifest.json"),
    }
    layers = config["layers"]
    with Journal(directory / "trajectories.jsonl", context) as journal:
        checked = {r.get("category") for r in journal.rows.values() if r.get("forward_check")}
        for sample in samples:
            label = labels[sample["trace_id"]]
            request = identity([sample, label])
            if journal.existing(sample["trace_id"], request) is not None:
                continue
            row: dict[str, Any] = {
                "trace_id": sample["trace_id"],
                "problem_id": sample["problem_id"],
                "role": sample["role"],
                "temperature": sample["temperature"],
                "task_family": sample["task_family"],
                "category": label["category"],
                "extraction_status": "excluded_by_verification",
            }
            try:
                if label["category"] in {
                    "verified",
                    "localized_tactic_failure",
                    "terminal_unsolved_goals",
                    "sorry_invalid_proof",
                    "timeout_resource",
                } and label.get("steps"):
                    alignment = align(
                        tokenizer,
                        sample["prompt_token_ids"],
                        sample["completion_token_ids"],
                        sample["completion"],
                        label["step_spans"],
                    )
                    ids = sample["prompt_token_ids"] + sample["completion_token_ids"]
                    inputs = torch.tensor([ids], device="cuda")
                    positions = alignment["positions"]
                    with torch.inference_mode(), record_residuals(model, layers, positions) as rec:
                        output = model(input_ids=inputs, use_cache=False)
                    token_lp = []
                    for start in range(0, len(ids) - 1, 128):
                        end = min(start + 128, len(ids) - 1)
                        logits = output.logits[0, start:end].float()
                        target = inputs[0, start + 1 : end + 1]
                        lp = logits.gather(1, target[:, None]).squeeze(1) - logits.logsumexp(-1)
                        token_lp.extend(lp.cpu().tolist())
                    del output
                    arrays = {f"states_{layer}": rec.captures[layer].numpy() for layer in layers}
                    arrays["surprisal"] = np.array(
                        [
                            -np.mean(token_lp[lo - 1 : hi])
                            for lo, hi in alignment["step_token_spans_inclusive"]
                        ],
                        dtype=np.float64,
                    )
                    if not all(np.isfinite(a).all() for a in arrays.values()):
                        raise ValueError(
                            "nonfinite residual states or realised-token log probabilities"
                        )
                    if label["category"] not in checked:
                        with torch.inference_mode():
                            independent = model(
                                input_ids=inputs, use_cache=False, output_hidden_states=True
                            )
                        checks = {}
                        for layer in layers:
                            actual = (
                                independent.hidden_states[layer + 1][0, positions].float().cpu()
                            )
                            captured = rec.captures[layer]
                            checks[str(layer)] = {
                                "max_abs_error": float((actual - captured).abs().max()),
                                "passed": bool(
                                    torch.allclose(actual, captured, atol=1e-5, rtol=1e-5)
                                ),
                            }
                        del independent
                        if not all(x["passed"] for x in checks.values()):
                            raise RuntimeError(
                                f"independent residual forward check failed: {checks}"
                            )
                        row["forward_check"] = checks
                        checked.add(label["category"])
                    # Cross-backend agreement is measured, never asserted to be bitwise identity.
                    generation_lp = np.array(sample["generation_token_logprobs"])
                    hf_lp = np.array(token_lp[len(sample["prompt_token_ids"]) - 1 :])
                    if len(generation_lp) != len(hf_lp):
                        raise ValueError("generation/HF probability alignment mismatch")
                    error = np.abs(generation_lp - hf_lp)
                    row["backend_logprob_comparison"] = {
                        "n": len(error),
                        "mean_abs_error": float(error.mean()),
                        "max_abs_error": float(error.max()),
                    }
                    artifact = directory / "states" / (identity(sample["trace_id"]) + ".npz")
                    artifact.parent.mkdir(parents=True, exist_ok=True)
                    temporary = artifact.with_suffix(".tmp")
                    with temporary.open("wb") as stream:
                        np.savez_compressed(stream, allow_pickle=False, **arrays)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, artifact)
                    row.update(
                        extraction_status="extracted",
                        alignment=alignment,
                        states_path=str(artifact),
                        states_sha256=digest(artifact),
                        n_steps=len(label["steps"]),
                    )
            except SourceExclusion as exc:
                row.update(extraction_status=exc.category, error=str(exc))
            journal.append(row, request)
            print(
                "extracted",
                len(journal.rows),
                "/",
                len(samples),
                row["trace_id"],
                row["extraction_status"],
                flush=True,
            )
        values = list(journal.rows.values())
    outputs = [directory / "trajectories.jsonl", directory / "trajectories.identity.json"]
    outputs.extend(Path(r["states_path"]) for r in values if r["extraction_status"] == "extracted")
    finish(
        directory,
        stage="extraction",
        context=context,
        inputs=[
            source,
            root / phase / "protocol.json",
            labels_path / "manifest.json",
            root / "checks/model-digests.json",
            root / "checks/container-digest.json",
            *manifests,
        ],
        outputs=outputs,
        metrics={
            "attempts": len(values),
            "extracted": sum(r["extraction_status"] == "extracted" for r in values),
            "forward_checked_categories": sorted(checked),
        },
    )
