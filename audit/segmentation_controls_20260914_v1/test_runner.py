import os,subprocess,sys,time
from pathlib import Path
from data import REPO,RUN as STATES,read,atomic,digest,environment
HERE=REPO/"audit/segmentation_controls_20260914_v1"
OUT=REPO/"runs/segmentation_controls_20260914_v1"/("tests-"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=False)
start=time.time()
run=subprocess.run([sys.executable,str(HERE/"test_controls.py"),"-v"],capture_output=True,text=True)
log=OUT/"tests.log";log.write_text(run.stdout+run.stderr,encoding="utf-8")
print(log.read_text(encoding="utf-8"),flush=True)
metrics={"passed":run.returncode==0,"exit_code":run.returncode,"elapsed_s":time.time()-start,"live_lean":False,"live_gpu":False}
atomic(OUT/"metrics.json",metrics)
atomic(OUT/"manifest.json",{"config":{"checks":"boundary denominators, recomputed argmax, task bootstrap, positional null, source parse"},
 "source_control":read(STATES/"source-manifest.json")["source_control"],"environment":environment(),
 "inputs":{str(HERE/"source-manifest.json"):digest(HERE/"source-manifest.json")},
 "outputs":{str(p):digest(p) for p in [log,OUT/"metrics.json"]}})
sys.exit(run.returncode)
