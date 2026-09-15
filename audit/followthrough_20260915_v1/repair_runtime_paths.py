"""Relocate container namespace input references without changing any scientific outputs."""
import copy
from stage_support import *
from portable_runtime import RUNTIME_ALIAS,immutable_runtime
from artifact_bridge import verify_any
def main():
 start("portable_runtime");archive=OUT/"provenance_repair";archive.mkdir(exist_ok=True);events=[]
 targets=[OUT/"lean_audit"/m/"manifest.json" for m in MODELS]+[OUT/"new_tasks"/("reference-v2-shard-"+str(i))/"manifest.json" for i in range(4)]
 changed={}
 for p in targets:
  original=read(p);key=str(RUNTIME_ALIAS)
  if key not in original["inputs"]:
   verify_any(p);continue
  oldhash=digest(p);m=copy.deepcopy(original);expected=m["inputs"].pop(key);canonical=immutable_runtime(expected)
  saved=archive/(str(p.parent.relative_to(OUT)).replace("/","__")+"-original.json")
  if saved.exists():assert digest(saved)==oldhash
  else:saved.write_bytes(p.read_bytes())
  m["inputs"][str(canonical)]=expected;m["inputs"][str(saved)]=oldhash
  m["inputs"][str(HERE/"portable_runtime-source-manifest.json")]=digest(HERE/"portable_runtime-source-manifest.json")
  m["provenance_path_repair"]={"original_manifest":str(saved),"original_sha256":oldhash,"runtime_namespace_path":key,"immutable_path":str(canonical),"unchanged_binary_sha256":expected,"repair_slurm_job":os.environ["SLURM_JOB_ID"],"scientific_outputs_unchanged":m["outputs"]==original["outputs"]}
  assert m["metrics"]==original["metrics"] and m["environment"]==original["environment"]
  atomic(p,m);verify_any(p);changed[str(p)]=(oldhash,digest(p));events.append(m["provenance_path_repair"])
 # Update only the dependent preflight input digests, preserving its measurements and sources.
 p=OUT/"p2_pipeline/manifest.json";original=read(p);m=copy.deepcopy(original)
 for name,(before,after) in changed.items():
  if name in m["inputs"]:assert m["inputs"][name]==before;m["inputs"][name]=after
 if m!=original:
  saved=archive/"p2-preflight-original.json";saved.write_bytes(p.read_bytes());m["inputs"][str(saved)]=digest(saved)
  m["provenance_path_repair"]={"original_manifest":str(saved),"affected_inputs":list(changed),"scientific_outputs_unchanged":True,"repair_slurm_job":os.environ["SLURM_JOB_ID"]}
  atomic(p,m)
 verify_any(p)
 atomic(archive/"metrics.json",{"events":events,"scientific_output_files_modified":0,"source_files_modified":0,"preflight_verified":True,"environment":environment()})
 print("RUNTIME PATH PROVENANCE REPAIRED",len(events),flush=True)
if __name__=="__main__":main()
