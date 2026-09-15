"""CPU and live-Lean regression gate for isolated recovery."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from onebigjump.e1.artifacts import digest,identity,environment,Journal
import campaign_annotation as ca
from recovery_support import inherit
from campaign_worker import atomic_json
from onebigjump.lean.verifier import ReplError

ROOT=Path("/beegfs/home/denis.rakhmankin/onebigjump")
AUDIT=ROOT/"audit/segmentation_recovery_20260914_v1"
RUN=ROOT/"runs/segmentation_20260914_v3_recovery1"
OLD=ROOT/"runs/segmentation_20260914_v3"
checks={}
item={"trace_id":"test","model":"test","problem_id":"test","old_category":"verified",
      "label_row_sha256":"label-hash","source_identity":{},"header":"","body":""}
class Fail:
    def __init__(self,err):self.err=err
    def inspect(self,*args):raise self.err
for name,err,status in [
    ("panic",ReplError("the REPL exited: INTERNAL PANIC: Nat.pow exponent is too big"),"observer_runtime_error"),
    ("protocol",ReplError("invalid response"),"observer_runtime_error"),
    ("timeout",TimeoutError("timeout"),"observer_timeout"),
    ("source",ValueError("source changed"),"alignment_or_source_exclusion")]:
    row,detail,restart=ca.annotate(item,Fail(err),None)
    checks[name]=row["status"]==status and row["p2_eligible"] is False and restart
    if name=="panic":checks["panic_not_proof_failure"]=row["old_category"]=="verified" and row["ready_for_activation_extraction"] is False
row,detail,restart=ca.annotate({**item,"exclusion":"original exclusion"},None,None)
checks["upstream_exclusion_unchanged"]=row["status"]=="upstream_exclusion" and not restart
try:ca.annotate(item,Fail(RuntimeError("programming bug")),None)
except RuntimeError:checks["unexpected_bug_not_swallowed"]=True
else:checks["unexpected_bug_not_swallowed"]=False

oldsource=json.loads((OLD/"source-manifest.json").read_text())
for name,h in oldsource["files"].items():
    if digest(name)!=h:raise ValueError("parent frozen source changed")
source={**oldsource,"parent_source_manifest":str(OLD/"source-manifest.json"),
        "parent_source_sha256":digest(OLD/"source-manifest.json"),
        "environment":environment(),"files":{**oldsource["files"],**{str(p):digest(p) for p in AUDIT.iterdir() if p.suffix in [".py",".sbatch"]}},
        "recovery_policy":json.loads((RUN/"config.json").read_text())["recovery_policy"]}
atomic_json(RUN/"source-manifest.json",source)
before=json.loads((OLD/"shards/004/progress.json").read_text())["completed"]
subprocess.run([sys.executable,str(AUDIT/"campaign_worker.py"),"--root",str(RUN),"--task","4","--max-new","2"],check=True)
p=json.loads((RUN/"shards/004/progress.json").read_text())
checks["live_panic_saved_and_next_processed"]=p["completed"]==before+2
rows=[json.loads(x) for x in (RUN/"shards/004/observations.jsonl").read_text().splitlines()]
checks["live_panic_separate_status"]=any(r["status"]=="observer_runtime_error" and "Nat.pow" in r.get("reason","") for r in rows)
checks["old_rows_preserved"]=sum("inherited_parent_row_sha256" in r for r in rows)==before
oldhash=digest(OLD/"shards/004/observations.jsonl")
subprocess.run([sys.executable,str(AUDIT/"campaign_worker.py"),"--root",str(RUN),"--task","4","--max-new","1"],check=True)
p=json.loads((RUN/"shards/004/progress.json").read_text())
checks["resume_no_duplicate"]=p["completed"]==before+3
checks["parent_journal_unchanged"]=digest(OLD/"shards/004/observations.jsonl")==oldhash
checks["new_context_distinct"]=digest(RUN/"shards/004/observations.identity.json")!=digest(OLD/"shards/004/observations.identity.json")
metrics={"passed":all(checks.values()),"checks":checks,"job":os.environ.get("SLURM_JOB_ID")}
atomic_json(AUDIT/"preflight-metrics.json",metrics)
atomic_json(AUDIT/"preflight-manifest.json",{"config":json.loads((RUN/"config.json").read_text()),"source":source,
    "outputs":{str(AUDIT/"preflight-metrics.json"):digest(AUDIT/"preflight-metrics.json")}})
print(json.dumps(metrics),flush=True)
if not metrics["passed"]:raise SystemExit(1)
