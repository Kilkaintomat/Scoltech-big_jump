"""Python 3.6 host controller for an additive campaign; never cancels any Slurm job."""

# ruff: noqa: UP022 -- login node Python 3.6
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import logging
import os
import subprocess
import time
from pathlib import Path


def manager():
    path = Path(__file__).resolve().parents[1] / "campaign/dispatch.py"
    spec = importlib.util.spec_from_file_location("campaign_manager", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def graph(root, source, validation):
    tasks = {}
    original = Path("/beegfs/home/denis.rakhmankin/onebigjump/runs/lean_recovery_20260911_v3")

    def add(key, stage, folder, deps=None, gpu=False, arguments=None, files=None, group="other"):
        tasks[key] = {
            "job_id": None,
            "state": "WAITING",
            "dependencies": ["validation"] + (deps or []),
            "partition": "ais-gpu" if gpu else "ais-htc",
            "stage": stage,
            "arguments": [stage, str(folder)] + (arguments or []),
            "file_dependencies": [str(p) for p in (files or [])],
            "group": group,
            "job_name": "obj-exp11-" + key.replace("/", "-"),
        }

    tasks["validation"] = {
        "job_id": str(validation),
        "state": "PENDING",
        "dependencies": [],
        "partition": "ais-htc",
        "external": True,
    }
    tasks["download"] = {
        "job_id": "8464476",
        "state": "COMPLETED",
        "dependencies": [],
        "partition": "ais-htc",
        "external": True,
    }
    # Cheap controls and technical pilot have precedence over long Monte Carlo shards.
    for phase in ("pilot", "main"):
        for model in ("deepseek", "goedel", "kimina"):
            model_root = original / model
            files = [model_root / phase / "measurement/manifest.json"]
            for stage in ("positional", "whitening"):
                key = phase + "/" + model + "/" + stage
                add(
                    key,
                    stage,
                    root / "e1-controls" / key,
                    files=files,
                    arguments=["--root", str(model_root), "--phase", phase, "--shard", "-1"],
                )
    synthetic = root / "deduction"
    add(
        "deduction/inputs",
        "deduction-population",
        synthetic / "inputs",
        arguments=["--root", str(synthetic)],
    )
    previous = "deduction/inputs"
    for phase in ("pilot", "main"):
        generators = []
        n_shards = 1 if phase == "pilot" else 8
        for shard in range(n_shards):
            key = "deduction/" + phase + "-generate-" + str(shard)
            add(
                key,
                "deduction-generate",
                synthetic / phase / "generation" / f"shard-{shard:03d}-of-{n_shards:03d}",
                deps=[previous, "download"],
                gpu=True,
                arguments=[
                    "--root",
                    str(synthetic),
                    "--phase",
                    phase,
                    "--shard",
                    str(shard),
                    "--n-shards",
                    str(n_shards),
                ],
            )
            generators.append(key)
        dependencies = generators
        for stage, directory in (
            ("verify", "verification"),
            ("extract", "extraction"),
            ("measure", "measurement"),
            ("analyze", "analysis"),
        ):
            key = "deduction/" + phase + "-" + stage
            add(
                key,
                "deduction-" + stage,
                synthetic / phase / directory,
                deps=dependencies,
                gpu=stage == "extract",
                arguments=["--root", str(synthetic), "--phase", phase],
            )
            dependencies = [key]
        if phase == "pilot":
            previous = "deduction/gate"
            add(
                previous,
                "deduction-gate",
                synthetic / "pilot/gate",
                deps=dependencies,
                arguments=["--root", str(synthetic)],
            )
    measurements = []
    for seed in range(5):
        for arm in ("real", "null"):
            name = arm + "-" + str(seed)
            training = root / "p4" / name / "training"
            measured = root / "p4" / name / "measurement"
            config = source / "configs/readiness" / ("p4-" + name + ".json")
            train_key = "p4/" + name + "/train"
            measure_key = "p4/" + name + "/measure"
            add(train_key, "p4-train", training, gpu=True, arguments=["--config", str(config)])
            add(
                measure_key,
                "p4-measure",
                measured,
                deps=[train_key],
                arguments=["--root", str(training), "--config", str(config)],
            )
            add(
                "p4/" + name + "/tail",
                "p4-tail",
                root / "p4" / name / "tail",
                deps=[measure_key],
                arguments=["--root", str(measured)],
            )
            measurements.append(measure_key)
    add(
        "p4/summary",
        "p4-summary",
        root / "p4/summary",
        deps=measurements,
        arguments=["--root", str(root / "p4")],
    )
    for model in ("deepseek", "goedel", "kimina"):
        for shard in range(10):
            key = "main/" + model + "/refit-" + str(shard)
            add(
                key,
                "whitening",
                root / "e1-controls" / key,
                files=[original / model / "main/measurement/manifest.json"],
                group="calibration",
                arguments=[
                    "--root",
                    str(original / model),
                    "--phase",
                    "main",
                    "--shard",
                    str(shard),
                ],
            )
    config_path = source / "configs/readiness/calibration.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    calibration_tasks = []
    for shard in range(config["shards_per_scenario"]):
        for scenario in config["scenarios"]:
            key = "calibration/" + scenario + "/" + str(shard)
            calibration_tasks.append(key)
            add(
                key,
                "calibration",
                root / key,
                group="calibration",
                arguments=[
                    "--config",
                    str(config_path),
                    "--scenario",
                    scenario,
                    "--shard",
                    str(shard),
                ],
            )
    add(
        "calibration/summary",
        "calibration-summary",
        root / "calibration-summary",
        deps=calibration_tasks,
        arguments=["--root", str(root / "calibration")],
    )
    return {
        "source": str(source),
        "tasks": tasks,
        "partition_submit_caps": {"ais-htc": 4, "ais-gpu": 2},
        "calibration_submit_cap": 2,
        "protected_campaign": str(original),
        "version": 1,
    }


def ready(task, tasks):
    return (
        not task.get("job_id")
        and task["state"] == "WAITING"
        and all(tasks[key]["state"] == "COMPLETED" for key in task["dependencies"])
        and all(Path(path).is_file() for path in task.get("file_dependencies", []))
    )


def tick(root, queue, host):
    host.poll(queue)
    owned = [t for t in queue["tasks"].values() if not t.get("external")]
    counts = {
        p: sum(t["partition"] == p and t["state"] in host.ACTIVE for t in owned)
        for p in queue["partition_submit_caps"]
    }
    calibration = sum(t.get("group") == "calibration" and t["state"] in host.ACTIVE for t in owned)
    for key, task in queue["tasks"].items():
        if task.get("external"):
            continue
        # Only infrastructure interruption/time limit gets a bounded, journal-based retry.
        if (
            task["state"] in {"TIMEOUT", "NODE_FAIL", "PREEMPTED", "BOOT_FAIL"}
            and len(task.get("attempt_history", [])) < 3
        ):
            task.setdefault("attempt_history", []).append(
                {"job_id": task["job_id"], "state": task["state"]}
            )
            task.update(job_id=None, state="WAITING")
            host.write(root / "queue.json", queue)
        if not task.get("job_id") and any(
            queue["tasks"][d]["state"] in host.FAILED | {"BLOCKED"} for d in task["dependencies"]
        ):
            task["state"] = "BLOCKED"
        if not ready(task, queue["tasks"]):
            continue
        partition = task["partition"]
        if counts[partition] >= queue["partition_submit_caps"][partition]:
            continue
        if task["group"] == "calibration" and calibration >= queue["calibration_submit_cap"]:
            continue
        command = [
            "sbatch",
            "--parsable",
            "--job-name=" + task["job_name"],
            "--partition=" + partition,
            "--time=24:00:00",
            "--output=" + str(root / "logs" / (task["job_name"] + "-%j.log")),
        ]
        command += (
            ["--gres=gpu:1", "--nice=10000"] if partition == "ais-gpu" else ["--exclude=cn69"]
        )
        command += [str(Path(queue["source"]) / "scripts/readiness/run.sbatch")] + task["arguments"]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(os.environ, E1_SNAPSHOT=queue["source"]),
        )
        if result.returncode:
            task["submit_error"] = result.stderr.decode(errors="replace")
            if "QOSMaxSubmit" not in task["submit_error"]:
                task["state"] = "BLOCKED"
            logging.error("SUBMIT %s: %s", key, task["submit_error"])
            host.write(root / "queue.json", queue)
            break
        job = result.stdout.decode().strip().split(";")[0]
        if not job.isdigit():
            raise ValueError("unexpected sbatch reply")
        task.update(
            job_id=job, state="PENDING", submitted_utc=datetime.datetime.utcnow().isoformat() + "Z"
        )
        host.write(root / "queue.json", queue)
        counts[partition] += 1
        calibration += int(task["group"] == "calibration")
        logging.info("SUBMITTED %s %s", key, job)
    queue["last_poll_utc"] = datetime.datetime.utcnow().isoformat() + "Z"
    queue["counts"] = {
        state: sum(t["state"] == state for t in queue["tasks"].values())
        for state in sorted({t["state"] for t in queue["tasks"].values()})
    }
    host.write(root / "queue.json", queue)
    logging.info("QUEUE %s", queue["counts"])
    return all(
        t["state"] in host.FAILED | {"COMPLETED", "BLOCKED"} for t in queue["tasks"].values()
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[
            logging.FileHandler(str(root / "controller/dispatch.log")),
            logging.StreamHandler(),
        ],
    )
    lock = (root / "controller/dispatch.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    host = manager()
    path = root / "queue.json"
    if path.exists():
        queue = host.read(path)
    else:
        queue = graph(root, Path(os.environ["E1_SNAPSHOT"]).resolve(), args.validation)
        host.write(path, queue)
        host.write(
            root / "controller/identity.json",
            {
                "source": queue["source"],
                "graph_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
        )
    logging.info("CONTROLLER STARTED pid=%s", os.getpid())
    while True:
        try:
            done = tick(root, queue, host)
            if done or args.once:
                return
        except Exception:
            logging.exception("Poll failed; dependent submissions withheld")
            if args.once:
                raise
        time.sleep(30)


if __name__ == "__main__":
    main()
