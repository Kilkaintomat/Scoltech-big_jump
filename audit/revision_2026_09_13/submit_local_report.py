"""Host-only snapshot capture and Slurm report submission."""
from pathlib import Path
import datetime,json,os,re,shutil,subprocess,sys,time
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
tag=sys.argv[1]
assert re.fullmatch("[a-z0-9_-]+",tag)
out=base/"audit/revision_2026_09_13/reviews"/tag
(out/"inputs").mkdir(parents=True,exist_ok=False)
(out/"code").mkdir()
shutil.copy2(str(base/"audit/revision_2026_09_13/render_local_report.py"),str(out/"code/report.py"))
for name in ("lean_reverification_20260913_local","development_20260913","controls_20260913_local","lean_reverification_20260913","development_20260913_exactlength"):
    data=json.loads((base/"runs"/name/"queue.json").read_text(encoding="utf-8"))
    (out/"inputs"/(name+"-queue.json")).write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
capture={"captured_utc":datetime.datetime.utcnow().isoformat()+"Z","host":os.uname().nodename}
(out/"inputs/capture.json").write_text(json.dumps(capture)+"\n",encoding="utf-8")
(out/"inputs/squeue.txt").write_text(subprocess.check_output(["squeue","-u","denis.rakhmankin","-o","%.18i %.10P %.60j %.10T %.10M %.8C %R"],universal_newlines=True),encoding="utf-8")
(out/"inputs/sacct.txt").write_text(subprocess.check_output(["sacct","-S","2026-09-13","-u","denis.rakhmankin","--format=JobIDRaw,JobName%64,Partition,State,Submit,Start,End,Elapsed,ExitCode,NodeList,AllocCPUS","--parsable2"],universal_newlines=True),encoding="utf-8")
if len(sys.argv)>2:
    allocation=sys.argv[2]
    assert allocation.isdigit()
    command=["srun","--jobid="+allocation,"--overlap","--exact","--ntasks=1","--cpus-per-task=2",
             "--output="+str(base/"audit/revision_2026_09_13"/("report-"+tag+"-step-%j-%s.log")),
             "--error="+str(base/"audit/revision_2026_09_13"/("report-"+tag+"-step-%j-%s.log")),
             "bash",str(base/"audit/revision_2026_09_13/report_local.sbatch"),str(out)]
    subprocess.check_call(command)
    job=allocation
else:
    job=subprocess.check_output(["sbatch","--parsable","--job-name=obj0913-review-"+tag,"--output="+str(base/"audit/revision_2026_09_13"/("report-"+tag+"-%j.log")),str(base/"audit/revision_2026_09_13/report_local.sbatch"),str(out)],universal_newlines=True).strip()
print(json.dumps({"job_id":job,"output":str(out)}))
