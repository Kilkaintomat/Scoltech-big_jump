"""Host Python 3.6 compatible Slurm graph submission; no experiment computation on login."""

import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
download_job, validation_job, unit_job = sys.argv[3:6]
for job in (download_job, validation_job, unit_job):
    if not job.isdigit():
        raise ValueError("invalid prerequisite job ID")
status = (
    subprocess.check_output(
        ["sacct", "-n", "-X", "-j", validation_job, "--format=JobID,State,ExitCode", "-P"]
    )
    .decode()
    .splitlines()
)
if not any(line.split("|")[:3] == [validation_job, "COMPLETED", "0:0"] for line in status):
    raise ValueError("validation job must have completed")
unit_state = (
    subprocess.check_output(
        ["sacct", "-n", "-X", "-j", unit_job, "--format=JobID,State,ExitCode", "-P"]
    )
    .decode()
    .splitlines()
)
unit_passed = any(line.split("|")[:3] == [unit_job, "COMPLETED", "0:0"] for line in unit_state)
unit_pending = any(
    line.split("|")[:2] in ([unit_job, "RUNNING"], [unit_job, "PENDING"]) for line in unit_state
)
if not unit_passed and not unit_pending:
    raise ValueError("full unit suite failed or unavailable")
os.environ["E1_SNAPSHOT"] = str(source)
logdir = root / "logs"
logdir.mkdir(parents=True, exist_ok=True)
receipt = {
    "source": str(source),
    "validation_job": validation_job,
    "download_job": download_job,
    "models": {},
}
receipt_path = root / "submission.json"
if receipt_path.exists():
    raise FileExistsError("campaign already submitted")


def save():
    temporary = receipt_path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    temporary.replace(receipt_path)


def submit(label, script, arguments, deps=(), gpu=False, array=False, hours=12):
    cmd = [
        "sbatch",
        "--parsable",
        "--kill-on-invalid-dep=yes",
        "--job-name=" + label,
        "--partition=" + ("ais-gpu" if gpu else "ais-htc"),
        "--output=" + str(logdir / (label + "-%A_%a.log")),
        f"--time={hours:02d}:00:00",
    ]
    if deps:
        cmd.append("--dependency=afterok:" + ":".join(str(d) for d in deps))
    if gpu:
        cmd.append("--gres=gpu:1")
    else:
        cmd.append("--exclude=cn69")
    if array:
        cmd.append("--array=0-7%2" if gpu else "--array=0-7%4")
    job = (
        subprocess.check_output(cmd + [str(script)] + [str(x) for x in arguments])
        .decode()
        .strip()
        .split(";")[0]
    )
    if not job.isdigit():
        raise RuntimeError("unexpected sbatch receipt")
    print(label, job, flush=True)
    return job


# Use accounting when Slurm has already forgotten a completed download job.
dl = (
    subprocess.check_output(
        ["sacct", "-n", "-X", "-j", download_job, "--format=JobID,State,ExitCode", "-P"]
    )
    .decode()
    .splitlines()
)
download_passed = any(line.split("|")[:3] == [download_job, "COMPLETED", "0:0"] for line in dl)
prepare = submit(
    "campaign-prepare",
    source / "scripts/campaign/prepare.sbatch",
    [root],
    deps=tuple(([] if download_passed else [download_job]) + ([] if unit_passed else [unit_job])),
    hours=1,
)
receipt["prepare"] = prepare
receipt["unit_validation_job"] = unit_job
save()
script = source / "scripts/campaign/run.sbatch"
for name in ("deepseek", "goedel", "kimina"):
    model_root = root / name
    jobs = {}
    receipt["models"][name] = jobs
    if name == "deepseek":
        jobs["pilot_analysis"] = "8462806"
        pilot_end = "8462806"
    else:
        previous = prepare
        for stage in ("smoke", "generate", "verify", "extract", "measure", "analyze"):
            previous = submit(
                name + "-pilot-" + stage,
                script,
                [stage, model_root],
                deps=(previous,),
                gpu=stage in ("generate", "extract"),
                hours=2 if stage in ("generate", "extract") else 12,
            )
            jobs["pilot_" + stage] = previous
            save()
        pilot_end = previous
    gate = submit(
        name + "-collection-gate", script, ["gate", model_root], deps=(prepare, pilot_end), hours=2
    )
    jobs["gate"] = gate
    save()
    generation = submit(
        name + "-main-generate",
        script,
        ["generate", model_root, "--phase", "main"],
        deps=(gate,),
        gpu=True,
        array=True,
        hours=12,
    )
    jobs["generation"] = generation
    save()
    verification = submit(
        name + "-main-verify",
        script,
        ["verify", model_root, "--phase", "main"],
        deps=(generation,),
        array=True,
        hours=24,
    )
    jobs["verification"] = verification
    save()
    gathered = submit(
        name + "-gather-verify",
        script,
        ["gather-verification", model_root, "--phase", "main", "--n-shards", "8"],
        deps=(verification,),
        hours=2,
    )
    jobs["gather_verification"] = gathered
    save()
    extraction = submit(
        name + "-main-extract",
        script,
        ["extract", model_root, "--phase", "main"],
        deps=(gathered,),
        gpu=True,
        array=True,
        hours=4,
    )
    jobs["extraction"] = extraction
    save()
    gathered = submit(
        name + "-gather-extract",
        script,
        ["gather-extraction", model_root, "--phase", "main", "--n-shards", "8"],
        deps=(extraction,),
        hours=2,
    )
    jobs["gather_extraction"] = gathered
    save()
    measurement = submit(
        name + "-main-measure",
        script,
        ["measure", model_root, "--phase", "main"],
        deps=(gathered,),
        hours=24,
    )
    jobs["measurement"] = measurement
    save()
    analysis = submit(
        name + "-main-analyze",
        script,
        ["analyze", model_root, "--phase", "main"],
        deps=(measurement,),
        hours=48,
    )
    jobs["analysis"] = analysis
    save()
print(json.dumps(receipt, indent=2))
