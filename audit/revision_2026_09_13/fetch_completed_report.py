"""Download the already authorized project report; performs no experiments or tests."""
from pathlib import Path
import datetime, hashlib, json, logging, os, subprocess, time
target = Path("/Users/den/work/Scoltech-big_jump/reports/revision_2026_09_13/automatic")
target.mkdir(parents=True,exist_ok=True)
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s")
remote = "/beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_13/delivery"
deadline = time.monotonic() + 72*3600
while time.monotonic() < deadline and not (target/"STOP_FETCH").exists():
    try:
        result = subprocess.run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=15","zhores","cat "+remote+"/latest.json"],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
        if result.returncode:
            time.sleep(60)
            continue
        metadata = json.loads(result.stdout.decode("utf-8"))
        for filename, expected, localname in (
            ("latest.zip",metadata["archive_sha256"],"REVIEW_PACKAGE.zip"),
            ("REPORT.md",metadata["report_sha256"],"REPORT.md")):
            temporary = target/(localname+".part")
            subprocess.run(["scp","-q","-o","BatchMode=yes","-o","ConnectTimeout=15",
                            "zhores:"+remote+"/"+filename,str(temporary)],check=True,timeout=600)
            actual=hashlib.sha256(temporary.read_bytes()).hexdigest()
            if actual != expected: raise ValueError("download digest mismatch: "+filename)
            os.replace(temporary,target/localname)
        metadata["downloaded_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
        (target/"delivery.json").write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
        logging.info("REPORT DOWNLOADED %s",metadata)
        break
    except (OSError, ValueError, subprocess.SubprocessError):
        logging.exception("Delivery unavailable; will retry without changing SSH settings")
    time.sleep(60)
else:
    logging.info("Fetcher stopped or deadline reached")
