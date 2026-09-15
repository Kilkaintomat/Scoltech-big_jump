"""Finite host-only Slurm continuation. No Lean or scientific computation on login."""
import datetime
import fcntl
import hashlib
import importlib.util
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from policy import activate, release, MODELS

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/revision_2026_09_13/saved-continuation-v1"
ROOT = BASE / "runs/lean_reverification_20260913_local"
OLD = BASE / "audit/revision_2026_09_13/snapshots/lean-local-toolchain-v7"
REPAIRED = BASE / "audit/revision_2026_09_13/speedup-v2/repaired"
spec = importlib.util.spec_from_file_location("original_dispatch", OLD / "scripts/campaign/dispatch.py")
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)
read, write = dispatch.read, dispatch.write


def utc():
    return datetime.datetime.utcnow().isoformat() + "Z"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def account(job_ids):
    if not job_ids:
        return {}
    text = subprocess.check_output(["sacct", "-X", "-n", "-j", ",".join(job_ids),
        "--format=JobID,State,ExitCode", "-P"]).decode()
    result = {}
    for line in text.splitlines():
        p = line.split("|")
        if len(p) >= 3:
            result[p[0]] = (p[1].split()[0] if p[1] else "UNKNOWN", p[2])
    return result


def shallow_manifest(path):
    # Full recursive DAG checking is done by the successful Slurm preflight/repair.
    # On the login node check only these small operational receipt outputs.
    meta = read(path)
    for name, expected in meta["outputs"].items():
        if sha(name) != expected:
            raise ValueError("receipt digest mismatch: " + name)
    return meta


def event(kind, before, after, detail):
    folder = HERE / "events" / (utc().replace(":", "-") + "-" + kind)
    folder.mkdir(parents=True)
    write(folder / "queue-before.json", before)
    write(folder / "queue-after.json", after)
    write(folder / "receipt.json", dict(
        utc=utc(), kind=kind, detail=detail,
        before_sha256=sha(folder / "queue-before.json"),
        after_sha256=sha(folder / "queue-after.json"),
        controller_sha256=sha(__file__), policy_sha256=sha(HERE / "policy.py")))
    write(ROOT / "queue.json", after)
    logging.info("%s %s", kind, detail)


def preflight():
    meta = shallow_manifest(HERE / "preflight/manifest.json")
    receipt = meta["metrics"]
    if account([receipt["job_id"]]).get(receipt["job_id"]) != ("COMPLETED", "0:0"):
        raise ValueError("preflight Slurm job is not successfully completed")
    for name, expected in receipt["operational_code"].items():
        if sha(name) != expected:
            raise ValueError("operational code changed since preflight")
    if sha(Path(receipt["source"]) / "source-manifest.json") != receipt["source_sha256"]:
        raise ValueError("validated source identity changed")
    if not receipt["passed"]:
        raise ValueError("preflight did not pass")
    return receipt


def discover_work():
    return [model + "/" + str(shard) for shard in range(8) for model in MODELS
        if (ROOT / model / ("main/verification/shard-%03d-of-008/manifest.json" % shard)).is_file()
        and not (REPAIRED / model / ("shard-%03d-of-008/manifest.json" % shard)).is_file()]


def reconcile_intent(item):
    # A crash around sbatch must never create a duplicate pass.
    text = subprocess.check_output(["sacct", "-X", "-n", "-u", os.environ["USER"],
        "-S", item["created_utc"][:10], "--format=JobID,JobName%100,State,ExitCode", "-P"]).decode()
    matches = []
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) >= 4 and parts[1] == item["job_name"]:
            matches.append(parts[0])
    if len(set(matches)) == 1:
        item["job_id"] = matches[0]
        return
    raise RuntimeError("ambiguous repair submission; inspect scheduler before retry: " + item["job_name"])


