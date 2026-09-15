from pathlib import Path
import subprocess,json,hashlib,os
O=Path(__file__).parent
subprocess.run(["lake","build","repl"],cwd=O/"repl",check=True)
import shutil
shutil.copyfile(O/"repl/.lake/build/bin/repl",O/"repl-observer")
(O/"repl-observer").chmod(0o555)
d={"job":os.environ["SLURM_JOB_ID"],"files":{str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [* (O/"repl/REPL").rglob("*.lean"),O/"repl-observer"]}}
(O/"runtime-manifest.json").write_text(json.dumps(d,indent=2),encoding="utf-8")
print("BUILT",flush=True)
