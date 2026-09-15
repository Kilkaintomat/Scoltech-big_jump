"""Repeated two-session lifecycle and replay stress on one reserved node."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os, threading, time
from onebigjump.e1.artifacts import digest, finish, write_once
from onebigjump.lean import LeanREPL, discover, verify_trace

base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
runtime = Path(os.environ["E1_REPL_RUNTIME_MANIFEST"])
def files():
    return [int(x) for x in Path("/proc/sys/fs/file-nr").read_text().split()]
def living(pgid):
    found = []
    for p in Path("/proc").glob("[0-9]*/stat"):
        try:
            f = p.read_text().rsplit(")", 1)[1].split()
            if int(f[2]) == pgid and f[0] != "Z": found.append(int(p.parent.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return found
cycles = []
for cycle in range(6):
    barrier = threading.Barrier(2)
    def worker(index):
        result = {"worker": index, "verified": 0, "refuted": 0}
        with LeanREPL(discover(base / "lean_workspace"), imports="import Mathlib\nimport Aesop") as repl:
            pgid = repl._proc.pid
            barrier.wait(timeout=600)
            result["both_started_file_nr"] = files()
            for i in range(50):
                bad = i % 5 == 0
                body = "  have h : True := True.intro\n"
                body += "  exact Nat.zero_ne_one rfl\n  trivial" if bad else "  exact h"
                trace = verify_trace(repl, body, trace_id=f"stress:{cycle}:{index}:{i}",
                                     problem_id="stress", header="example : True := by")
                assert trace.check_absorbing()
                if bad:
                    assert trace.whole_proof_ok is False and trace.t_star == 1
                    assert [s.status.value for s in trace.steps] == ["ok", "error", "unreached"]
                    result["refuted"] += 1
                else:
                    assert trace.whole_proof_ok and trace.verified
                    result["verified"] += 1
            result["before_close_file_nr"] = files()
            result["restarts"] = repl.restarts
        deadline = time.monotonic() + 5
        while living(pgid) and time.monotonic() < deadline: time.sleep(0.05)
        result["remaining_processes"] = living(pgid)
        assert not result["remaining_processes"], result
        return result
    before = files()
    with ThreadPoolExecutor(max_workers=2) as pool:
        workers = list(pool.map(worker, range(2)))
    immediate = files()
    time.sleep(5)
    entry = {"cycle": cycle, "before": before, "workers": workers,
             "after_immediate": immediate, "after_grace": files()}
    cycles.append(entry)
    print(entry, flush=True)
peak = max(w["both_started_file_nr"][0] for c in cycles for w in c["workers"])
limit = files()[2]
assert peak < 0.8 * limit, (peak, limit)
metrics = {"cycles": cycles, "passed": True, "peak_file_nr": peak, "file_limit": limit,
           "traces": sum(w["verified"] + w["refuted"] for c in cycles for w in c["workers"]),
           "sessions": sum(len(c["workers"]) for c in cycles),
           "interpretation": "bounded lifecycle stress; global counters include other kernel users"}
folder = base / "audit/revision_2026_09_13" / (os.environ["SLURM_JOB_ID"] + "-stress")
output = write_once(folder / "metrics.json", metrics)
finish(folder, stage="repeated-two-session-repl-stress", context={"source": digest(source)},
       inputs=[source, runtime, Path(__file__)], outputs=[output], metrics=metrics)
print("STRESS_PASSED", folder, flush=True)
