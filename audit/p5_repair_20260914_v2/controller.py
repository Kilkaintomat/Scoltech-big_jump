"""Host-only P5 admission. The protected queue is never modified."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from release_policy import release_reason, MODELS

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/p5_repair_20260914_v2"
MAIN = BASE / "runs/lean_reverification_20260913_local"
STATE = HERE / "controller-state.json"


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(x):
    x["last_poll_utc"] = datetime.datetime.utcnow().isoformat() + "Z"
    p = STATE.with_suffix(".tmp")
    p.write_text(json.dumps(x, indent=2), encoding="utf-8")
    os.replace(str(p), str(STATE))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def account(job):
    result = subprocess.check_output(["sacct", "-X", "-n", "-j", job,
        "--format=JobID,State,ExitCode", "-P"]).decode("utf-8")
    for line in result.splitlines():
        p = line.split("|")
        if p[0] == job:
            return p[1].split()[0], p[2]
    return "UNKNOWN", ""


def validate():
    receipt = read(HERE / "preflight-result.json")
    manifest = read(receipt["manifest"])
    if sha(receipt["manifest"]) != receipt["manifest_sha256"]:
        raise ValueError("preflight manifest changed")
    if account(receipt["job_id"]) != ("COMPLETED", "0:0"):
        raise ValueError("preflight did not finish successfully")
    if not manifest["metrics"]["passed"]:
        raise ValueError("preflight failed")
    for path, expected in manifest["metrics"]["operational_files"].items():
        if sha(path) != expected:
            raise ValueError("validated operational file changed: " + path)
    source = HERE / "source/source-manifest.json"
    if sha(source) != receipt["source_sha256"]:
        raise ValueError("frozen source changed")
    return receipt


def main():
    lock = (HERE / "controller.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = read(STATE) if STATE.exists() else {"status": "WAITING_MAIN_GPU", "job_id": None}
    if state.get("status") in ["COMPLETED", "BLOCKED", "FAILED"]:
        return
    try:
        validate()
        if state.get("status") == "SUBMITTING" and not state.get("job_id"):
            raise RuntimeError("submission interrupted; reconcile job name before resuming")
        while True:
            if state.get("job_id"):
                status, code = account(state["job_id"])
                state.update(status="PILOT_" + status, exit_code=code)
                if status == "COMPLETED" and code == "0:0":
                    p = BASE / "runs/p5_repair_20260914_v2/summary/manifest.json"
                    manifest = read(p)
                    for name, expected in manifest["outputs"].items():
                        if sha(name) != expected:
                            raise ValueError("pilot result changed")
                    state.update(status="COMPLETED", result_manifest=str(p),
                        technical_gates={k:v["technical_gate"]["passed"] for k,v in manifest["metrics"]["arms"].items()},
                        scientific_decision="inconclusive")
                    save(state)
                    return
                if status in ["FAILED", "TIMEOUT", "CANCELLED", "OUT_OF_MEMORY", "NODE_FAIL"]:
                    state["status"] = "FAILED"; save(state); return
                save(state); time.sleep(30); continue
            queue = read(MAIN / "queue.json")
            output = subprocess.check_output(["squeue", "-h", "-u", os.environ["USER"], "-o", "%P"]).decode("utf-8")
            gpu_jobs = sum(line.strip() == "ais-gpu" for line in output.splitlines())
            present = all((MAIN / model / ("main/extraction/shard-%03d-of-008/manifest.json" % shard)).is_file()
                for model in MODELS for shard in range(8))
            okay, reason = release_reason(queue, gpu_jobs, present)
            state.update(status="WAITING_MAIN_GPU", reason=reason, active_gpu_jobs=gpu_jobs)
            if okay:
                validate()
                state.update(status="SUBMITTING", job_name="obj-p5-paired-format-0914-v2")
                save(state)
                job = subprocess.check_output(["sbatch", "--parsable", "--job-name=" + state["job_name"],
                    "--output=" + str(HERE / "pilot-%j.log"), str(HERE / "pilot.sbatch")]).decode("utf-8").strip().split(";")[0]
                if not job.isdigit():
                    raise ValueError("unexpected sbatch reply")
                state.update(status="PILOT_SUBMITTED", job_id=job)
            save(state)
            time.sleep(30)
    except Exception as exc:
        state.update(status="BLOCKED", error=repr(exc)); save(state); raise

if __name__ == "__main__":
    main()