def collect_pass(item):
    job = item["job_id"]
    path = HERE / ("pass-" + job) / "manifest.json"
    meta = shallow_manifest(path)
    if meta["stage"] != "saved-continuation-pass" or meta["environment"]["slurm_job_id"] != job:
        raise ValueError("repair receipt job mismatch")
    if not meta["metrics"]["passed"]:
        raise ValueError("repair pass did not pass")
    accepted = meta["metrics"]["accepted_models"]
    for model, evidence in accepted.items():
        expected = ROOT / model / "main/verification/manifest.json"
        if evidence["manifest"] != str(expected) or sha(expected) != evidence["manifest_sha256"]:
            raise ValueError("accepted merged manifest changed")
        merged = read(expected)
        if merged["metrics"] != evidence["metrics"] or merged["stage"] != evidence["stage"]:
            raise ValueError("merged evidence differs from validated receipt")
    return accepted


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
        handlers=[logging.FileHandler(str(HERE / "controller.log")), logging.StreamHandler()])
    own_lock = (HERE / "controller.lock").open("w")
    fcntl.flock(own_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    queue_lock = (ROOT / "controller/dispatch.lock").open("w")
    fcntl.flock(queue_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    receipt = preflight()
    queue = read(ROOT / "queue.json")
    state_path = HERE / "state.json"
    state = read(state_path) if state_path.exists() else dict(
        status="STARTING", activated_utc=utc(), passes=[], scope="saved 20016 attempts; no new generation")
    if state.get("status") == "BLOCKED":
        raise RuntimeError("recorded failure requires review before restarting")
    try:
        dispatch.poll(queue)
        if not queue.get("saved_continuation"):
            amended = activate(queue, receipt, str(HERE / "verify-v9-node.sbatch"))
            event("activate", queue, amended, amended["saved_continuation"])
            queue = amended
        state["status"] = "RUNNING"
        write(state_path, state)
        while True:
            active = dispatch.poll(queue)
            current = next((p for p in state["passes"] if not p.get("collected")), None)
            if current:
                if not current.get("job_id"):
                    reconcile_intent(current)
                    write(state_path, state)
                status = account([current["job_id"]]).get(current["job_id"])
                if status and status[0] in dispatch.FAILED:
                    raise RuntimeError("repair job failed: " + str(status))
                if status and status[0] == "COMPLETED":
                    if status[1] != "0:0":
                        raise RuntimeError("repair job has nonzero exit")
                    accepted = collect_pass(current)
                    amended = release(queue, accepted, current["job_id"], True)
                    if amended != queue:
                        event("release", queue, amended, dict(job_id=current["job_id"], models=list(accepted)))
                        queue = amended
                    current.update(collected=True, completed_utc=utc(), accepted_models=list(accepted))
                    write(state_path, state)
                    current = None
            needed = discover_work()
            # With a main-submit cap of three, one repair may bring the total to four.
            cpu_jobs = sum(row["partition"] == "ais-htc" for row in active)
            if needed and not current and cpu_jobs < 4:
                preflight()
                item = dict(job_name="obj0913-saved-v9-pass-%02d" % (len(state["passes"]) + 1),
                            created_utc=utc(), work_at_submission=needed, job_id=None, collected=False)
                state["passes"].append(item)
                write(state_path, state)  # record intent before scheduler mutation
                output = subprocess.check_output(["sbatch", "--parsable",
                    "--job-name=" + item["job_name"], "--output=" + str(HERE / "repair-%j.log"),
                    str(HERE / "repair-v9.sbatch")]).decode().strip().split(";")[0]
                if not output.isdigit():
                    raise RuntimeError("unexpected repair sbatch reply")
                item["job_id"] = output
                write(state_path, state)
                logging.info("REPAIR SUBMITTED %s %s", output, needed)
            terminal = dispatch.tick(ROOT, queue)
            state.update(last_poll_utc=utc(), remaining_ready_shards=needed,
                         accepted_models=queue["saved_continuation"]["merged"],
                         queue_counts=queue["counts"])
            if all(queue["tasks"][m + "/analyze"]["state"] == "COMPLETED" for m in MODELS):
                state["status"] = "COMPLETED"
                state["finished_utc"] = utc()
                write(state_path, state)
                logging.info("MAIN ANALYSES COMPLETED; independent controls keep their controllers")
                return
            if (terminal and not needed and not any(not p.get("collected") for p in state["passes"])):
                raise RuntimeError("remaining pipeline is blocked; no automatic retries or gate bypass")
            write(state_path, state)
            time.sleep(30)
    except Exception as exc:
        state.update(status="BLOCKED", stopped_utc=utc(), error=repr(exc))
        write(state_path, state)
        logging.exception("CONTINUATION BLOCKED; existing Slurm jobs preserved")
        raise


if __name__ == "__main__":
    main()
