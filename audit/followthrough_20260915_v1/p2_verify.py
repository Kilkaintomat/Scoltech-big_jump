import argparse,collections,gzip,time
from stage_support import *
from onebigjump.lean import LeanREPL,discover
from onebigjump.e1.verification import verify_one
from onebigjump.e1.artifacts import Journal,identity,write_once
from artifact_bridge import finish_artifact as artifact_finish
from segmenter_fast import SegmenterFast
from campaign_annotation import annotate
def main():
 p=argparse.ArgumentParser();p.add_argument("task",type=int);args=p.parse_args();plan=start("p2_pipeline")
 model=["deepseek","goedel"][args.task//4];shard=args.task%4;base=OUT/"p2_pipeline"
 config=read(base/(model+"-config.json"));reqs={r["trace_id"]:r for r in read(base/(model+"-requests.json"))}
 samples=[];upstream=[]
 for role in ["pilot","evaluation"]:
  mp=base/model/role/"generation/manifest.json";check_manifest(mp);upstream.append(mp)
  with (mp.parent/"samples.jsonl").open(encoding="utf-8") as f:samples.extend(json.loads(line) for line in f)
 assert {s["trace_id"] for s in samples}==set(reqs)
 chosen=[s for s in samples if int(identity(s["problem_id"])[:12],16)%4==shard]
 folder=base/model/("verification-"+str(shard));folder.mkdir(parents=True,exist_ok=True)
 if (folder/"manifest.json").exists():check_manifest(folder/"manifest.json");return
 env=discover();assert digest(env.repl_binary)==read(SEG/"source-manifest.json")["observer_binary_sha256"]
 from transformers import AutoTokenizer
 tok=AutoTokenizer.from_pretrained(config["model_path"],local_files_only=True)
 settings={"max_heartbeats":400000,"whole_timeout_s":180,"step_timeout_s":60}
 context={"source":digest(HERE/"p2_pipeline-source-manifest.json"),"generation_manifests":[digest(p) for p in upstream],"shard":shard}
 repl=None;age=0
 try:
  with Journal(folder/"results.jsonl",context) as journal:
   for sample in chosen:
    tid=sample["trace_id"];request=reqs[tid];request_id=identity([sample["row_sha256"],request])
    if journal.existing(tid,request_id) is not None:continue
    t0=time.monotonic();problem=request["problem"];detail={};result={"trace_id":tid,"problem_id":sample["problem_id"],"role":sample["role"],"model":model,"exercise_group":problem["exercise_group"],"task_family":problem["task_family"],"p2_eligible":False}
    try:
     if repl is None or age>=8:
      if repl is not None:repl.close()
      repl=LeanREPL(env,imports="import Mathlib\nimport Aesop",startup_timeout_s=90,startup_attempts=1,default_timeout_s=180,drain_timeout_s=5);repl.__enter__();age=0
     label=verify_one(repl,sample,problem,settings);age+=1
     result.update(category=label["category"],whole_proof_ok=label.get("whole_proof_ok"),resource_limited=label.get("resource_limited"),axioms=label.get("axioms"))
     detail["label"]=label
     if label["category"] in ["verified","localized_tactic_failure"]:
      item={"trace_id":tid,"model":model,"problem_id":problem["problem_id"],"sample":sample,
       "old_category":label["category"],"old_whole_proof_ok":label["whole_proof_ok"],"header":"set_option maxHeartbeats 400000\n"+problem["directives"]+"\n"+problem["statement"],
       "body":label["body"],"body_start":label["body_start"],"n_old_blocks":len(label["steps"]),"label_origin":str(folder/"results.jsonl"),
       "label_row_sha256":identity(label),"sample_row_sha256":sample["row_sha256"],"source_identity":request_id}
      nr,nd,restart=annotate(item,SegmenterFast(repl,timeout_s=180),tok,300)
      detail.update(item=item,annotation=nr,annotation_detail=nd)
      result.update(p2_eligible=nr["p2_eligible"],annotation_status=nr["status"],localization_status=nr.get("localization_status"),ready_for_activation_extraction=nr.get("ready_for_activation_extraction",False))
      if restart:repl.close();repl=None
     if label["category"] in ["timeout_resource","infrastructure_error"]:
      if repl is not None:repl.close();repl=None
    except Exception as e:
     result.update(category="verification_runtime_error",error=type(e).__name__+": "+str(e))
     if repl is not None:
      try:repl.close()
      except Exception:pass
      repl=None
    blob=folder/(identity(tid)+".json.gz")
    with gzip.open(blob,"wt",encoding="utf-8") as f:json.dump(clean(detail),f,ensure_ascii=False)
    result.update(detail_path=str(blob),detail_sha256=digest(blob),elapsed_s=time.monotonic()-t0)
    journal.append(result,request_id);atomic(folder/"progress.json",{"completed":len(journal.rows),"expected":len(chosen),"updated_unix":time.time(),"last_category":result["category"]})
    if len(journal.rows)%10==0:print("P2 VERIFIED",model,shard,len(journal.rows),len(chosen),flush=True)
   results=list(journal.rows.values())
  metrics={"all_accounted":len(results)==len(chosen),"attempts":len(results),"categories":dict(collections.Counter(r["category"] for r in results)),"p2_eligible":sum(r["p2_eligible"] for r in results)}
  mp=write_once(folder/"metrics.json",metrics)
  artifact_finish(folder,stage="prospective-P2-Lean-and-fine-localization",context=context,
   inputs=[HERE/"p2_pipeline-source-manifest.json",Path(env.repl_binary),*upstream],outputs=[mp,folder/"results.jsonl",folder/"results.identity.json",*[Path(r["detail_path"]) for r in results]],metrics=metrics)
 finally:
  if repl is not None:repl.close()
if __name__=="__main__":main()
