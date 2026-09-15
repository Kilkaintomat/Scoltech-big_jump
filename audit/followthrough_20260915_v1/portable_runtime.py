"""Use immutable external binary paths for container-bound Lean runtime inputs."""
from stage_support import *
from artifact_bridge import finish_artifact
RUNTIME_ALIAS=ROOT/"lean_workspace/repl/.lake/build/bin/repl"
RUNTIME_FILES=[ROOT/"audit/segmentation_v3_20260914/frozen/repl-observer",ROOT/"runs/repl_runtime_20260913_sealed/repl"]
def immutable_runtime(expected):
 for p in RUNTIME_FILES:
  if digest(p)==expected:return p
 raise ValueError("Observed runtime does not match either pinned immutable binary")
def finish_portable(directory,**kw):
 original=[];inputs=[]
 for p in kw["inputs"]:
  if str(Path(p))==str(RUNTIME_ALIAS):
   expected=digest(p);canonical=immutable_runtime(expected);original.append({"runtime_namespace_path":str(p),"sha256":expected,"immutable_path":str(canonical)});inputs.append(canonical)
  else:inputs.append(p)
 kw["inputs"]=[*inputs,HERE/"portable_runtime-source-manifest.json"]
 kw["context"]={**kw["context"],"runtime_path_resolution":original,"runtime_adapter":digest(HERE/"portable_runtime-source-manifest.json")}
 return finish_artifact(directory,**kw)
