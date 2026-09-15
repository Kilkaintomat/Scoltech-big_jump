import os,json,hashlib
from pathlib import Path
import torch,xgrammar as xgr
from artifact_bridge import verify_any,finish_artifact
from stage_support import read,digest
R=Path(__file__).resolve().parent
O=Path("/beegfs/home/denis.rakhmankin/onebigjump/runs/followthrough_recovery_20260916_v2")/("gpu-preflight-"+os.environ["SLURM_JOB_ID"])
P=Path("/beegfs/home/denis.rakhmankin/onebigjump/audit/p5_repair_20260914_v2/runtime_cc")
receipt=read(P/"probe-result.json");assert digest(receipt["manifest"])==receipt["sha256"]
verify_any(receipt["manifest"])
assert read(receipt["manifest"])["metrics"]["passed"]
assert os.environ["CC"]==str(P/"cc-wrapper.sh")
checks=[]
for vocab,cols,indices in [(151936,151936,None),(151936,151936,[0,2]),(47,64,None)]:
 g=torch.Generator().manual_seed(2026091405)
 x=torch.randn((4,cols),generator=g)
 mask=torch.randint(-(2**31),2**31-1,(4,(vocab+31)//32),generator=g,dtype=torch.int32)
 expected=x.clone();xgr.apply_token_bitmask_inplace(expected,mask,vocab_size=vocab,indices=indices)
 actual=x.cuda();xgr.apply_token_bitmask_inplace(actual,mask.cuda(),vocab_size=vocab,indices=indices);torch.cuda.synchronize()
 assert torch.equal(actual.cpu(),expected)
 checks.append({"vocab":vocab,"columns":cols,"indices":indices,"exact_match":True})
O.mkdir(exist_ok=False);m={"passed":True,"checks":checks,"CC":os.environ["CC"]}
mp=O/"metrics.json";mp.write_text(json.dumps(m,indent=2))
finish_artifact(O,stage="recovery-runtime-gpu-preflight",context={},inputs=[R/"source-manifest.json",Path(receipt["manifest"])],outputs=[mp],metrics=m)
print("RECOVERY GPU MASK CHECK PASSED",flush=True)
