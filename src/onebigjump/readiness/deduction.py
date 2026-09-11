"""Controlled modus-ponens pilot/main for P1-P3 and assigned-length P5.

This is a new controlled synthetic task, not a reproduction of all PrOntoQA settings.
Every attempt is retained. A format gate precedes main; no semantic success rate gates sampling.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..e1.analysis import finite_json, localization, overshoot, tail
from ..e1.artifacts import Journal, digest, finish, identity, read_json, verify_manifest, write_once
from ..e1.main_analysis import bootstrap_cell, subsets
from ..e1.measurement import fit_transform, transformed_norms
from ..e1.spans import SourceExclusion, align
from ..e1.stages import rows
from .controls import positional_null


def make_problem(length: int, role: str, index: int, seed: int = 20260911) -> dict[str, Any]:
    if not 3 <= length <= 12:
        raise ValueError("assigned lengths must be 3..12")
    rid = f"{role}:L{length}:{index:04d}"
    rng = np.random.default_rng(int(identity([seed, rid])[:16], 16))
    names = [f"p{int(x):04d}" for x in rng.choice(10000, size=2 * length + 3, replace=False)]
    chain = names[: length + 1]
    edges = list(pairwise(chain))
    # Irrelevant branch from the same initial fact; it cannot shorten the target path.
    distractor = [(chain[0], names[length + 1]), *list(pairwise(names[length + 1 :]))]
    edges.extend(distractor)
    rng.shuffle(edges)
    return {
        "problem_id": rid,
        "role": role,
        "length": length,
        "entity": "Mira",
        "initial": chain[0],
        "goal": chain[-1],
        "rules": [list(e) for e in edges],
        "gold_chain": chain[1:],
        "task_family": "modus_ponens",
    }


def prompt(problem: dict[str, Any]) -> str:
    rules = "\n".join(f"All {a} things are {b}." for a, b in problem["rules"])
    return (
        f"Fact: Mira is {problem['initial']}.\nRules:\n{rules}\n"
        f"Prove that Mira is {problem['goal']} using exactly {problem['length']} single-rule inferences.\n"
        "Write only one new fact per line, exactly in the form 'Mira is p1234.'. "
        "Each line must follow by ONE supplied rule from a fact already established. "
        "Do not repeat the initial fact or the rules. Do not skip intermediate inferences. "
        "After the proof, write 'Answer: true'."
    )


def check(completion: str, problem: dict[str, Any]) -> dict[str, Any]:
    # Token positions are original completion offsets. Answer lines are explicitly excluded.
    clean = re.sub(r"<\|[^<>]+\|>|</s>", lambda m: " " * len(m.group()), completion)
    spans = []
    unknown = []
    for match in re.finditer(r"[^\n]+", clean):
        line = match.group().strip()
        if not line:
            continue
        if re.fullmatch(r"(?:Final\s+)?Answer:\s*true\.?", line, re.I):
            continue
        fact_match = re.fullmatch(
            r"(?:\d+[.)]\s*)?(?:(?:Therefore|Thus),?\s*)?Mira is (p\d{4})\.", line, re.I
        )
        if fact_match is None:
            unknown.append(line)
            continue
        left = match.start() + len(match.group()) - len(match.group().lstrip())
        right = match.end() - len(match.group()) + len(match.group().rstrip())
        spans.append({"start": left, "end": right, "fact": fact_match.group(1).lower()})
    if unknown or len(spans) != problem["length"]:
        return {
            "category": "format_error",
            "format_eligible": False,
            "observed_steps": len(spans),
            "unknown_lines": unknown,
            "steps": [],
            "step_spans": [],
            "t_star": None,
            "verified": False,
        }
    known = {problem["initial"]}
    edges = {tuple(e) for e in problem["rules"]}
    steps = []
    failure = None
    for t, span in enumerate(spans):
        fact = span["fact"]
        valid = any((premise, fact) in edges for premise in known)
        if failure is None and not valid:
            failure = t
        reached = failure is None or failure == t
        steps.append(
            {
                "t": t,
                "valid": int(failure is None),
                "status": "ok" if failure is None else "error" if reached else "unreached",
                "fact": fact,
                "reason": None if valid else "no single supplied rule from established facts",
            }
        )
        if failure is None:
            known.add(fact)
    if failure is None and problem["goal"] not in known:
        failure = len(steps) - 1
        steps[-1].update(valid=0, status="error", reason="target fact was not derived")
    return {
        "category": "verified" if failure is None else "invalid_inference",
        "format_eligible": True,
        "observed_steps": len(spans),
        "steps": steps,
        "step_spans": spans,
        "t_star": failure,
        "verified": failure is None,
    }


def population(root: Path, source: Path) -> None:
    config = read_json(root / "protocol.json")
    problems: list[dict[str, Any]] = []
    for length in range(3, 13):
        for role, count in (
            ("pilot_calibration", 2),
            ("pilot_evaluation", 2),
            ("calibration", config["calibration_per_length"]),
            ("evaluation", config["evaluation_per_length"]),
        ):
            problems.extend(make_problem(length, role, i, config["seed"]) for i in range(count))
    path = write_once(root / "inputs/problems.json", problems)
    finish(
        root / "inputs",
        stage="controlled-deduction-population",
        context={"config": digest(root / "protocol.json")},
        inputs=[source, root / "protocol.json"],
        outputs=[path],
        metrics={"tasks": len(problems), "lengths": list(range(3, 13))},
    )


def requests(root: Path, phase: str, shard: int = 0, n_shards: int = 1) -> list[dict[str, Any]]:
    config = read_json(root / "protocol.json")
    roles = (
        {"pilot_calibration", "pilot_evaluation"}
        if phase == "pilot"
        else {"calibration", "evaluation"}
    )
    result = []
    for p in read_json(root / "inputs/problems.json"):
        if p["role"] not in roles or int(identity(p["problem_id"])[:8], 16) % n_shards != shard:
            continue
        for temperature in config["temperatures"]:
            for attempt in range(1 if phase == "pilot" else config["attempts_per_temperature"]):
                rid = f"{p['problem_id']}:T{temperature}:a{attempt}"
                result.append(
                    {
                        "trace_id": rid,
                        "problem": p,
                        "temperature": temperature,
                        "seed": int(identity([config["seed"], rid])[:8], 16) % (2**31),
                    }
                )
    return result


def model_info(root: Path) -> dict[str, Any]:
    model_root = Path(read_json(root / "protocol.json")["model_root"])
    verify_manifest(model_root / "manifest.json")
    info = read_json(model_root / "model.json")
    if any(digest(p) != sha for p, sha in info["files"].items()):
        raise ValueError("changed model files")
    return info


def generate(root: Path, phase: str, source: Path, shard: int, n_shards: int) -> None:
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    config = read_json(root / "protocol.json")
    verify_manifest(root / "inputs/manifest.json")
    if phase == "main":
        verify_manifest(root / "pilot/gate/manifest.json")
    info = model_info(root)
    folder = root / phase / "generation" / f"shard-{shard:03d}-of-{n_shards:03d}"
    if (folder / "manifest.json").exists():
        verify_manifest(folder / "manifest.json")
        return
    planned = requests(root, phase, shard, n_shards)
    context = {
        "source": digest(source),
        "protocol": digest(root / "protocol.json"),
        "model_revision": info["revision"],
        "requests": identity(planned),
    }
    path = folder / "samples.jsonl"
    with Journal(path, context) as journal:
        pending = [r for r in planned if journal.existing(r["trace_id"], identity(r)) is None]
        if pending:
            tokenizer = AutoTokenizer.from_pretrained(info["model_path"], local_files_only=True)
            model = LLM(
                model=info["model_path"],
                dtype="bfloat16",
                enforce_eager=True,
                trust_remote_code=False,
                gpu_memory_utilization=0.80,
                max_model_len=4096,
                max_num_seqs=16,
                seed=config["seed"],
            )
            for start in range(0, len(pending), 16):
                batch = pending[start : start + 16]
                ids = [
                    tokenizer.apply_chat_template(
                        [{"role": "user", "content": prompt(r["problem"])}],
                        tokenize=True,
                        add_generation_prompt=True,
                    )
                    for r in batch
                ]
                if any(len(x) + config["max_new_tokens"] > 4096 for x in ids):
                    raise ValueError("context budget exceeded")
                params = [
                    SamplingParams(
                        n=1,
                        temperature=r["temperature"],
                        top_p=1,
                        top_k=-1,
                        max_tokens=config["max_new_tokens"],
                        seed=r["seed"],
                        skip_special_tokens=False,
                        logprobs=1,
                    )
                    for r in batch
                ]
                generated = model.generate([{"prompt_token_ids": x} for x in ids], params)
                for r, original, out in zip(batch, ids, generated, strict=True):
                    if (
                        out.prompt_token_ids is None
                        or list(out.prompt_token_ids) != original
                        or len(out.outputs) != 1
                    ):
                        raise ValueError("backend attempt mismatch")
                    sample = out.outputs[0]
                    if sample.logprobs is None:
                        raise ValueError("backend omitted token log probabilities")
                    tokens = list(sample.token_ids)
                    journal.append(
                        {
                            **r,
                            "prompt_token_ids": original,
                            "completion_token_ids": tokens,
                            "completion": tokenizer.decode(
                                tokens,
                                skip_special_tokens=False,
                                clean_up_tokenization_spaces=False,
                            ),
                            "finish_reason": sample.finish_reason,
                            "generation_token_logprobs": [
                                float(lp[t].logprob)
                                for t, lp in zip(tokens, sample.logprobs, strict=True)
                            ],
                        },
                        identity(r),
                    )
                print(f"saved {len(journal.rows)}/{len(planned)} attempts", flush=True)
    inputs = [
        source,
        root / "protocol.json",
        root / "inputs/manifest.json",
        Path(config["model_root"]) / "manifest.json",
    ]
    if phase == "main":
        inputs.append(root / "pilot/gate/manifest.json")
    finish(
        folder,
        stage="controlled-deduction-generation",
        context=context,
        inputs=inputs,
        outputs=[path, path.with_suffix(".identity.json")],
        metrics={"attempts": len(planned), "shard": shard, "n_shards": n_shards},
    )


def samples(root: Path, phase: str) -> tuple[list[dict[str, Any]], list[Path]]:
    manifests = sorted((root / phase / "generation").glob("shard-*/manifest.json"))
    found = []
    for manifest in manifests:
        verify_manifest(manifest)
        found.extend(rows(manifest.parent / "samples.jsonl"))
    ids = [r["trace_id"] for r in found]
    if len(ids) != len(set(ids)) or set(ids) != {r["trace_id"] for r in requests(root, phase)}:
        raise ValueError("incomplete generation population")
    return found, manifests


def verify(root: Path, phase: str, source: Path) -> None:
    found, manifests = samples(root, phase)
    folder = root / phase / "verification"
    path = folder / "labels.jsonl"
    context = {"source": digest(source), "generation": {str(p): digest(p) for p in manifests}}
    with Journal(path, context) as journal:
        for sample in found:
            if journal.existing(sample["trace_id"], identity(sample)) is not None:
                continue
            result = check(sample["completion"], sample["problem"])
            if sample["finish_reason"] == "length":
                result.update(
                    category="generation_truncation",
                    verified=False,
                    format_eligible=False,
                    steps=[],
                    step_spans=[],
                    t_star=None,
                )
            journal.append({"trace_id": sample["trace_id"], **result}, identity(sample))
        categories = dict(Counter(r["category"] for r in journal.rows.values()))
    finish(
        folder,
        stage="symbolic-single-rule-verification",
        context=context,
        inputs=[source, *manifests],
        outputs=[path, path.with_suffix(".identity.json")],
        metrics={"attempts": len(found), "categories": categories},
    )


def extract(root: Path, phase: str, source: Path) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from ..models.hooks import record_residuals

    info = model_info(root)
    config = read_json(root / "protocol.json")
    found, _ = samples(root, phase)
    labels_path = root / phase / "verification/manifest.json"
    verify_manifest(labels_path)
    labels = {r["trace_id"]: r for r in rows(labels_path.parent / "labels.jsonl")}
    folder = root / phase / "extraction"
    model = (
        AutoModelForCausalLM.from_pretrained(
            info["model_path"],
            torch_dtype=torch.bfloat16,
            local_files_only=True,
            attn_implementation="sdpa",
        )
        .to("cuda")
        .eval()
    )
    tokenizer = AutoTokenizer.from_pretrained(info["model_path"], local_files_only=True)
    layers = [int(model.config.num_hidden_layers * f) - 1 for f in (0.25, 0.5, 0.75)]
    context = {
        "source": digest(source),
        "verification": digest(labels_path),
        "model_revision": info["revision"],
    }
    path = folder / "trajectories.jsonl"
    with Journal(path, context) as journal:
        checked = any(r.get("forward_check") for r in journal.rows.values())
        for sample in found:
            label = labels[sample["trace_id"]]
            request = identity([sample, label])
            if journal.existing(sample["trace_id"], request) is not None:
                continue
            p = sample["problem"]
            row = {
                "trace_id": sample["trace_id"],
                "problem_id": p["problem_id"],
                "role": p["role"].replace("pilot_", ""),
                "temperature": sample["temperature"],
                "category": label["category"],
                "length": p["length"],
                "extraction_status": "excluded_by_verification",
                "task_family": p["task_family"],
            }
            if label["format_eligible"]:
                try:
                    alignment = align(
                        tokenizer,
                        sample["prompt_token_ids"],
                        sample["completion_token_ids"],
                        sample["completion"],
                        label["step_spans"],
                    )
                    ids = sample["prompt_token_ids"] + sample["completion_token_ids"]
                    tensor = torch.tensor([ids], device="cuda")
                    with (
                        torch.inference_mode(),
                        record_residuals(model, layers, alignment["positions"]) as capture,
                    ):
                        output = model(input_ids=tensor, use_cache=False)
                    lp = []
                    for lo in range(0, len(ids) - 1, 128):
                        hi = min(lo + 128, len(ids) - 1)
                        logits = output.logits[0, lo:hi].float()
                        target = tensor[0, lo + 1 : hi + 1]
                        lp.extend(
                            (logits.gather(1, target[:, None]).squeeze(1) - logits.logsumexp(-1))
                            .cpu()
                            .tolist()
                        )
                    del output
                    arrays = {
                        f"states_{layer}": capture.captures[layer].numpy() for layer in layers
                    }
                    arrays["surprisal"] = np.array(
                        [
                            -np.mean(lp[lo - 1 : hi])
                            for lo, hi in alignment["step_token_spans_inclusive"]
                        ]
                    )
                    if not all(np.isfinite(v).all() for v in arrays.values()):
                        raise ValueError("nonfinite activations")
                    if not checked:
                        with torch.inference_mode():
                            independent = model(
                                input_ids=tensor, use_cache=False, output_hidden_states=True
                            )
                        errors = {
                            str(layer): float(
                                (
                                    independent.hidden_states[layer + 1][0, alignment["positions"]]
                                    .float()
                                    .cpu()
                                    - capture.captures[layer]
                                )
                                .abs()
                                .max()
                            )
                            for layer in layers
                        }
                        if any(v > 1e-5 for v in errors.values()):
                            raise ValueError("independent hook check failed")
                        row["forward_check"] = {"passed": True, "max_abs_error": errors}
                        checked = True
                        del independent
                    artifact = folder / "states" / (identity(sample["trace_id"]) + ".npz")
                    artifact.parent.mkdir(parents=True, exist_ok=True)
                    temporary = artifact.with_suffix(".tmp")
                    with temporary.open("wb") as stream:
                        np.savez_compressed(stream, **arrays)
                    os.replace(temporary, artifact)
                    generation = np.array(sample["generation_token_logprobs"])
                    hf = np.array(lp[len(sample["prompt_token_ids"]) - 1 :])
                    row.update(
                        states_path=str(artifact),
                        states_sha256=digest(artifact),
                        extraction_status="extracted",
                        alignment=alignment,
                        backend_logprob_mean_abs_error=float(np.mean(np.abs(generation - hf))),
                    )
                except SourceExclusion as exc:
                    row.update(extraction_status=exc.category, error=str(exc))
            journal.append(row, request)
            print(f"captured {len(journal.rows)}/{len(found)}", flush=True)
        outputs = [
            path,
            path.with_suffix(".identity.json"),
            *[
                Path(r["states_path"])
                for r in journal.rows.values()
                if r["extraction_status"] == "extracted"
            ],
        ]
        n = sum(r["extraction_status"] == "extracted" for r in journal.rows.values())
    finish(
        folder,
        stage="deduction-activations",
        context=context,
        inputs=[source, labels_path, Path(config["model_root"]) / "manifest.json"],
        outputs=outputs,
        metrics={"attempts": len(found), "extracted": n, "layers": layers},
    )


def measure(root: Path, phase: str, source: Path) -> None:
    config = read_json(root / "protocol.json")
    upstream = root / phase / "extraction/manifest.json"
    verify_manifest(upstream)
    labels = {r["trace_id"]: r for r in rows(root / phase / "verification/labels.jsonl")}
    records = [
        r
        for r in rows(upstream.parent / "trajectories.jsonl")
        if r["extraction_status"] == "extracted"
    ]
    layers = read_json(upstream)["metrics"]["layers"]
    loaded = {}
    for r in records:
        if digest(r["states_path"]) != r["states_sha256"]:
            raise ValueError("state digest mismatch")
        with np.load(r["states_path"], allow_pickle=False) as bundle:
            loaded[r["trace_id"]] = {k: bundle[k] for k in bundle.files}
    entries = []
    diagnostics = []
    transform_files = []
    folder = root / phase / "measurement"
    folder.mkdir(parents=True, exist_ok=True)
    for temperature in config["temperatures"]:
        selected = [r for r in records if r["temperature"] == temperature]
        cal = [r for r in selected if r["role"] == "calibration" and r["category"] == "verified"]
        for layer in layers:
            states = [loaded[r["trace_id"]][f"states_{layer}"] for r in cal]
            n = sum(len(s) - 1 for s in states)
            n_tasks = len({r["problem_id"] for r in cal})
            fit = (
                fit_transform(states, 0.1, 1.0)
                if n_tasks >= (2 if phase == "pilot" else 20)
                and n >= (8 if phase == "pilot" else 200)
                else None
            )
            if fit is not None:
                artifact = folder / f"transform-T{temperature}-L{layer}.npz"
                with artifact.with_suffix(".tmp").open("wb") as stream:
                    np.savez_compressed(stream, allow_pickle=False, **fit)
                os.replace(artifact.with_suffix(".tmp"), artifact)
                transform_files.append(artifact)
            diagnostics.append(
                {
                    "temperature": temperature,
                    "layer": layer,
                    "calibration_tasks": n_tasks,
                    "increments": n,
                    "available": fit is not None,
                }
            )
            for r in selected:
                label = labels[r["trace_id"]]
                values = transformed_norms(loaded[r["trace_id"]][f"states_{layer}"], fit)
                for statistic, z in values.items():
                    for t, value in enumerate(z):
                        entries.append(
                            {
                                "trace_id": r["trace_id"],
                                "prompt_id": r["problem_id"],
                                "role": r["role"],
                                "task_family": "modus_ponens",
                                "temperature": temperature,
                                "layer": layer,
                                "statistic": statistic,
                                "z": float(value),
                                "t": t,
                                "L": r["length"],
                                "t_star": label["t_star"],
                                "valid": label["steps"][t]["valid"],
                                "outcome": "verified" if label["verified"] else "refuted",
                                "surprisal": float(loaded[r["trace_id"]]["surprisal"][t]),
                            }
                        )
    folder = root / phase / "measurement"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "deviations.parquet"
    pd.DataFrame(entries).to_parquet(path, index=False)
    info = write_once(folder / "calibration.json", diagnostics)
    finish(
        folder,
        stage="deduction-measurement",
        context={"source": digest(source)},
        inputs=[source, upstream],
        outputs=[path, info, *transform_files],
        metrics={"rows": len(entries), "traces": len(records), "layers": layers},
    )


def analyze(root: Path, phase: str, source: Path) -> None:
    from ..experiments.p5_length_law import fit_length_law

    config = read_json(root / "protocol.json")
    manifest = root / phase / "measurement/manifest.json"
    verify_manifest(manifest)
    table = pd.read_parquet(manifest.parent / "deviations.parquet")
    found, _ = samples(root, phase)
    labels = {r["trace_id"]: r for r in rows(root / phase / "verification/labels.jsonl")}
    layer = read_json(manifest)["metrics"]["layers"][1]
    cells = []
    analysis_folder = root / phase / "analysis"
    for temperature in config["temperatures"]:
        for statistic in ("raw", "whitened", "innovation"):
            frame = (
                table[
                    (table["temperature"] == temperature)
                    & (table["layer"] == layer)
                    & (table["statistic"] == statistic)
                ]
                if not table.empty
                else pd.DataFrame()
            )
            if frame.empty:
                cells.append(
                    {"temperature": temperature, "statistic": statistic, "available": False}
                )
                continue
            cell_path = analysis_folder / f"cell-T{temperature}-{statistic}.json"
            if cell_path.exists():
                cells.append(read_json(cell_path))
                continue
            cal = frame[frame["role"] == "calibration"]
            evaluation = frame[frame["role"] == "evaluation"]
            stats_config = {"seed": config["seed"], "statistics": config["statistics"]}
            cell: dict[str, Any] = {
                "temperature": temperature,
                "statistic": statistic,
                "available": True,
                "P1": {k: tail(v, stats_config) for k, v in subsets(evaluation).items()},
                "P2": localization(evaluation, stats_config),
                "positional_null": positional_null(evaluation),
                "P3": overshoot(cal, evaluation, 0.01),
            }
            if phase == "main":
                cell["task_bootstrap"] = bootstrap_cell(cal, evaluation, stats_config)
            write_once(cell_path, finite_json(cell))
            cells.append(cell)
    p5 = []
    for temperature in config["temperatures"]:
        selected = [
            r
            for r in found
            if r["temperature"] == temperature and r["problem"]["role"].endswith("evaluation")
        ]
        counts = {
            length: (
                sum(
                    labels[r["trace_id"]]["verified"]
                    for r in selected
                    if r["problem"]["length"] == length
                ),
                sum(r["problem"]["length"] == length for r in selected),
            )
            for length in range(3, 13)
        }
        format_fraction = (
            np.mean([labels[r["trace_id"]]["format_eligible"] for r in selected])
            if selected
            else 0.0
        )
        result: dict[str, Any] = {
            "temperature": temperature,
            "assigned_length_counts": counts,
            "format_fraction": float(format_fraction),
            "decision": "inconclusive",
            "interpretation": "assigned-length intention-to-treat diagnostic; format failures remain in denominator",
        }
        if not table.empty:
            verified = table[
                (table["temperature"] == temperature)
                & (table["layer"] == layer)
                & (table["statistic"] == "raw")
                & (table["role"] == "calibration")
                & (table["outcome"] == "verified")
            ]
            try:
                result["fit"] = fit_length_law(counts, verified["z"].to_numpy()).as_dict()
            except (ValueError, RuntimeError, FloatingPointError) as exc:
                result["fit_error"] = str(exc)
        p5.append(result)
    metrics = finite_json(
        {
            "phase": phase,
            "categories": dict(Counter(r["category"] for r in labels.values())),
            "cells": cells,
            "P5": p5,
            "decision": "inconclusive",
            "limitations": [
                "single controlled ontology family and first model",
                "no causal theta/tau identification",
                "assigned length differs from actual opportunities for malformed outputs",
                "dependence-calibrated P5 test pending",
            ],
        }
    )
    path = write_once(root / phase / "analysis/metrics.json", metrics)
    finish(
        path.parent,
        stage="deduction-P1-P5-descriptive",
        context={"source": digest(source)},
        inputs=[source, manifest, root / phase / "verification/manifest.json"],
        outputs=[path, *sorted(analysis_folder.glob("cell-*.json"))],
        metrics={"phase": phase, "decision": "inconclusive"},
    )


def gate(root: Path, source: Path) -> None:
    for stage in ("verification", "extraction", "measurement", "analysis"):
        verify_manifest(root / "pilot" / stage / "manifest.json")
    labels = rows(root / "pilot/verification/labels.jsonl")
    records = rows(root / "pilot/extraction/trajectories.jsonl")
    eligible = {r["trace_id"] for r in labels if r["format_eligible"]}
    extracted = {r["trace_id"] for r in records if r["extraction_status"] == "extracted"}
    fraction = len(eligible) / len(labels)
    if (
        fraction < 0.90
        or eligible != extracted
        or not any(r.get("forward_check", {}).get("passed") for r in records)
    ):
        raise ValueError(
            "synthetic technical pilot failed: format coverage/alignment/hooks; main withheld"
        )
    path = write_once(
        root / "pilot/gate/result.json",
        {
            "passed": True,
            "format_fraction": fraction,
            "purpose": "technical data acquisition only; no semantic success threshold",
        },
    )
    finish(
        path.parent,
        stage="deduction-acquisition-gate",
        context={"source": digest(source)},
        inputs=[
            source,
            *[
                root / "pilot" / s / "manifest.json"
                for s in ("verification", "extraction", "measurement", "analysis")
            ],
        ],
        outputs=[path],
        metrics={"passed": True},
    )
