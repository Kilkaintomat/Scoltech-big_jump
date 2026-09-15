import argparse,collections,re,zipfile
from stage_support import *
from onebigjump.e1.artifacts import identity
from onebigjump.e1.spans import mask_comments
def stem(name):
 name=re.sub(r"^[A-Za-z][A-Za-z-]*_(?=exercise|problem|theorem)","",name)
 name=re.sub(r"(?<=\d)[a-z]$","",name)
 name=re.sub(r"_[a-z]$","",name)
 return name
def statement_key(statement):
 s=mask_comments(statement or "",mask_strings=False)
 s=re.sub(r"^\s*(theorem|lemma)\s+\S+","theorem TARGET",s)
 s=re.sub(r":=\s*by\s*(sorry)?\s*$","",s)
 return re.sub(r"\s+","",s)
def collect(plan):
 folder=OUT/"new_tasks";folder.mkdir(parents=True,exist_ok=True);ext=ROOT/plan["source_dir"]
 source=ext/"data/proofnet-verified.jsonl";archive=ext/"data/proofnet-verified_gt.zip"
 paths=set()
 for n in range(1,5):
  paths.update((ROOT/"runs").glob("/".join(["*"]*n+["generation","*","samples.jsonl"])))
 paths.add(ROOT/"data/raw/prover-sampling/samples.jsonl")
 prior_names=set();prior_keys=set();scanned=[];seen=set();statement_inputs=[]
 for path in sorted(paths):
  if not path.is_file() or "followthrough_20260915_v1" in str(path):continue
  st=path.stat();key=(st.st_dev,st.st_ino)
  if key in seen:continue
  seen.add(key);count=0
  with path.open(encoding="utf-8") as f:
   for line in f:
    row=json.loads(line);prob=row.get("problem",{})
    if not isinstance(prob,dict):prob={}
    name=row.get("problem_id") or prob.get("problem_id")
    if name:prior_names.add(str(name));prior_names.add(stem(str(name)))
    text=prob.get("statement") or prob.get("formal_statement") or row.get("statement")
    if text:prior_keys.add(statement_key(text))
    count+=1
  scanned.append({"path":str(path),"sha256":digest(path),"rows":count})
 # Add statement identities for observed problem IDs from frozen input populations.
 for n in range(1,4):
  for path in (ROOT/"runs").glob("/".join(["*"]*n+["inputs","problems.json"])):
   if "followthrough_20260915_v1" in str(path):continue
   data=read(path)
   if not isinstance(data,list):continue
   statement_inputs.append(path)
   for prob in data:
    if prob.get("problem_id") in prior_names:
     s=prob.get("statement") or prob.get("formal_statement")
     if s:prior_keys.add(statement_key(s))
 candidates=[];excluded=[];keys=set();refs=folder/"references";refs.mkdir(exist_ok=True)
 with source.open(encoding="utf-8") as f:records=[json.loads(line) for line in f]
 with zipfile.ZipFile(archive) as z:
  for r in records:
   stmt=r["formal_stmt"];name=r["name"];reason=None
   prefix=re.sub(r"\s+sorry\s*$","",stmt).rstrip()
   directives="\n".join(l for l in r["header"].splitlines() if not l.strip().startswith("import "))
   if r.get("helper"):directives+="\n"+r["helper"]
   key=statement_key(stmt)
   if name in prior_names or stem(name) in prior_names:reason="previously_generated_exercise_family"
   elif key in prior_keys:reason="previous_statement_identity"
   elif key in keys:reason="duplicate_statement"
   elif not prefix.endswith("by"):reason="unsupported_statement_shape"
   elif re.search(r"\b(sorry|admit|axiom)\b",mask_comments(directives,mask_strings=True)):reason="untrusted_helper_hole_or_axiom"
   keys.add(key)
   if reason:excluded.append({"name":name,"reason":reason});continue
   refname=f'proofnet_verified_gt/proofnet-{r["index"]}.lean';ref=refs/(str(r["index"])+".lean");ref.write_bytes(z.read(refname))
   group=str(r["textbook"])+":"+stem(name)
   candidates.append({"problem_id":name,"statement":prefix,"directives":directives,"header":r["header"],
    "benchmark":"proofnet_verified","task_family":r["textbook"],"exercise_group":group,"source_index":r["index"],
    "source_commit":plan["source_commit"],"reference_path":str(ref),"reference_sha256":digest(ref),
    "reference_scope":"verification only; proof and informal proof must never enter model prompt","statement_key":key})
 atomic(folder/"candidates.json",candidates);atomic(folder/"excluded.json",excluded);atomic(folder/"prior-generation-scan.json",scanned)
 finish("new_tasks",{"candidate_problems":len(candidates),"candidate_exercise_groups":len({r["exercise_group"] for r in candidates}),
  "source_problems":len(records),"excluded":dict(collections.Counter(x["reason"] for x in excluded)),
  "prior_generation_files":len(scanned),"prior_generation_rows":sum(x["rows"] for x in scanned),
  "reference_proofs_not_in_generation_records":True,"generation_calls":0},
  [source,archive,*statement_inputs,*[Path(x["path"]) for x in scanned]],[folder/"candidates.json",folder/"excluded.json",folder/"prior-generation-scan.json",*[Path(r["reference_path"]) for r in candidates]])
 print("CANDIDATES READY",len(candidates),flush=True)
def main():
 plan=start("new_tasks");collect(plan)
if __name__=="__main__":main()
