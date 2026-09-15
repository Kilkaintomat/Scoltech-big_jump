"""Python 3.6 host job manager. Obey partition submit limits; execute no science on login."""

# ruff: noqa: UP022 -- capture_output requires Python 3.7; login host runs 3.6
import argparse
import datetime
import fcntl
import hashlib
import json
import logging
import os
import subprocess
import time
from pathlib import Path

ACTIVE = {"PENDING", "RUNNING", "CONFIGURING", "COMPLETING", "SUSPENDED", "REQUEUED"}
FAILED = {
    "FAILED",
    "CANCELLED",
    "TIMEOUT",
    "OUT_OF_MEMORY",
    "NODE_FAIL",
    "BOOT_FAIL",
    "DEADLINE",
    "PREEMPTED",
}


def read(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def write(path, value):
    temporary = Path(str(path) + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    temporary.replace(path)


def graph(root):
    receipt = read(root / "submission.json")
    source = Path(receipt["source"])
    tasks = {}

    def add(key, name, stage, phase, dependencies, gpu=False, shard=None, hours=12, job=None):
        arguments = [stage, str(root / name), "--phase", phase]
        if stage.startswith("gather-"):
            arguments += ["--n-shards", "8"]
        if shard is not None:
            arguments += ["--shard", str(shard), "--n-shards", "8"]
        tasks[key] = {
            "model": name,
            "stage": stage,
            "dependencies": dependencies,
            "partition": "ais-gpu" if gpu else "ais-htc",
            "hours": min(hours, 24) if not gpu else hours,
            "script": str(source / "scripts/campaign/run.sbatch"),
            "arguments": arguments,
            "job_name": "obj0909-" + key.replace("/", "-"),
            "job_id": job,
            "state": "WAITING",
        }

    tasks["prepare"] = {
        "model": None,
        "job_id": receipt["prepare"],
        "dependencies": [],
        "partition": "ais-htc",
        "state": "PENDING",
        "external": True,
    }
    # Existing jobs keep their original immutable code and dependencies.
    tasks["deepseek/pilot-analyze"] = {
        "model": "deepseek",
        "job_id": "8462806",
        "dependencies": [],
        "partition": "ais-htc",
        "state": "PENDING",
        "external": True,
    }
    for name in ("goedel", "kimina"):
        previous = "prepare"
        for stage in ("smoke", "generate", "verify", "extract", "measure", "analyze"):
            key = name + "/pilot-" + stage
            add(
                key,
                name,
                stage,
                "pilot",
                [previous],
                gpu=stage in ("generate", "extract"),
                hours=2 if stage in ("generate", "extract") else 12,
            )
            previous = key
    for name in ("deepseek", "goedel", "kimina"):
        add(
            name + "/gate",
            name,
            "gate",
            "main",
            ["prepare", name + "/pilot-analyze"],
            hours=2,
            job=receipt["models"].get(name, {}).get("gate"),
        )
    # Interleave models for fair admission into the bounded queue.
    for stage in ("generate", "verify", "extract"):
        for shard in range(8):
            for name in ("deepseek", "goedel", "kimina"):
                if stage == "generate":
                    deps = [name + "/gate"]
                elif stage == "verify":
                    deps = [name + "/main-generate-" + str(i) for i in range(8)]
                else:
                    deps = [name + "/gather-verify"]
                add(
                    name + "/main-" + stage + "-" + str(shard),
                    name,
                    stage,
                    "main",
                    deps,
                    gpu=stage != "verify",
                    shard=shard,
                    hours={"generate": 12, "verify": 24, "extract": 4}[stage],
                )
    for name in ("deepseek", "goedel", "kimina"):
        add(
            name + "/gather-verify",
            name,
            "gather-verification",
            "main",
            [name + "/main-verify-" + str(i) for i in range(8)],
            hours=2,
        )
        add(
            name + "/gather-extract",
            name,
            "gather-extraction",
            "main",
            [name + "/main-extract-" + str(i) for i in range(8)],
            hours=2,
        )
        add(name + "/measure", name, "measure", "main", [name + "/gather-extract"], hours=24)
        add(name + "/analyze", name, "analyze", "main", [name + "/measure"], hours=24)
    # Reject missing dependencies and cycles before the first submit.
    done = set()
    while len(done) < len(tasks):
        available = {k for k, v in tasks.items() if set(v["dependencies"]) <= done}
        if available <= done:
            raise ValueError("work graph has a missing dependency or a cycle")
        done |= available
    return {
        "source": str(source),
        "tasks": tasks,
        "partition_submit_caps": {"ais-gpu": 6, "ais-htc": 12},
        "gpu_submitted_per_model": 2,
        "version": 1,
    }


def poll(queue):
    ids = [task["job_id"] for task in queue["tasks"].values() if task.get("job_id")]
    states = {}
    if ids:
        output = subprocess.check_output(
            ["sacct", "-X", "-n", "-j", ",".join(ids), "--format=JobID,State,ExitCode", "-P"]
        ).decode()
        for line in output.splitlines():
            values = line.split("|")
            if len(values) >= 3:
                state = values[1].split()[0] if values[1] else "UNKNOWN"
                states[values[0]] = (
                    "COMPLETED" if state == "COMPLETED" and values[2] == "0:0" else state
                )
                if state == "COMPLETED" and values[2] != "0:0":
                    states[values[0]] = "FAILED"
    active = []
    output = subprocess.check_output(
        ["squeue", "-h", "-u", os.environ["USER"], "-o", "%i|%j|%P"]
    ).decode()
    for line in output.splitlines():
        values = line.split("|")
        if len(values) == 3:
            active.append({"job_id": values[0], "name": values[1], "partition": values[2]})
    for task in queue["tasks"].values():
        if task.get("job_id"):
            task["state"] = states.get(task["job_id"], task["state"])
        else:
            # Reconcile a submit accepted just before a controller interruption.
            matches = [row for row in active if row["name"] == task.get("job_name")]
            if len(matches) > 1:
                raise RuntimeError("duplicate submitted job name")
            if matches:
                task.update(job_id=matches[0]["job_id"], state="PENDING")
    return active


def ready(task, tasks):
    return (
        task["state"] != "BLOCKED"
        and not task.get("job_id")
        and all(tasks[d]["state"] == "COMPLETED" for d in task["dependencies"])
    )


def tick(root, queue, dry_run=False):
    active = poll(queue)
    counts = {
        p: sum(row["partition"] == p for row in active) for p in queue["partition_submit_caps"]
    }
    gpu_model = {
        n: sum(
            t["partition"] == "ais-gpu" and t["model"] == n and t["state"] in ACTIVE
            for t in queue["tasks"].values()
        )
        for n in ("deepseek", "goedel", "kimina")
    }
    for key, task in queue["tasks"].items():
        if task.get("job_id"):
            continue
        if any(queue["tasks"][d]["state"] in FAILED | {"BLOCKED"} for d in task["dependencies"]):
            task["state"] = "BLOCKED"
            continue
        if not ready(task, queue["tasks"]):
            continue
        partition = task["partition"]
        if counts[partition] >= queue["partition_submit_caps"][partition]:
            continue
        if partition == "ais-gpu" and gpu_model[task["model"]] >= queue["gpu_submitted_per_model"]:
            continue
        cmd = [
            "sbatch",
            "--parsable",
            "--job-name=" + task["job_name"],
            "--partition=" + partition,
            "--time={}:00:00".format(task["hours"]),
            "--output=" + str(root / "logs" / (task["job_name"] + "-%j.log")),
        ]
        cmd += ["--gres=gpu:1"] if partition == "ais-gpu" else ["--exclude=cn69"]
        cmd += [task["script"]] + task["arguments"]
        if dry_run:
            logging.info("WOULD SUBMIT %s %s", key, cmd)
            continue
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(os.environ, E1_SNAPSHOT=queue["source"]),
        )
        if result.returncode:
            message = result.stderr.decode(errors="replace").strip()
            task["submit_error"] = message
            if "QOSMaxSubmit" in message or "temporarily unavailable" in message:
                logging.info("Capacity unavailable for %s: %s", key, message)
                break
            task["state"] = "BLOCKED"
            logging.error("SUBMIT REJECTED %s: %s", key, message)
            continue
        job = result.stdout.decode().strip().split(";")[0]
        if not job.isdigit():
            raise ValueError("unexpected sbatch reply")
        task.update(
            job_id=job, state="PENDING", submitted_utc=datetime.datetime.utcnow().isoformat() + "Z"
        )
        task.pop("submit_error", None)
        write(root / "queue.json", queue)
        counts[partition] += 1
        if partition == "ais-gpu":
            gpu_model[task["model"]] += 1
        logging.info("SUBMITTED %s %s", key, job)
    queue["last_poll_utc"] = datetime.datetime.utcnow().isoformat() + "Z"
    queue["counts"] = {
        state: sum(t["state"] == state for t in queue["tasks"].values())
        for state in sorted({t["state"] for t in queue["tasks"].values()})
    }
    write(root / "queue.json", queue)
    logging.info("QUEUE %s", queue["counts"])
    return all(t["state"] in FAILED | {"COMPLETED", "BLOCKED"} for t in queue["tasks"].values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
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
    path = root / "queue.json"
    queue = read(path) if path.exists() else graph(root)
    if not path.exists():
        write(path, queue)
        write(
            root / "controller/identity.json",
            {
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "graph_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source": queue["source"],
                "host": os.uname().nodename,
            },
        )
    logging.info("CONTROLLER STARTED pid=%s source=%s", os.getpid(), queue["source"])
    while True:
        try:
            complete = tick(root, queue, args.dry_run)
            if complete or args.once:
                return
        except Exception:
            logging.exception("Poll failed; no dependent work will be launched")
            if args.once:
                raise
        time.sleep(30)


if __name__ == "__main__":
    main()
