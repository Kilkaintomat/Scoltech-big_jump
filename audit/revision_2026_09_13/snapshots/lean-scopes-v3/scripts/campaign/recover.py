"""Create a fresh campaign graph, preserving immutable pilots and reusing generated tokens.

Host Python 3.6: file and Slurm job management only. No experiment runs on the login node.
"""

import argparse
import copy
import datetime
import json
import shutil
from pathlib import Path


def prepare(original, target, storage, source, validation_job):
    old = json.loads((original / "queue.json").read_text(encoding="utf-8"))
    if any(
        t.get("job_id") and t["state"] in {"RUNNING", "PENDING", "COMPLETING"}
        for t in old["tasks"].values()
    ):
        raise ValueError("source campaign has active jobs; reconcile accounting before recovery")
    for key, task in old["tasks"].items():
        if (
            key != "prepare"
            and "/pilot-" not in key
            and task.get("job_id")
            and task.get("stage") != "gate"
        ):
            raise ValueError("recovery expects the original main collection never to have started")
    target.mkdir(parents=True, exist_ok=False)
    storage.mkdir(parents=True, exist_ok=False)
    (target / "logs").mkdir()
    (target / "controller").mkdir()
    tasks = {
        "validation": {
            "model": None,
            "job_id": validation_job,
            "dependencies": [],
            "partition": "ais-htc",
            "state": "PENDING",
            "external": True,
        }
    }
    for name in ("deepseek", "goedel", "kimina"):
        previous = original / name
        root = target / name
        root.mkdir()
        (root / "inputs").symlink_to(previous / "inputs", target_is_directory=True)
        (root / "checks").mkdir()
        for filename in ("model-digests.json", "container-digest.json"):
            (root / "checks" / filename).symlink_to(previous / "checks" / filename)
        for phase in ("pilot", "main"):
            (root / phase).mkdir()
            shutil.copy2(
                str(previous / phase / "protocol.json"), str(root / phase / "protocol.json")
            )
            for stage in (
                "generation",
                "verification",
                "extraction",
                "measurement",
                "analysis",
                "collection-gate",
            ):
                if phase == "pilot" and stage == "generation":
                    dest = previous / phase / stage
                else:
                    dest = storage / name / phase / stage
                    dest.mkdir(parents=True)
                (root / phase / stage).symlink_to(dest, target_is_directory=True)
        dependency = "validation"
        for stage in ("smoke", "verify", "extract", "measure", "analyze"):
            key = name + "/pilot-" + stage
            tasks[key] = {
                "model": name,
                "stage": stage,
                "dependencies": [dependency],
                "partition": "ais-gpu" if stage == "extract" else "ais-htc",
                "hours": 2,
                "script": str(source / "scripts/campaign/run.sbatch"),
                "arguments": [stage, str(root), "--phase", "pilot"],
                "job_name": "obj0911-" + key.replace("/", "-"),
                "job_id": None,
                "state": "WAITING",
            }
            dependency = key
    for key, task in old["tasks"].items():
        if key == "prepare" or "/pilot-" in key:
            continue
        task = copy.deepcopy(task)
        task.update(
            job_id=None,
            state="WAITING",
            script=str(source / "scripts/campaign/run.sbatch"),
            job_name="obj0911-" + key.replace("/", "-"),
        )
        task.pop("submit_error", None)
        task["dependencies"] = [d for d in task["dependencies"] if d != "prepare"]
        task["arguments"][1] = str(target / task["model"])
        tasks[key] = task
    queue = {
        "source": str(source),
        "tasks": tasks,
        "partition_submit_caps": old["partition_submit_caps"],
        "gpu_submitted_per_model": old["gpu_submitted_per_model"],
        "version": 2,
        "recovery_of": str(original),
        "created_utc": datetime.datetime.utcnow().isoformat() + "Z",
    }
    (target / "queue.json").write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    (target / "recovery.json").write_text(
        json.dumps(
            {
                "original": str(original),
                "source": str(source),
                "storage": str(storage),
                "generation_reused_without_resampling": True,
                "protocol_bytes_unchanged": True,
                "validation_job": validation_job,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("storage", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("validation_job")
    args = parser.parse_args()
    print(
        prepare(
            args.original.resolve(),
            args.target.resolve(),
            args.storage.resolve(),
            args.source.resolve(),
            args.validation_job,
        )
    )


if __name__ == "__main__":
    main()
