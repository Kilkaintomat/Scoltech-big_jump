import os,sys,json,tempfile,types,hashlib,collections
from pathlib import Path
import p2_generate_recovery as gen
from stage_support import start,check_manifest,read
from artifact_bridge import verify_any,finish_artifact
from onebigjump.e1.spans import original_token_spans,SourceExclusion
from transformers.models.gpt2.tokenization_gpt2 import bytes_to_unicode
from unittest.mock import patch
REC=Path(__file__).parent
OUT=Path("/beegfs/home/denis.rakhmankin/onebigjump/runs/followthrough_recovery_20260916_v2")
for p,h in read(REC/"source-manifest.json")["files"].items():assert gen.digest(p)==h,p
start("p2_pipeline");start("p5");start("flow");start("portable_runtime")
check_manifest(gen.OUT/"p2_pipeline/manifest.json")
class ByteTokenizer:
 def get_added_vocab(self):return {}
 def convert_ids_to_tokens(self,ids):return [bytes_to_unicode()[x] for x in ids]
 def decode(self,ids,**kw):return bytes(ids).decode("utf-8",errors="replace")
tok=ByteTokenizer()
assert original_token_spans(tok,[0xD0,0x96],"Ж")==[(0,1),(1,2)]
assert gen.alignment_status(tok,[0xD0],"�")["category"]=="alignment_error"
assert gen.alignment_status(tok,[65],"A")["passed"]
class FakeTokenizer:
 def apply_chat_template(self,*a,**k):return [10]
 def decode(self,ids,**k):return "broken" if ids==[2] else "good"
class FakeLLM:
 calls=0
 def __init__(self,**kwargs):pass
 def generate(self,ids,params):
  FakeLLM.calls+=1
  return [types.SimpleNamespace(prompt_token_ids=[10],outputs=[types.SimpleNamespace(token_ids=[n],logprobs=[{n:types.SimpleNamespace(logprob=-1.)}],text="mock",finish_reason="stop",stop_reason=None)]) for n in [1,2]]
def aligned(t,ids,text):
 if ids==[2]:raise SourceExclusion("alignment_error","regression: invalid UTF-8")
 return [(0,4)]
with tempfile.TemporaryDirectory() as td:
 base=Path(td)/"p2_pipeline";base.mkdir();(base/"manifest.json").write_text("{}")
 cfg={"model_path":"fake","seed":1,"max_new_tokens":4,"top_p":.95,"top_k":-1,"model_id":"fake","revision":"fixed","tokenizer_revision":"fixed","lean":{"max_heartbeats":1}}
 reqs=[{"trace_id":"trace-"+str(i),"problem_id":"task-"+str(i),"role":"pilot","seed":i,"temperature":.6,"problem":{"statement":"theorem t : True","task_family":"test","exercise_group":"g"}} for i in [1,2]]
 (base/"fake-config.json").write_text(json.dumps(cfg));(base/"fake-requests.json").write_text(json.dumps(reqs))
 captured=[]
 def finish(folder,**kwargs):
  captured.append(kwargs);(folder/"manifest.json").write_text('{"outputs":{}}')
 vm=types.ModuleType("vllm");vm.LLM=FakeLLM;vm.SamplingParams=lambda **kw:kw
 import transformers
 with patch.object(gen,"OUT",Path(td)),patch.object(gen,"original_token_spans",aligned),patch.object(gen,"formal_body",lambda *a:{}),patch.object(gen,"prompt_content",lambda *a:"prompt"),patch.object(gen,"trusted_prefix",lambda *a:"context"),patch.object(gen,"artifact_finish",finish),patch.object(transformers.AutoTokenizer,"from_pretrained",lambda *a,**kw:FakeTokenizer()),patch.dict(sys.modules,{"vllm":vm}):
  gen.generate("fake","pilot",{"context_limit":16})
  folder=base/"fake/pilot/generation"
  saved=[json.loads(line) for line in (folder/"samples.jsonl").read_text().splitlines()]
  assert len(saved)==2 and [r["trace_id"] for r in saved]==["trace-1","trace-2"]
  assert saved[1]["completion_token_ids"]==[2] and saved[1]["original_token_alignment"]["passed"] is False
  metrics=read(folder/"metrics.json");assert metrics["alignment_exclusions"]==1 and not metrics["exact_original_token_reconstruction"] and metrics["all_accounted"]
  assert REC/"source-manifest.json" in captured[0]["inputs"]
  before=(folder/"samples.jsonl").read_bytes();gen.generate("fake","pilot",{"context_limit":16})
  assert FakeLLM.calls==1 and (folder/"samples.jsonl").read_bytes()==before
inventory={}
for model in ["deepseek","goedel"]:
 for role in ["pilot","evaluation"]:
  path=gen.OUT/"p2_pipeline"/model/role/"generation/samples.jsonl"
  rows=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
  assert len({r["trace_id"] for r in rows})==len(rows)
  inventory[model+"/"+role]={"saved":len(rows),"sha256":gen.digest(path) if path.exists() else None,"last_slurm_job":rows[-1].get("slurm_job_id") if rows else None}
plan=read(REC/"flow-plan-v3.json")
assert plan["stages"]["p5_evaluation"]["gate_field"]=="ready_for_evaluation"
assert not any(plan["stages"][x]["resumable"] for x in ["p2_generate","p5_calibration","p5_evaluation"])
import flow_v3
assert flow_v3.status_of({},[{"id":"1"}],{}, {"1":["1","TIMEOUT","0:0","04:00:00","start","end"]})["state"]=="STOPPED"
import unittest
import p2_extract_recovery
from repair_support import validate_architecture
assert p2_extract_recovery.validate_architecture is validate_architecture
suite=unittest.defaultTestLoader.loadTestsFromName("test_repair")
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful() and result.testsRun==7 and not result.skipped
m={"passed":True,"architecture_regressions_passed":result.testsRun,"checks":["split Unicode bytes reconstruct exactly","invalid UTF-8 remains an explicit exclusion","all batch responses saved despite one alignment failure","original token IDs preserved","resume does not regenerate saved rows","recovery source in artifact inputs","original frozen source manifests verified","P5 calibration gate unchanged","program failures not automatically retried"],"saved_before_recovery":inventory}
folder=OUT/"preflight";folder.mkdir(exist_ok=False);mp=folder/"metrics.json";mp.write_text(json.dumps(m,ensure_ascii=False,indent=2))
finish_artifact(folder,stage="runtime-recovery-preflight",context={},inputs=[REC/"source-manifest.json"],outputs=[mp],metrics=m)
print(json.dumps(m,ensure_ascii=False),flush=True)
