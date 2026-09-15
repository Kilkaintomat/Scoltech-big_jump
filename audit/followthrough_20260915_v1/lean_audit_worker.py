import argparse,collections,gzip,time
from stage_support import *
from onebigjump.lean import LeanREPL,discover
from onebigjump.e1.verification import verify_one
from onebigjump.e1.artifacts import Journal,identity,finish as artifact_finish,write_once
from segmenter_fast import SegmenterFast
from campaign_annotation import annotate
def main():
 parser=argparse.ArgumentParser();parser.add_argument("model");args=parser.parse_args();model=args.model
 plan=start("lean_audit");check_manifest(OUT/"lean_audit/manifest.json")
 selection=OUT/"lean_audit"/(model+"-selected.json");selected=read(selection)
 env=discover();assert digest(env.repl_binary)==read(SEG/"source-manifest.json")["observer_binary_sha256"]
 from transformers import AutoTokenizer
 protocol=read(STATES/"protocols"/(model+".json"));tok=AutoTokenizer.from_pretrained(protocol["model_path"],local_files_only=True)
 dest=OUT/"lean_audit"/model;dest.mkdir(exist_ok=True);outputs=[];repl=None;age=0
 context={"selection":digest(selection),"plan":digest(HERE/"lean_audit-plan.json"),"source":digest(HERE/"lean_audit-source-manifest.json")}
 try:
  with Journal(dest/"results.jsonl",context) as journal:
   for request in selected:
    item=request["item"];tid=item["trace_id"]
    if journal.existing(tid,identity(request)) is not None:continue
    began=time.monotonic();old=request["old_label"];ann=request["old_annotation"]
    result={"trace_id":tid,"problem_id":item["problem_id"],"stratum":request["stratum"],"old_category":old["category"],
     "model":model,"inclusion_probability":request["selection_probability"],"old_fine_star":ann.get("fine_star")}
    try:
     if repl is None or age>=8:
      if repl is not None:repl.close()
      repl=LeanREPL(env,imports="import Mathlib\nimport Aesop",startup_attempts=1,startup_timeout_s=90,default_timeout_s=180,drain_timeout_s=5)
      repl.__enter__();age=0
     sample=dict(item["sample"]);sample.setdefault("attempt_index",old["attempt_index"])
     settings={k:plan[k] for k in ["max_heartbeats","step_timeout_s","whole_timeout_s"]}
     fresh=verify_one(repl,sample,request["problem"],settings);age+=1
     result.update(new_category=fresh["category"],whole_proof_ok=fresh.get("whole_proof_ok"),
      axiom_dependencies=fresh.get("axioms"),category_agrees=fresh["category"]==old["category"],
      resource_limited=fresh.get("resource_limited",False),unexplained_disagreement=fresh.get("unexplained_disagreement",False),
      error=fresh.get("error"),pre_truncation_category=fresh.get("pre_truncation_category"))
     detail={"new_authoritative_verification":fresh}
     if not item.get("exclusion") and ann.get("p2_eligible"):
      segmenter=SegmenterFast(repl,timeout_s=plan["whole_timeout_s"]);nr,nd,restart=annotate(item,segmenter,tok,plan["replay_budget_s"])
      detail["new_fine_annotation"]=nr;detail["new_fine_detail"]=nd
      obs=nd.get("export",{}).get("observation_rows",[]);ats=[i for i,o in enumerate(obs) if o["trace_label"]=="at"]
      result["new_fine_star"]=ats[0] if len(ats)==1 else None
      result["fine_reproduced"]=bool(nr.get("p2_eligible") and result["new_fine_star"]==ann["fine_star"])
      result["fine_status"]=nr.get("localization_status",nr["status"])
      if restart:repl.close();repl=None
     if fresh["category"] in ["timeout_resource","infrastructure_error"]:
      if repl is not None:repl.close();repl=None
     blob=dest/(hashlib.sha256(tid.encode()).hexdigest()+".json.gz")
     with gzip.open(blob,"wt",encoding="utf-8") as f:json.dump(clean(detail),f,ensure_ascii=False)
     result.update(detail_path=str(blob),detail_sha256=digest(blob))
    except Exception as exc:
     result.update(new_category="audit_runtime_error",category_agrees=None,error=type(exc).__name__+": "+str(exc))
     if repl is not None:
      try:repl.close()
      except Exception:pass
      repl=None
    result["elapsed_s"]=time.monotonic()-began;journal.append(result,identity(request))
    atomic(dest/"progress.json",{"completed":len(journal.rows),"expected":len(selected),"last":tid,"category":result["new_category"]})
    print("AUDITED",model,len(journal.rows),len(selected),result["new_category"],flush=True)
   rows=list(journal.rows.values())
  metrics={"model":model,"expected":len(selected),"completed":len(rows),"all_accounted":len(rows)==len(selected),
   "category_agreement":sum(r.get("category_agrees") is True for r in rows),"category_disagreement":sum(r.get("category_agrees") is False for r in rows),
   "runtime_errors":sum(r["new_category"]=="audit_runtime_error" for r in rows),"strata":{}}
  for st in plan["strata"]:
   subset=[r for r in rows if r["stratum"]==st]
   metrics["strata"][st]={"n":len(subset),"tasks":len({r["problem_id"] for r in subset}),
    "category_agreement":sum(r.get("category_agrees") is True for r in subset),"fresh_categories":dict(collections.Counter(r["new_category"] for r in subset)),
    "fine_reproduced":sum(r.get("fine_reproduced") is True for r in subset),"fine_not_reproduced":sum(r.get("fine_reproduced") is False for r in subset)}
  p=write_once(dest/"metrics.json",metrics)
  artifact_finish(dest,stage="random-stratified-lean-label-audit",context=context,
   inputs=[selection,HERE/"lean_audit-source-manifest.json",Path(env.repl_binary)],outputs=[p,dest/"results.jsonl",dest/"results.identity.json",*[Path(r["detail_path"]) for r in rows if r.get("detail_path")]],metrics=metrics)
 finally:
  if repl is not None:repl.close()
 print("AUDIT MODEL COMPLETE",json.dumps(metrics),flush=True)
if __name__=="__main__":main()
