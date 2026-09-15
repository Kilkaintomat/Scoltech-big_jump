import sys
from stage_support import *
from artifact_bridge import finish_artifact
import lean_audit_worker as original
def fixed(*args,**kwargs):
 kwargs["context"]={**kwargs["context"],"finalization_repair":{"source":digest(HERE/"audit_finalize-source-manifest.json"),"original_slurm_array":"8467329","meaning":"Completed verifier rows reused unchanged; this execution finalizes their artifact metadata."}}
 kwargs["inputs"]=[*kwargs["inputs"],HERE/"audit_finalize-source-manifest.json"]
 return finish_artifact(*args,**kwargs)
if __name__=="__main__":
 start("audit_finalize");original.artifact_finish=fixed;original.main()
