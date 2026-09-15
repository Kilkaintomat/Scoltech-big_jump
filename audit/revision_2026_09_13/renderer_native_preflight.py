from pathlib import Path
import ast,os,re
from collections import Counter
from onebigjump.e1.stages import rows
from onebigjump.e1.spans import mask_comments
from onebigjump.e1.verification import ALLOWED_AXIOMS
from onebigjump.e1.artifacts import read_json,write_once,finish,digest
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
a=base/"audit/revision_2026_09_13";p=a/"renderer_native_preflight_input.py"
text=p.read_text(encoding="utf-8");tree=ast.parse(text)
node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="native_policy_inventory")
exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),"exec"))
results={m:native_policy_inventory(base/"runs/lean_reverification_20260913_local"/m/"pilot/verification/labels.jsonl") for m in ["deepseek","goedel","kimina"]}
previous=read_json(a/"8466072-compiler-review/metrics.json")["pilot_inventory"]
assert all(results[m]["native_policy_only_count"]==previous[m]["native_policy_only"] and results[m]["attempts"]==previous[m]["n"] for m in results)
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
out=a/(os.environ["SLURM_JOB_ID"]+"-renderer-preflight")
metrics={"passed":True,"pilot_counts":{m:{k:v for k,v in r.items() if k!="native_policy_only_ids"} for m,r in results.items()},"renderer_sha256":digest(p),"ast_parse_passed":True}
q=write_once(out/"metrics.json",metrics)
finish(out,stage="completion-renderer-native-policy-preflight",context={"source":digest(source)},
 inputs=[source,Path(__file__),p,a/"8466072-compiler-review/manifest.json"],
 outputs=[q],metrics=metrics)
print("RENDERER_PREFLIGHT",metrics,flush=True)
