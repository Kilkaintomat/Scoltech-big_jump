"""Fixed, independently seeded attempts without verifier feedback."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .artifacts import Journal, digest, finish, identity, read_json
from .verification import trusted_prefix

PLAN_REQUEST = (
    "Before producing the Lean 4 code to formally prove the given theorem, provide a detailed proof plan outlining the main proof steps and strategies.\n"
    "The plan should highlight key ideas, intermediate lemmas, and proof structures that will guide the construction of the final formal proof."
)


def prompt_content(problem: dict[str, Any], config: dict[str, Any]) -> str:
    source = (
        trusted_prefix(problem, config["lean"]["max_heartbeats"])
        + "\n\n"
        + problem["statement"]
        + "\n  sorry"
    )
    if config.get("prompt_style") == "kimina":
        informal = problem.get("informal_statement", "")
        return (
            "Think about and solve the following problem step by step in Lean 4."
            + (f"\n# Problem:{informal}" if informal else "")
            + f"\n# Formal statement:\n```lean4\n{source}\n```\n"
        )
    return f"Complete the following Lean 4 code:\n\n```lean4\n{source}\n```\n\n{PLAN_REQUEST}"


def planned_requests(
    root: Path, phase: str, config: dict[str, Any], shard: int = 0, n_shards: int = 1
) -> list[dict[str, Any]]:
    if n_shards < 1 or not 0 <= shard < n_shards:
        raise ValueError("invalid shard")
    problems = read_json(root / "inputs/problems.json")
    splits = read_json(root / "inputs/splits.json")
    chosen = (
        set(splits["pilot_calibration"] + splits["pilot_evaluation"])
        if phase == "pilot"
        else set(splits["calibration"] + splits["evaluation"])
    )
    count = config["pilot_attempts" if phase == "pilot" else "main_attempts"]
    requests = []
    for p in sorted(problems, key=lambda p: p["problem_id"]):
        pid = p["problem_id"]
        if (
            pid not in chosen
            or not p["eligible"]
            or (phase == "main" and pid in config.get("statement_exclusions", []))
            or int(identity(pid)[:16], 16) % n_shards != shard
        ):
            continue
        for temperature in config["temperatures"]:
            for attempt in range(count):
                rid = f"{phase}:{pid}:T{temperature:.1f}:a{attempt:02d}"
                requests.append(
                    {
                        "trace_id": rid,
                        "problem_id": pid,
                        "problem": p,
                        "temperature": temperature,
                        "attempt_index": attempt,
                        "seed": int(identity([config["seed"], rid])[:8], 16) % (2**31 - 1),
                        "role": (
                            "calibration" if pid in splits["pilot_calibration"] else "evaluation"
                        )
                        if phase == "pilot"
                        else p["role"],
                    }
                )
    return requests


def generate(root: Path, phase: str, source_manifest: Path, shard: int, n_shards: int) -> None:
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    from ..models.generation import assert_tokenizer_roundtrips
    from .stages import check_model, completed, configuration, pilot_gate

    config_path = root / phase / "protocol.json"
    config = configuration(root, phase)
    directory = root / phase / "generation" / f"shard-{shard:03d}-of-{n_shards:03d}"
    if completed(directory):
        return
    model_digests = root / "checks/model-digests.json"
    gate = pilot_gate(root, source_manifest)
    if phase == "main":
        from .campaign import require_collection_gate

        require_collection_gate(root, source_manifest)
    check_model(root, config)
    requests = planned_requests(root, phase, config, shard, n_shards)
    context = {
        "config_sha256": digest(config_path),
        "source_sha256": digest(source_manifest),
        "input_sha256": digest(root / "inputs/problems.json"),
        "requests_sha256": identity(requests),
        "shard": shard,
        "n_shards": n_shards,
    }
    with Journal(directory / "samples.jsonl", context) as journal:
        pending = [r for r in requests if journal.existing(r["trace_id"], identity(r)) is None]
        if pending:
            tokenizer = AutoTokenizer.from_pretrained(config["model_path"], local_files_only=True)
            assert_tokenizer_roundtrips(tokenizer, config["model_id"])
            llm = LLM(
                model=config["model_path"],
                tokenizer=config["model_path"],
                dtype="bfloat16",
                trust_remote_code=False,
                enforce_eager=True,
                gpu_memory_utilization=0.85,
                max_model_len=12288,
                max_num_seqs=12,
                seed=config["seed"],
            )
            for start in range(0, len(pending), 16):
                batch = pending[start : start + 16]
                prompts = [prompt_content(r["problem"], config) for r in batch]
                ids = [
                    tokenizer.apply_chat_template(
                        (
                            [
                                {
                                    "role": "system",
                                    "content": "You are an expert in mathematics and Lean 4.",
                                }
                            ]
                            if config.get("prompt_style") == "kimina"
                            else []
                        )
                        + [{"role": "user", "content": p}],
                        tokenize=True,
                        add_generation_prompt=True,
                    )
                    for p in prompts
                ]
                if any(len(x) + config["max_new_tokens"] > 12288 for x in ids):
                    raise ValueError("prompt exceeds fixed context limit; no truncation allowed")
                params = [
                    SamplingParams(
                        n=1,
                        temperature=r["temperature"],
                        top_p=config["top_p"],
                        top_k=config["top_k"],
                        max_tokens=config["max_new_tokens"],
                        seed=r["seed"],
                        logprobs=1,
                        skip_special_tokens=False,
                    )
                    for r in batch
                ]
                t0 = time.monotonic()
                outputs = llm.generate([{"prompt_token_ids": x} for x in ids], params)
                elapsed = time.monotonic() - t0
                for req, prompt, original_ids, generated in zip(
                    batch, prompts, ids, outputs, strict=True
                ):
                    if (
                        generated.prompt_token_ids is None
                        or list(generated.prompt_token_ids) != original_ids
                        or len(generated.outputs) != 1
                    ):
                        raise ValueError("backend changed prompt IDs or attempt count")
                    output = generated.outputs[0]
                    completion_ids = list(output.token_ids)
                    completion = tokenizer.decode(
                        completion_ids,
                        skip_special_tokens=False,
                        clean_up_tokenization_spaces=False,
                    )
                    row = {k: v for k, v in req.items() if k != "problem"}
                    row.update(
                        {
                            "model_id": config["model_id"],
                            "model_revision": config["revision"],
                            "tokenizer_revision": config["tokenizer_revision"],
                            "prompt_content": prompt,
                            "prompt": tokenizer.decode(
                                original_ids,
                                skip_special_tokens=False,
                                clean_up_tokenization_spaces=False,
                            ),
                            "prompt_token_ids": original_ids,
                            "completion_token_ids": completion_ids,
                            "completion": completion,
                            "backend_completion": output.text,
                            "finish_reason": output.finish_reason,
                            "stop_reason": output.stop_reason,
                            "sampling": {
                                "seed": req["seed"],
                                "top_p": config["top_p"],
                                "top_k": config["top_k"],
                                "max_new_tokens": config["max_new_tokens"],
                            },
                            "theorem_statement": req["problem"]["statement"],
                            "trusted_context": trusted_prefix(
                                req["problem"], config["lean"]["max_heartbeats"]
                            ),
                            "task_family": req["problem"]["task_family"],
                            "batch_elapsed_s": elapsed,
                            "batch_size": len(batch),
                            "slurm_job_id": os.getenv("SLURM_JOB_ID"),
                            "generation_token_logprobs": [
                                float(values[token].logprob)
                                for token, values in zip(
                                    completion_ids, output.logprobs or [], strict=True
                                )
                            ],
                        }
                    )
                    journal.append(row, identity(req))
                print(
                    f"completed {len(journal.rows)}/{len(requests)} generation attempts, batch {elapsed:.1f}s",
                    flush=True,
                )
        if set(journal.rows) != {r["trace_id"] for r in requests}:
            raise ValueError("unexpected or missing generation IDs")
    if not (directory / "manifest.json").exists():
        finish(
            directory,
            stage="generation",
            context=context,
            inputs=[
                config_path,
                source_manifest,
                gate,
                model_digests,
                root / "checks/container-digest.json",
                root / "inputs/problems.json",
                root / "inputs/splits.json",
                *([root / "main/collection-gate/manifest.json"] if phase == "main" else []),
            ],
            outputs=[directory / "samples.jsonl", directory / "samples.identity.json"],
            metrics={"attempts": len(requests)},
        )
