"""Bridge for frozen source manifests and recursive artifact manifests."""
from stage_support import *
from onebigjump.e1.artifacts import write_once
def verify_any(path,seen=None):
 path=Path(path);seen=set() if seen is None else seen;key=str(path.resolve())
 if key in seen:return
 seen.add(key);d=read(path)
 if not any(k in d for k in ["files","inputs","outputs"]):raise ValueError("Unrecognized manifest schema: "+str(path))
 for section in ["files","inputs","outputs"]:
  for name,expected in d.get(section,{}).items():
   if digest(name)!=expected:raise ValueError("Artifact digest mismatch: "+name)
   if section=="inputs" and name.endswith("manifest.json"):verify_any(name,seen)
def finish_artifact(directory,*,stage,context,inputs,outputs,metrics):
 for p in inputs:
  if Path(p).name.endswith("manifest.json"):verify_any(p)
 sources=[read(p).get("source_control") for p in inputs if Path(p).name.endswith("source-manifest.json")]
 m={"stage":stage,"context":context,"source_control":sources,"environment":environment(),
  "inputs":{str(Path(p).resolve()):digest(p) for p in inputs},
  "outputs":{str(Path(p).resolve()):digest(p) for p in outputs},"metrics":clean(metrics)}
 return write_once(Path(directory)/"manifest.json",m)
