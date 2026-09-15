"""Fresh verification lineage for saved tokens, including still-running generation jobs.

Host Python 3.6 file/job management only. Never generates or overwrites a completion.
"""

import argparse
import copy
import datetime
import json
import shutil
from pathlib import Path

MODELS = ("deepseek", "goedel", "kimina")


def prepare(original, target, storage, source, validation_job, regression_job):
    old = json.loads((original / "queue.json").read_text(encoding="utf-8"))
    if target.exists() or storage.exists():
        raise ValueError("reverification requires new, empty lineage paths")
    for name in MODELS:
        for phase in ("pilot", "main"):
            if not (original / name / phase / "generation").is_dir():
                raise ValueError("missing original generation directory")
            if not (original / name / phase / "protocol.json").is_file():
                raise ValueError("missing frozen protocol")
        for shard in range(8):
            task = old["tasks"][name + "/main-generate-" + str(shard)]
            if not task.get("job_id") or task["state"] not in {
                "COMPLETED",
                "RUNNING",
                "PENDING",
                "COMPLETING",
                "CONFIGURING",
            }:
                raise ValueError("generation must be completed or have a live original job")
    target.mkdir(parents=True)
    storage.mkdir(parents=True)
    (target / "logs").mkdir()
    (target / "controller").mkdir()
    tasks = {}
    for key, job in (("validation", validation_job), ("regression", regression_job)):
        tasks[key] = {
            "model": None,
            "job_id": job,
            "dependencies": [],
            "partition": "ais-htc",
            "state": "PENDING",
            "external": True,
        }
    for name in MODELS:
        previous, root = original / name, target / name
        root.mkdir()
        (root / "inputs").symlink_to((previous / "inputs").resolve(), target_is_directory=True)
        (root / "checks").mkdir()
        for filename in ("model-digests.json", "container-digest.json"):
            (root / "checks" / filename).symlink_to((previous / "checks" / filename).resolve())
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
                if stage == "generation":
                    destination = (previous / phase / stage).resolve()
                else:
                    destination = storage / name / phase / stage
                    destination.mkdir(parents=True)
                (root / phase / stage).symlink_to(destination, target_is_directory=True)
        dependencies = ["validation", "regression"]
        for stage in ("smoke", "verify", "extract", "measure", "analyze"):
            key = name + "/pilot-" + stage
            tasks[key] = {
                "model": name,
                "stage": stage,
                "dependencies": dependencies,
                "partition": "ais-gpu" if stage == "extract" else "ais-htc",
                "hours": 2,
                "script": str(source / "scripts/campaign/run.sbatch"),
                "arguments": [stage, str(root), "--phase", "pilot"],
                "job_name": "obj0912-" + key.replace("/", "-"),
                "job_id": None,
                "state": "WAITING",
            }
            dependencies = [key]
    for key, previous in old["tasks"].items():
        if previous.get("model") not in MODELS or "/pilot-" in key:
            continue
        task = copy.deepcopy(previous)
        if task.get("stage") == "generate":
            # All identity and data validation is performed by generation_inputs on Slurm.
            # This external task cannot be submitted again by dispatch.ready.
            task.update(
                external=True,
                reused_from=str(original),
                original_source=old["source"],
                dependencies=[],
            )
            task.pop("arguments", None)
            task.pop("script", None)
        else:
            task.update(
                job_id=None,
                state="WAITING",
                script=str(source / "scripts/campaign/run.sbatch"),
                job_name="obj0912-" + key.replace("/", "-"),
            )
            task.pop("submit_error", None)
            task["arguments"][1] = str(target / task["model"])
            task["dependencies"] = [
                d
                for d in task["dependencies"]
                if d not in {"prepare", "validation_all", "parser_validation"}
            ]
            if task["stage"] == "verify":
                task["dependencies"].append(task["model"] + "/gate")
            if task["stage"] == "gate":
                task["dependencies"] += ["validation", "regression"]
        tasks[key] = task
    done = set()
    while len(done) < len(tasks):
        available = {k for k, v in tasks.items() if set(v["dependencies"]) <= done}
        if available <= done:
            raise ValueError("missing dependency or cycle in reverification graph")
        done |= available
    queue = {
        "version": 3,
        "source": str(source),
        "tasks": tasks,
        "partition_submit_caps": old["partition_submit_caps"],
        "gpu_submitted_per_model": old["gpu_submitted_per_model"],
        "reverification_of": str(original),
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
                "regression_job": regression_job,
                "old_labels_immutable": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def main():
    parser = argparse.ArgumentParser()
    for name in ("original", "target", "storage", "source"):
        parser.add_argument(name, type=Path)
    parser.add_argument("validation_job")
    parser.add_argument("regression_job")
    a = parser.parse_args()
    print(
        prepare(
            a.original.resolve(),
            a.target.resolve(),
            a.storage.resolve(),
            a.source.resolve(),
            a.validation_job,
            a.regression_job,
        )
    )


if __name__ == "__main__":
    main()
