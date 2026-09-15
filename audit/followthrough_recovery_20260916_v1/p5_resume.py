import argparse,subprocess,sys
from stage_support import *
from artifact_bridge import verify_any
def main():
 p=argparse.ArgumentParser();p.add_argument("arm",choices=["calibration","evaluation"]);args=p.parse_args();start("flow")
 root=OUT/("p5_"+args.arm)
 for action,folder in [("generate","generation/shard-000-of-001"),("verify","verification"),("extract","extraction")]:
  mp=root/"main"/folder/"manifest.json"
  if mp.exists():verify_any(mp);continue
  subprocess.run([sys.executable,str(Path(__file__).parent/"entry.py"),"p5",action,args.arm],check=True)
 if args.arm=="calibration":
  mp=root/"calibration_gate/manifest.json"
  if mp.exists():verify_any(mp)
  else:subprocess.run([sys.executable,str(Path(__file__).parent/"entry.py"),"p5","gate"],check=True)
if __name__=="__main__":main()
