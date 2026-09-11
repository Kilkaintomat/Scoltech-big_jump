"""Durable P4 training and a second measurement pass using final-model frequencies."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, cast

import numpy as np

from ..config import GrokkingConfig
from ..e1.analysis import finite_json
from ..e1.artifacts import digest, finish, identity, read_json, verify_manifest, write_once
from ..experiments.p4_grokking import Checkpoint, _tail_fast, analyse_p4
from ..reproducibility import seed_everything


def checkpoint_paths(folder: Path) -> list[Path]:
    return sorted(folder.glob("step-*.pt.receipt.json"))


def train(folder: Path, config: dict[str, Any], source: Path) -> None:
    import torch
    from filelock import FileLock

    from ..models.grokking import build_model, make_data

    folder.mkdir(parents=True, exist_ok=True)
    with FileLock(str(folder / "train.lock"), timeout=0):
        context = {"source": digest(source), "config": identity(config)}
        write_once(folder / "identity.json", context)
        if (folder / "manifest.json").exists():
            verify_manifest(folder / "manifest.json")
            return
        cfg = GrokkingConfig(**config["grokking"])
        seed = int(config["seed"])
        seed_everything(seed)
        device = cfg.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        data = make_data(cfg.p, cfg.train_frac, seed, cfg.shuffle_labels)
        model = build_model(cfg.p, cfg.d_model, cfg.n_heads, cfg.d_mlp, seed).to(device)
        opt = torch.optim.AdamW(
            model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay, betas=cfg.betas
        )
        inputs, targets = data.inputs.to(device), data.targets.to(device)
        train_x, train_y = inputs[data.train_idx], targets[data.train_idx]
        previous = checkpoint_paths(folder)
        start = 0
        if previous:
            receipt = read_json(previous[-1])
            path = folder / receipt["file"]
            if receipt["context"] != context or digest(path) != receipt["sha256"]:
                raise ValueError("changed P4 source/config/checkpoint")
            state = torch.load(path, map_location=device, weights_only=False)
            model.load_state_dict(state["model"])
            opt.load_state_dict(state["optimizer"])
            torch.set_rng_state(state["torch_rng"].cpu())
            if device == "cuda":
                torch.cuda.set_rng_state_all([v.cpu() for v in state["cuda_rng"]])
            start = int(state["step"])
            print(f"resume from optimizer/model/RNG checkpoint {start}", flush=True)
        started = time.monotonic()
        for step in range(start, cfg.steps + 1):
            if step % cfg.checkpoint_every == 0 or step == cfg.steps:
                path = folder / f"step-{step:06d}.pt"
                receipt_path = path.with_suffix(".pt.receipt.json")
                if not receipt_path.exists():
                    if path.exists():
                        path.rename(path.with_name(path.name + ".orphan-" + digest(path)[:12]))
                    payload = {
                        "step": step,
                        "model": model.state_dict(),
                        "optimizer": opt.state_dict(),
                        "torch_rng": torch.get_rng_state(),
                        "cuda_rng": torch.cuda.get_rng_state_all() if device == "cuda" else [],
                        "train_indices": data.train_idx,
                        "test_indices": data.test_idx,
                    }
                    temporary = path.with_suffix(".tmp")
                    torch.save(payload, temporary)
                    os.replace(temporary, path)
                    write_once(
                        receipt_path,
                        {
                            "file": path.name,
                            "sha256": digest(path),
                            "context": context,
                            "step": step,
                        },
                    )
                if step % max(1000, cfg.checkpoint_every) == 0:
                    print(
                        f"saved checkpoint {step}/{cfg.steps}; session {time.monotonic() - started:.1f}s",
                        flush=True,
                    )
            if step == cfg.steps:
                break
            model.train()
            opt.zero_grad(set_to_none=True)
            loss = torch.nn.functional.cross_entropy(model(train_x), train_y)
            loss.backward()
            opt.step()
        files = checkpoint_paths(folder)
        outputs = [
            folder / "identity.json",
            *files,
            *[folder / read_json(p)["file"] for p in files],
        ]
        finish(
            folder,
            stage="p4-durable-training",
            context=context,
            inputs=[source],
            outputs=outputs,
            metrics={
                "seed": seed,
                "shuffle_labels": cfg.shuffle_labels,
                "steps": cfg.steps,
                "checkpoints": len(files),
                "device": device,
                "config": config,
            },
        )


def transition(checkpoints: list[Checkpoint], radius: int = 500) -> dict[str, Any]:
    """A fixed, accuracy-anchored comparison; no search for the most favourable tail drop."""
    ordered = sorted(checkpoints, key=lambda c: c.step)
    reference = next(
        (
            c.step
            for i, c in enumerate(ordered[:-4])
            if all(x.test_acc >= 0.90 for x in ordered[i : i + 5])
        ),
        None,
    )
    out: dict[str, Any] = {
        "reference_step": reference,
        "rule": "first of five consecutive accuracy>=0.90 checkpoints",
        "window_radius_steps": radius,
        "decision": "inconclusive",
    }
    if reference is None:
        out["reason"] = "no sustained generalization transition"
        return out
    before = [c for c in ordered if reference - radius <= c.step < reference]
    after = [c for c in ordered if reference < c.step <= reference + radius]
    out["n_before"], out["n_after"] = len(before), len(after)
    for key in ("hill", "moment", "gpd", "restricted_loss", "excluded_loss"):
        a = np.asarray([getattr(c, key) for c in before], dtype=float)
        b = np.asarray([getattr(c, key) for c in after], dtype=float)
        out[key] = {
            "before": float(np.median(a)) if len(a) else None,
            "after": float(np.median(b)) if len(b) else None,
            "after_minus_before": float(np.median(b) - np.median(a))
            if len(a) and len(b) and np.isfinite(a).all() and np.isfinite(b).all()
            else None,
        }
    out["reason"] = "descriptive within-seed windows; paired training-seed controls required"
    return finite_json(out)


def measure(folder: Path, training: Path, config: dict[str, Any], source: Path) -> None:
    import torch
    from filelock import FileLock

    from ..models.grokking import build_model, key_frequencies, make_data, progress_measures

    verify_manifest(training / "manifest.json")
    folder.mkdir(parents=True, exist_ok=True)
    with FileLock(str(folder / "measure.lock"), timeout=0):
        if (folder / "manifest.json").exists():
            verify_manifest(folder / "manifest.json")
            return
        context = {
            "source": digest(source),
            "training": digest(training / "manifest.json"),
            "config": identity(config),
        }
        write_once(folder / "identity.json", context)
        cfg, seed = GrokkingConfig(**config["grokking"]), int(config["seed"])
        data = make_data(cfg.p, cfg.train_frac, seed, cfg.shuffle_labels)
        model = build_model(cfg.p, cfg.d_model, cfg.n_heads, cfg.d_mlp, seed).eval()
        receipts = checkpoint_paths(training)
        final = read_json(receipts[-1])
        state = torch.load(training / final["file"], map_location="cpu", weights_only=False)
        model.load_state_dict(state["model"])
        frequencies = key_frequencies(model, top_k=6)
        write_once(
            folder / "frequencies.json",
            {
                "frequencies": frequencies,
                "from_step": final["step"],
                "checkpoint_sha256": final["sha256"],
            },
        )
        checkpoints, outputs = [], [folder / "identity.json", folder / "frequencies.json"]
        for item in receipts:
            receipt = read_json(item)
            step = int(receipt["step"])
            result_path = folder / f"step-{step:06d}.json"
            if result_path.exists():
                result = read_json(result_path)
                if (
                    result["checkpoint_sha256"] != receipt["sha256"]
                    or digest(folder / f"norms-{step:06d}.npz") != result["norms_sha256"]
                ):
                    raise ValueError("changed P4 checkpoint/norm artifact")
            else:
                state = torch.load(
                    training / receipt["file"], map_location="cpu", weights_only=False
                )
                model.load_state_dict(state["model"])
                model.eval()
                with torch.no_grad():
                    inc = cast(Any, model).block_increment(data.inputs).float().numpy()
                z = np.linalg.norm(inc, axis=1)
                median = float(np.median(z))
                zn = z / median if median > 0 else z
                pm = progress_measures(model, data, frequencies=frequencies)
                h, m, g, k = _tail_fast(zn)
                result = {
                    "step": step,
                    "train_loss": pm.train_loss,
                    "test_loss": pm.test_loss,
                    "train_acc": pm.train_acc,
                    "test_acc": pm.test_acc,
                    "restricted_loss": pm.restricted_loss,
                    "excluded_loss": pm.excluded_loss,
                    "hill": h,
                    "moment": m,
                    "gpd": g,
                    "k": k,
                    "n": len(z),
                    "median_deviation": median,
                    "key_frequencies": frequencies,
                    "checkpoint_sha256": receipt["sha256"],
                }
                # Norms retain the input identity for later full estimator/calibration work.
                norms = folder / f"norms-{step:06d}.npz"
                np.savez_compressed(
                    norms, z=zn, train_idx=data.train_idx.numpy(), test_idx=data.test_idx.numpy()
                )
                result["norms_sha256"] = digest(norms)
                write_once(result_path, finite_json(result))
            values = {
                k: v for k, v in result.items() if k not in {"checkpoint_sha256", "norms_sha256"}
            }
            for field in ("hill", "moment", "gpd"):
                if values[field] is None:
                    values[field] = float("nan")
            checkpoints.append(Checkpoint(**values))
            outputs.extend([result_path, folder / f"norms-{step:06d}.npz"])
        metrics = {
            "seed": seed,
            "shuffle_labels": cfg.shuffle_labels,
            "fixed_final_frequencies": frequencies,
            "primary_transition": transition(checkpoints),
            "legacy_exploratory": analyse_p4(checkpoints),
            "scientific_decision": "inconclusive",
            "bootstrap_unit": "training_seed for cross-run effects",
            "full_k_bootstrap_status": "queued fixed-grid full-tail stage; fixed-fraction curves remain diagnostic",
        }
        path = write_once(folder / "metrics.json", finite_json(metrics))
        finish(
            folder,
            stage="p4-fixed-frequency-measurement",
            context=context,
            inputs=[source, training / "manifest.json"],
            outputs=[*outputs, path],
            metrics=finite_json(metrics),
        )


def full_tail(folder: Path, measurement: Path, source: Path) -> None:
    """Fixed checkpoint grid; input bootstrap is conditional on one trained model and selected k."""
    from ..config import TailEstimationConfig
    from ..stats import estimate_tail

    verify_manifest(measurement / "manifest.json")
    outputs = []
    for step in (0, 10000, 20000, 30000, 40000):
        path = folder / f"step-{step:06d}.json"
        if not path.exists():
            with np.load(measurement / f"norms-{step:06d}.npz", allow_pickle=False) as bundle:
                z = bundle["z"]
            estimate = estimate_tail(
                z,
                np.arange(len(z)),
                cfg=TailEstimationConfig(bootstrap_unit="prompt"),
                seed=20260911 + step,
            )
            write_once(
                path,
                finite_json(
                    {
                        "step": step,
                        "estimate": estimate.as_dict(),
                        "interpretation": "conditional input-resampling intervals, k fixed within resample; training-seed variation reported separately",
                        "decision": "inconclusive",
                    }
                ),
            )
        outputs.append(path)
    finish(
        folder,
        stage="p4-fixed-grid-full-tail",
        context={"source": digest(source)},
        inputs=[source, measurement / "manifest.json"],
        outputs=outputs,
        metrics={"checkpoints": len(outputs)},
    )


def summarize(folder: Path, root: Path, source: Path) -> None:
    """Compare matched seeds at the REAL run's predetermined accuracy transition."""
    pairs = []
    manifests = []
    for seed in range(5):
        paths = {arm: root / f"{arm}-{seed}" / "measurement" for arm in ("real", "null")}
        for path in paths.values():
            verify_manifest(path / "manifest.json")
            manifests.append(path / "manifest.json")
        reference = read_json(paths["real"] / "metrics.json")["primary_transition"][
            "reference_step"
        ]
        pair: dict[str, Any] = {"seed": seed, "real_reference_step": reference}
        if reference is not None:
            for arm, path in paths.items():
                checkpoints = [read_json(p) for p in sorted(path.glob("step-*.json"))]
                changes = {}
                for key in (
                    "hill",
                    "moment",
                    "gpd",
                    "restricted_loss",
                    "excluded_loss",
                    "test_acc",
                ):
                    before = [
                        c[key] for c in checkpoints if reference - 500 <= c["step"] < reference
                    ]
                    after = [
                        c[key] for c in checkpoints if reference < c["step"] <= reference + 500
                    ]
                    complete = len(before) == len(after) == 5 and all(
                        v is not None and np.isfinite(v) for v in before + after
                    )
                    changes[key] = float(np.median(after) - np.median(before)) if complete else None
                pair[arm] = changes
            pair["paired_difference"] = {
                k: pair["real"][k] - pair["null"][k]
                if pair["real"][k] is not None and pair["null"][k] is not None
                else None
                for k in pair["real"]
            }
        pairs.append(pair)
    metrics = {
        "pairs": pairs,
        "unit": "paired training seed",
        "decision": "inconclusive",
        "limitations": [
            "five seed pairs are a replication screen, not a high-power confirmatory experiment",
            "no transition is retained as a no-transition outcome",
            "bounded finite input domain does not identify an asymptotic heavy-tail class",
        ],
    }
    path = write_once(folder / "metrics.json", finite_json(metrics))
    finish(
        folder,
        stage="p4-paired-seed-summary",
        context={"source": digest(source)},
        inputs=[source, *manifests],
        outputs=[path],
        metrics={"pairs": 5, "decision": "inconclusive"},
    )
