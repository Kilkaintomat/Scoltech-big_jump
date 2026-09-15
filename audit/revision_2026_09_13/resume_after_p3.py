"""Host-only bounded scheduling window; always restore dispatch after the P3 summary."""
from pathlib import Path
import datetime,json,logging,subprocess,time
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
root=base/"runs/lean_reverification_20260913"
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s")
receipt=json.loads((root/"controller/p3-summary-window.json").read_text(encoding="utf-8"))
deadline=time.monotonic()+600
try:
    while time.monotonic()<deadline:
        q=json.loads((base/"runs/development_20260913/queue.json").read_text(encoding="utf-8"))
        if q["tasks"]["p3/summary"]["state"] in ("COMPLETED","FAILED","BLOCKED","CANCELLED","TIMEOUT"):
            break
        time.sleep(15)
finally:
    results=[]
    for job in receipt["held_jobs"]:
        p=subprocess.run(["scontrol","release",job],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        results.append({"job":job,"returncode":p.returncode,"stderr":p.stderr.decode(errors="replace")})
    q=json.loads((root/"queue.json").read_text(encoding="utf-8"))
    command="cd "+str(base)+" && PYTHONIOENCODING=utf-8 python3 "+q["source"]+"/scripts/campaign/dispatch.py "+str(root)+" >> "+str(root/"controller/console-0913.log")+" 2>&1"
    subprocess.check_call(["tmux","new-session","-d","-s","onebigjump-lean-0913-after-p3",command])
    result={"utc":datetime.datetime.utcnow().isoformat()+"Z","released":results,"controller_restarted":True}
    (root/"controller/p3-summary-window-closed.json").write_text(json.dumps(result)+"\n",encoding="utf-8")
    logging.info("WINDOW CLOSED %s",result)
