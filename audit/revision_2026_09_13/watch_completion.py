"""Host-only completion watcher: snapshot, submit a Slurm report, then package files."""
from pathlib import Path
import datetime, hashlib, json, logging, os, shutil, subprocess, time, zipfile
base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
audit = base / "audit/revision_2026_09_13"
delivery = audit / "delivery"
delivery.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
names = ("lean_reverification_20260913", "development_20260913", "controls_20260913")
failed = {"FAILED","BLOCKED","CANCELLED","TIMEOUT","NODE_FAIL","OUT_OF_MEMORY","BOOT_FAIL"}
attempt = 0
deadline = time.monotonic() + 72*3600
while time.monotonic() < deadline:
    try:
        queues = {n:json.loads((base/"runs"/n/"queue.json").read_text(encoding="utf-8")) for n in names}
        unexpected = {n+":"+k:t["state"] for n,q in queues.items() for k,t in q["tasks"].items()
                      if t["state"] in failed and not (n=="development_20260913" and k=="deduction/gate")}
        complete = all(t["state"]=="COMPLETED" for n,q in queues.items() for k,t in q["tasks"].items()
                       if not (n=="development_20260913" and k=="deduction/gate"))
        if complete or unexpected:
            attempt += 1
            tag = "automatic-" + str(attempt).zfill(3)
            logging.info("REPORT TRIGGER complete=%s unexpected=%s", complete, unexpected)
            try:
                submitted = json.loads(subprocess.check_output(
                    ["python3",str(audit/"submit_report.py"),tag],universal_newlines=True))
            except subprocess.CalledProcessError:
                logging.exception("Report submission unavailable; will retry without changing experiments")
                time.sleep(60)
                continue
            job, output = submitted["job_id"], Path(submitted["output"])
            while time.monotonic() < deadline:
                result = subprocess.check_output(["sacct","-j",job,"--format=JobIDRaw,State","--noheader","--parsable2"],universal_newlines=True)
                states = {line.split("|")[0]:line.split("|")[1] for line in result.splitlines()}
                state = states.get(job,"UNKNOWN")
                if state == "COMPLETED": break
                if state.split()[0].split("+")[0] in failed:
                    raise RuntimeError("Report job failed: "+job+" "+state)
                time.sleep(30)
            if not (output/"manifest.json").is_file(): raise RuntimeError("report has no manifest")
            temporary = delivery/"latest.zip.part"
            with zipfile.ZipFile(str(temporary),"w",compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
                for p in sorted(output.rglob("*")):
                    if p.is_file(): archive.write(str(p),str(p.relative_to(output)))
            os.replace(str(temporary),str(delivery/"latest.zip"))
            shutil.copy2(str(output/"REPORT.md"),str(delivery/"REPORT.md"))
            meta = {"created_utc":datetime.datetime.utcnow().isoformat()+"Z","report_job":job,
                    "report_directory":str(output),"result":"complete" if complete else "needs_investigation",
                    "unexpected_failures":unexpected,
                    "archive_sha256":hashlib.sha256((delivery/"latest.zip").read_bytes()).hexdigest(),
                    "report_sha256":hashlib.sha256((delivery/"REPORT.md").read_bytes()).hexdigest()}
            tmp=delivery/"latest.json.part"
            tmp.write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")
            os.replace(str(tmp),str(delivery/"latest.json"))
            logging.info("DELIVERY READY %s",meta)
            break
    except (OSError, ValueError):
        logging.exception("Could not read a consistent snapshot; will retry")
    time.sleep(30)
else:
    logging.error("Watcher deadline reached; experiments remain unchanged")
