import concurrent.futures, json, os, pathlib, time
from onebigjump.lean.verifier import LeanREPL
from onebigjump.lean.environment import discover
out = pathlib.Path("audit/revision_2026_09_12/startup-" + os.environ["SLURM_JOB_ID"])
out.mkdir(exist_ok=True)
print("CWD", os.getcwd(), flush=True)
for ws in (pathlib.Path("lean_workspace"), pathlib.Path("/beegfs/home/denis.rakhmankin/onebigjump/lean_workspace")):
    print("WORKSPACE", str(ws), str(ws.resolve()), discover(ws).as_dict(), flush=True)
    for path in (ws / "mathlib_project/.lake/packages").glob("*"):
        print("PACKAGE",str(path),path.is_dir(),str(path.resolve()),flush=True)
def one(i):
    events=[]
    class Probe(LeanREPL):
        def _exchange(self, payload, timeout_s=None):
            reply=super()._exchange(payload, timeout_s)
            events.append({"request":payload,"response":reply})
            return reply
    repl=Probe(discover(pathlib.Path("/beegfs/home/denis.rakhmankin/onebigjump/lean_workspace")), imports="import Mathlib\nimport Aesop")
    t=time.monotonic()
    try:
        with repl:
            repl.command("#check Mathlib.Meta.NormNum.Result")
            r=repl.command("set_option maxHeartbeats 400000\nexample : True := by sorry")
            if r.get("sorries"):
                repl.tactic('run_tac do Lean.logInfo m!"heartbeats={Lean.maxHeartbeats.get (← Lean.getOptions)}"', r["sorries"][0]["proofState"])
        status="ok"
    except Exception as exc:
        status=repr(exc)
    finally:
        repl.close()
    row={"index":i,"status":status,"elapsed_s":time.monotonic()-t,"stderr":list(repl._stderr),"events":events}
    (out/str(i)).write_text(json.dumps(row,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in row.items() if k!="events"},ensure_ascii=False),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(one,range(8)))
