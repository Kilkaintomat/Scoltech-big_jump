"""Host-side submission of one isolated resumed job after compiler validation."""
from pathlib import Path
import json
import os
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from controller import account, validate, sha
from release_policy import release_reason, MODELS

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
ROOT=BASE/"audit/p5_repair_20260914_v2/runtime_cc"
def main():
    if (ROOT/"resume-job.json").exists():
        raise RuntimeError("resume already submitted")
    validate()
    receipt=json.loads((ROOT/"probe-result.json").read_text(encoding="utf-8"))
    assert account(receipt["job_id"])==("COMPLETED","0:0"), "compiler probe unfinished"
    assert sha(receipt["manifest"])==receipt["sha256"]
    manifest=json.loads(Path(receipt["manifest"]).read_text(encoding="utf-8"))
    assert manifest["metrics"]["passed"]
    for name,expected in manifest["outputs"].items():
        assert sha(name)==expected
    main=BASE/"runs/lean_reverification_20260913_local"
    queue=json.loads((main/"queue.json").read_text(encoding="utf-8"))
    active=subprocess.check_output(["squeue","-h","-u",os.environ["USER"],"-o","%P"]).decode("utf-8")
    n=sum(line.strip()=="ais-gpu" for line in active.splitlines())
    present=all((main/m/("main/extraction/shard-%03d-of-008/manifest.json"%s)).is_file() for m in MODELS for s in range(8))
    okay,reason=release_reason(queue,n,present)
    assert okay,reason
    job=subprocess.check_output(["sbatch","--parsable","--job-name=obj-p5-resume-cc",
        "--output="+str(ROOT/"resume-%j.log"),str(ROOT/"resume.sbatch")]).decode("utf-8").strip()
    assert job.isdigit()
    paths=[ROOT/"resume.sbatch",ROOT/"gpu_mask.py",ROOT.parent/"review_pilot.py",ROOT/"probe-result.json",ROOT/"cc-wrapper.sh",Path(__file__)]
    state={"job_id":job,"compiler_probe_job":receipt["job_id"],"release_reason":reason,
        "config_digests":{str(p):sha(p) for p in paths}}
    (ROOT/"resume-job.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
    print(json.dumps(state))
if __name__=="__main__":
    main()
