"""Host-side file-capacity guard for Lean jobs; all execution is inside Slurm."""
import datetime
import fcntl
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

PER_WORKER = 80000
RESERVE = 32768


def choose_workers(allocated, maximum, cpus):
    if allocated < 0 or maximum <= 0 or allocated > maximum or cpus < 1:
        raise ValueError("invalid node capacity")
    return max(0, min(2, cpus // 8, (maximum - allocated - RESERVE) // PER_WORKER))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    job = os.environ["SLURM_JOB_ID"]
    cpus = int(os.environ["SLURM_CPUS_PER_TASK"])
    source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
    folder = Path(__file__).parent / "resource-guard-runs" / job
    folder.mkdir(parents=True, exist_ok=False)
    command = sys.argv[1:]
    if not command:
        raise ValueError("missing child command")
    minimum = int(os.environ.get("E1_GUARD_MIN_WORKERS", "1"))
    if minimum not in (1, 2):
        raise ValueError("minimum workers must be one or two")
    # One guarded job per node prevents races between this project's new jobs.
    # Legacy/other-user processes are covered by the live node-wide count and headroom.
    with Path("/tmp/onebigjump-lean-capacity-%d.lock" % os.getuid()).open("a") as lock:
        print("WAITING_FOR_NODE_LEAN_LOCK", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        started = time.monotonic()
        while True:
            allocated, unused, maximum = map(int, Path("/proc/sys/fs/file-nr").read_text().split())
            workers = choose_workers(allocated, maximum, cpus)
            if workers >= minimum:
                break
            if time.monotonic() - started > 3600:
                raise RuntimeError("no safe Lean file capacity within one hour")
            print("WAITING_FOR_FILE_CAPACITY", allocated, maximum, flush=True)
            time.sleep(15)
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft < 65536:
            raise RuntimeError("per-process descriptor limit below validated Lean environment")
        capacity = {
            "job_id": job, "created_utc": datetime.datetime.utcnow().isoformat() + "Z",
            "node": platform.node(), "allocated_file_handles": allocated, "unused": unused,
            "maximum_file_handles": maximum, "descriptors_budget_per_worker": PER_WORKER,
            "reserve": RESERVE, "selected_workers": workers, "cpus": cpus,
            "per_process_soft_limit": soft, "per_process_hard_limit": hard,
            "scope": "conservative live capacity check; one guarded job per node; other users can still change node load",
            "command": command, "source_sha256": digest(source),
        }
        save(folder / "capacity.json", capacity)
        print("LEAN_CAPACITY", json.dumps(capacity), flush=True)
        env = dict(os.environ, E1_VERIFY_WORKERS=str(workers))
        completed = subprocess.run(command, env=env)
        status = {"returncode": completed.returncode, "finished_utc": datetime.datetime.utcnow().isoformat() + "Z"}
        save(folder / "status.json", status)
        source_meta = json.loads(source.read_text())["metrics"]
        inputs = {str(Path(__file__).resolve()): digest(__file__), str(source): digest(source)}
        for arg in command[:2]:
            p = Path(arg)
            if p.is_file():
                inputs[str(p.resolve())] = digest(p)
        child = os.environ.get("E1_GUARD_CHILD_MANIFEST")
        if child and Path(child).is_file():
            inputs[str(Path(child).resolve())] = digest(child)
        manifest = {
            "stage": "node-file-capacity-guard",
            "source_control": [{k: source_meta[k] for k in ("git_commit", "git_branch", "dirty")}],
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                            "hostname": platform.node(), "slurm_job_id": job,
                            "packages": "standard library only; numerical environment is in the child manifest"},
            "inputs": inputs,
            "outputs": {str(p.resolve()): digest(p) for p in [folder / "capacity.json", folder / "status.json"]},
            "metrics": {"workers": workers, "returncode": completed.returncode},
        }
        save(folder / "manifest.json", manifest)
        return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
