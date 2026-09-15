import argparse,collections,gzip,re,subprocess,time
from stage_support import *
from artifact_bridge import finish_artifact
from onebigjump.e1.artifacts import Journal,identity,write_once
from onebigjump.lean import discover
from onebigjump.e1.spans import formal_body,SourceExclusion
from onebigjump.e1.verification import trusted_prefix,theorem_name,ALLOWED_AXIOMS
def main():
 p=argparse.ArgumentParser();p.add_argument("model");args=p.parse_args();plan=start("audit_cli");model=args.model
 selection=OUT/"lean_audit"/(model+"-selected.json");chosen=read(selection);upstream=OUT/"lean_audit"/model/"manifest.json";check_manifest(upstream)
 dest=OUT/"audit_cli"/model;dest.mkdir(parents=True,exist_ok=True);env=discover().require();context={"source":digest(HERE/"audit_cli-source-manifest.json"),"selection":digest(selection),"repl_audit":digest(upstream)}
 with Journal(dest/"results.jsonl",context) as journal:
  for request in chosen:
   item=request["item"];tid=item["trace_id"];sample=item["sample"];problem=request["problem"]
   if journal.existing(tid,identity(request)) is not None:continue
   result={"trace_id":tid,"problem_id":problem["problem_id"],"model":model,"stratum":request["stratum"],"old_category":request["old_label"]["category"]};detail={};starttime=time.monotonic()
   try:
    parsed=formal_body(sample["completion"],problem["statement"],trusted_prefix(problem,400000))
    name=theorem_name(problem);source=trusted_prefix(problem,400000)+"\n"+problem["statement"]+parsed["body"]+"\n#print axioms "+name+"\n"
    path=dest/(identity(tid)+".lean");path.write_text(source,encoding="utf-8");result.update(source_path=str(path),source_sha256=digest(path))
    t=subprocess.run([env.lake or "lake","env","lean",str(path)],cwd=str(env.project),env=env.env_vars(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace",timeout=plan["timeout_s"])
    detail={"stdout":t.stdout,"stderr":t.stderr,"returncode":t.returncode}
    deps=re.findall(r"depends on axioms:\s*\[(.*?)\]",t.stdout,re.S);no_deps="does not depend on any axioms" in t.stdout
    axioms=[v.strip() for d in deps for v in d.split(",") if v.strip()]
    okay=t.returncode==0 and bool(deps or no_deps) and all(a in ALLOWED_AXIOMS for a in axioms)
    result.update(status="standalone_checked",returncode=t.returncode,standalone_certified=okay,axioms=axioms,axiom_audit_present=bool(deps or no_deps),
     matches_verified_category=(okay==(result["old_category"]=="verified")) if sample["finish_reason"]!="length" else None,
     truncated_but_certificate_valid=sample["finish_reason"]=="length" and okay)
   except SourceExclusion as e:result.update(status="source_excluded",reason=e.category,error=str(e))
   except subprocess.TimeoutExpired as e:
    result.update(status="standalone_resource_timeout",error=str(e));detail={"stdout":str(e.stdout),"stderr":str(e.stderr)}
   except Exception as e:result.update(status="standalone_runtime_error",error=type(e).__name__+": "+str(e))
   blob=dest/(identity(tid)+".json.gz")
   with gzip.open(blob,"wt",encoding="utf-8") as f:json.dump(detail,f,ensure_ascii=False)
   result.update(detail_path=str(blob),detail_sha256=digest(blob),elapsed_s=time.monotonic()-starttime)
   journal.append(result,identity(request));atomic(dest/"progress.json",{"completed":len(journal.rows),"expected":len(chosen),"updated_unix":time.time(),"status":result["status"]})
   print("STANDALONE",model,len(journal.rows),len(chosen),result["status"],flush=True)
  rows=list(journal.rows.values())
 metrics={"expected":len(chosen),"completed":len(rows),"statuses":dict(collections.Counter(r["status"] for r in rows)),
  "original_verified":sum(r["old_category"]=="verified" for r in rows),"verified_independently_certified":sum(r["old_category"]=="verified" and r.get("standalone_certified",False) for r in rows),
  "nontruncated_category_disagreements":sum(r.get("matches_verified_category") is False for r in rows),
  "truncated_but_certificate_valid":sum(r.get("truncated_but_certificate_valid",False) for r in rows),
  "scope":"Separate standalone compiler path using the same trusted statement and pinned Lean/Mathlib; complements REPL repeatability, does not establish correctness of informal formalization."}
 mp=write_once(dest/"metrics.json",metrics)
 finish_artifact(dest,stage="stratified-independent-Lean-CLI-audit",context=context,inputs=[selection,upstream,HERE/"audit_cli-source-manifest.json"],
  outputs=[mp,dest/"results.jsonl",dest/"results.identity.json",*[Path(r["detail_path"]) for r in rows],*[Path(r["source_path"]) for r in rows if r.get("source_path")]],metrics=metrics)
if __name__=="__main__":main()
