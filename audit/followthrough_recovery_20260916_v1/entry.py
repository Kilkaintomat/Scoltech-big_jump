"""Fail promptly after the journal/manifest closes; avoid vLLM shutdown hanging until Slurm timeout."""
import os,sys,json,hashlib,traceback,runpy
from pathlib import Path
REC=Path(__file__).resolve().parent
OUT=Path("/beegfs/home/denis.rakhmankin/onebigjump/runs/followthrough_recovery_20260916_v1")
def validate():
 for name,expected in json.loads((REC/"source-manifest.json").read_text())["files"].items():
  assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,name

def main():
 validate()
 mode=sys.argv.pop(1)
 if mode=="p2":
  import p2_generate_recovery
  p2_generate_recovery.main()
 elif mode=="p5":
  import p5_run
  p5_run.main()
 else:raise ValueError(mode)
if __name__=="__main__":
 code=0
 try:main()
 except BaseException:
  code=1
  msg=traceback.format_exc();sys.stderr.write(msg)
  (OUT/("error-"+os.environ.get("SLURM_JOB_ID","unknown")+".txt")).write_text(msg)
 finally:
  sys.stdout.flush();sys.stderr.flush()
 os._exit(code)
