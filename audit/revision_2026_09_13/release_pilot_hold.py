"""Host-only release of one documented scheduler hold after all pilot gates pass."""
import datetime, json, logging, subprocess, time
from pathlib import Path
base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
root = base / "runs/lean_reverification_20260913"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
while True:
    try:
        queue = json.loads((root / "queue.json").read_text(encoding="utf-8"))
        states = {model: queue["tasks"][model + "/gate"]["state"] for model in ("deepseek", "goedel", "kimina")}
        if all(s == "COMPLETED" for s in states.values()):
            subprocess.check_call(["scontrol", "release", "8465963"])
            receipt = {"released_job": "8465963", "utc": datetime.datetime.utcnow().isoformat() + "Z", "pilot_gate_states": states}
            (root / "controller/pilot-hold-released.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            logging.info("RELEASED %s", receipt)
            break
        if any(s in ("FAILED", "BLOCKED", "CANCELLED", "TIMEOUT") for s in states.values()):
            logging.error("Gate requires investigation; hold retained: %s", states)
            break
    except (OSError, ValueError):
        logging.exception("Snapshot unavailable; hold retained")
    time.sleep(30)
