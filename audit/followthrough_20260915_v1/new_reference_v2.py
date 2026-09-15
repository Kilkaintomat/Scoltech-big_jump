import argparse,collections,gzip,re,time
from stage_support import *
from onebigjump.lean import LeanREPL,discover
from onebigjump.lean.verifier import _errors,_is_resource_error
from onebigjump.e1.verification import trusted_prefix,theorem_name
from onebigjump.e1.spans import formal_body,mask_comments,SourceExclusion
from onebigjump.e1.artifacts import Journal,identity,write_once
from artifact_bridge import finish_artifact as artifact_finish
def main():
 parser=argparse.ArgumentParser();parser.add_argument("shard",type=int);parser.add_argument("--shards",type=int,default=4);args=parser.parse_args()
 plan=start("new_reference_v2");check_manifest(OUT/"new_tasks/manifest.json")
 candidates=OUT/"new_tasks/candidates.json";allrows=read(candidates)
 rows=[r for r in allrows if int(r["source_index"])%args.shards==args.shard]
 dest=OUT/"new_tasks"/("reference-v2-shard-"+str(args.shard));dest.mkdir(exist_ok=True)
 env=discover();repl=None;age=0;context={"plan":digest(HERE/"new_reference_v2-plan.json"),"source":digest(HERE/"new_reference_v2-source-manifest.json"),"candidates":digest(candidates),"shard":args.shard,"shards":args.shards}
 try:
  with Journal(dest/"results.jsonl",context) as journal:
   for problem in rows:
    tid="proofnet-"+str(problem["source_index"])+":"+problem["problem_id"]
    if journal.existing(tid,identity(problem)) is not None:continue
    result={"trace_id":tid,"problem_id":problem["problem_id"],"exercise_group":problem["exercise_group"],"source_index":problem["source_index"]}
    t0=time.monotonic();detail={}
    try:
     reference=Path(problem["reference_path"]);assert digest(reference)==problem["reference_sha256"]
     code=reference.read_text(encoding="utf-8");live=mask_comments(code)
     declaration=theorem_name(problem)
     declarations=re.findall(r"(?m)^\s*(?:theorem|lemma)\s+([^\s:(]+)",live)
     related=[n for n in declarations if n==declaration or n.startswith(declaration+"_corrected")]
     if not related:raise SourceExclusion("reference_target_missing","no original or corrected target declaration")
     related=sorted(set(related),key=lambda n:(not n.startswith(declaration+"_corrected"),n))
     target="obj_reference_"+str(problem["source_index"])
     target_statement=re.sub(r"^(\s*(?:theorem|lemma)\s+)([^\s:(]+)",lambda m:m.group(1)+target,problem["statement"],count=1)
     # The appended theorem has exactly the JSON statement; all candidate lemmas are kernel checked.
     proof="\n  first\n"+"\n".join("  | solve\n    | exact "+name+"\n    | apply "+name+" <;> assumption" for name in related)
     source_without_imports=re.sub(r"(?m)^\s*import\s+[^\n]+","",code)
     checked_source=source_without_imports+"\n"+problem["directives"]+"\n"+target_statement+proof+"\n#print axioms "+target
     if repl is None or age>=10:
      if repl is not None:repl.close()
      repl=LeanREPL(env,imports="import Mathlib\nimport Aesop",startup_timeout_s=90,startup_attempts=1,default_timeout_s=plan["reference_timeout_s"],drain_timeout_s=5)
      repl.__enter__();age=0
     absent=repl.command("#check "+declaration);detail["base_absence_check"]=absent
     if not _errors(absent):raise SourceExclusion("answer_already_imported","target theorem is already available")
     source="set_option maxHeartbeats "+str(plan["reference_heartbeats"])+"\n"+checked_source
     reply=repl.command(source);age+=1;detail["reply"]=reply
     errors=_errors(reply);result["errors"]=errors
     axmsgs=[str(m.get("data","")) for m in reply.get("messages",[]) if "axioms" in str(m.get("data",""))]
     axioms=[]
     for msg in axmsgs:
      mat=re.search(r"depends on axioms:\s*\[(.*?)\]",msg,re.S)
      if mat:axioms.extend(x.strip() for x in mat.group(1).split(",") if x.strip())
     result["axioms"]=axioms;result["axiom_messages"]=axmsgs
     if errors:result["category"]="reference_resource" if _is_resource_error(errors) else "reference_incompatible"
     elif not axmsgs:result["category"]="reference_axiom_audit_missing"
     elif any(a not in plan["allowed_axioms"] for a in axioms):result["category"]="reference_unapproved_axiom"
     else:result["category"]="reference_verified"
     if result["category"]=="reference_resource":repl.close();repl=None
    except SourceExclusion as exc:
     result.update(category=exc.category,error=str(exc))
    except Exception as exc:
     result.update(category="reference_runtime_error",error=type(exc).__name__+": "+str(exc))
     if repl is not None:
      try:repl.close()
      except Exception:pass
      repl=None
    blob=dest/(identity(tid)+".json.gz")
    with gzip.open(blob,"wt",encoding="utf-8") as f:json.dump(clean(detail),f,ensure_ascii=False)
    result.update(detail_path=str(blob),detail_sha256=digest(blob),elapsed_s=time.monotonic()-t0)
    journal.append(result,identity(problem))
    atomic(dest/"progress.json",{"completed":len(journal.rows),"expected":len(rows),"last_category":result["category"]})
    print("REFERENCE",args.shard,len(journal.rows),len(rows),tid,result["category"],flush=True)
   results=list(journal.rows.values())
  metrics={"completed":len(results),"expected":len(rows),"categories":dict(collections.Counter(r["category"] for r in results))}
  mp=write_once(dest/"metrics.json",metrics)
  artifact_finish(dest,stage="corrected-proofnet-reference-verification",context=context,
   inputs=[candidates,HERE/"new_reference_v2-source-manifest.json",Path(env.repl_binary)],outputs=[mp,dest/"results.jsonl",dest/"results.identity.json",*[Path(r["detail_path"]) for r in results]],metrics=metrics)
 finally:
  if repl is not None:repl.close()
if __name__=="__main__":main()
