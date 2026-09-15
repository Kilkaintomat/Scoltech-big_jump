from pathlib import Path
from datetime import datetime,timezone
import os
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,verify_manifest
from onebigjump.e1.stages import generation_inputs,rows
from onebigjump.e1.verification import verify_one
from onebigjump.lean import LeanREPL,discover
import onebigjump.lean.segmentation as segmentation
BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
AUDIT=BASE/"audit/revision_2026_09_13"
OUT=AUDIT/"segmentation-outdent-v1/result"
HERE=Path(__file__).parent
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
root=BASE/"runs/lean_reverification_20260913_local/kimina"
failed=root/"main/verification/shard-001-of-008"
verify_manifest(failed/"manifest.json")
bad=[r for r in rows(failed/"labels.jsonl") if r["unexplained_disagreement"]]
assert len(bad)==1
target=bad[0]["trace_id"]
samples,manifests=generation_inputs(root,"main")
sample=next(r for r in samples if r["trace_id"]==target)
protocol=root/"main/protocol.json";settings=read_json(protocol)["lean"]
problem=next(p for p in read_json(root/"inputs/problems.json") if p["problem_id"]==sample["problem_id"])
old_function=segmentation._finalise
candidate_namespace={"Segment":segmentation.Segment}
exec(compile((HERE/"candidate.py").read_text(),str(HERE/"candidate.py"),"exec"),candidate_namespace)
new_function=candidate_namespace["_finalise"]
results=[]
for method,function in [("original",old_function),("candidate",new_function)]:
    segmentation._finalise=function
    with LeanREPL(discover(settings["workspace"]),imports="import Mathlib\nimport Aesop",
                  startup_timeout_s=settings["startup_timeout_s"]) as repl:
        r=verify_one(repl,sample,problem,settings)
        results.append({"method":method,"result":r})
        print("FRESH_REPLAY",method,r["category"],r["whole_proof_ok"],r["replay_ok"],flush=True)
segmentation._finalise=new_function
token_tests=[]
for proof in ["  skip\n<;> skip","  skip\n <;> skip","  skip\n  <;> skip","  skip\n; skip",
              "  first\n| skip","  (skip\n)","  skip\n<;>\n  skip",bad[0]["replay_body"]]:
    segments=segmentation.segment_proof(proof)
    before="".join(segmentation.strip_comments(proof).split())
    after="".join("".join(s.text.split()) for s in segments)
    token_tests.append({"source":proof,"segments":[s.text for s in segments],"tokens_preserved":before==after})
# Existing independent saved-proof regression under the isolated candidate.
previous=read_json(AUDIT/"8466032-preflight/metrics.json")
expected={r["trace_id"]:r["category"] for r in previous["cases_summary"]}
groot=BASE/"runs/lean_reverification_20260912/goedel"
gsamples,gmanifests=generation_inputs(groot,"main")
gproblems={p["problem_id"]:p for p in read_json(groot/"inputs/problems.json")}
gsettings=read_json(groot/"main/protocol.json")["lean"]
regression=[]
with LeanREPL(discover(gsettings["workspace"]),imports="import Mathlib\nimport Aesop",
              startup_timeout_s=gsettings["startup_timeout_s"]) as repl:
    for s in gsamples:
        if s["trace_id"] not in expected:continue
        r=verify_one(repl,s,gproblems[s["problem_id"]],gsettings)
        regression.append(r)
        print("REGRESSION",r["trace_id"],r["category"],flush=True)
segmentation._finalise=old_function
passed=(results[0]["result"]["whole_proof_ok"] is True and results[0]["result"]["replay_ok"] is False
        and results[1]["result"]["category"]=="verified"
        and all(t["tokens_preserved"] for t in token_tests)
        and len(regression)==len(expected)
        and all(not r["unexplained_disagreement"] and r["category"]==expected[r["trace_id"]] for r in regression))
metrics={"created_utc":datetime.now(timezone.utc).isoformat(),"trace_id":target,
 "failed_job":"8466099","failed_shard":"kimina/main-verify-1",
 "archived_shard_attempts":read_json(failed/"manifest.json")["metrics"]["attempts"],
 "archived_disagreements":len(bad),"candidate_passed_bounded_review":passed,
 "main_source_changed":False,"main_labels_changed":False,"production_promoted":False,
 "fresh_summary":[{"method":r["method"],**{k:r["result"][k] for k in ["whole_proof_ok","replay_ok","category","t_star","unexplained_disagreement"]}} for r in results],
 "token_preservation_cases":len(token_tests),"token_preservation_passed":sum(t["tokens_preserved"] for t in token_tests),
 "previous_regression_cases":len(regression),
 "previous_regression_matches":sum(r["category"]==expected[r["trace_id"]] and not r["unexplained_disagreement"] for r in regression),
 "diagnosis":"_finalise slices seg.indent characters unconditionally; outdented continuation loses non-whitespace operator characters. Candidate removes at most existing leading whitespace.",
 "scope":"isolated monkeypatch with saved tokens; not full-suite acceptance or permission to bypass the failed gate"}
a=write_once(OUT/"metrics.json",metrics)
b=write_once(OUT/"replay-results.json",results)
c=write_once(OUT/"regression-results.json",regression)
e=write_once(OUT/"token-preservation.json",token_tests)
inputs=[SOURCE,Path(__file__),HERE/"candidate.py",failed/"manifest.json",protocol,root/"inputs/problems.json",
        AUDIT/"8466032-preflight/manifest.json",groot/"main/protocol.json",groot/"inputs/problems.json",
        Path(os.environ["E1_REPL_RUNTIME_MANIFEST"]),Path(os.environ["E1_ELAN_RUNTIME_MANIFEST"]),*manifests,*gmanifests]
finish(OUT,stage="isolated-outdent-segmentation-reproduction",context={"source":digest(SOURCE)},
       inputs=inputs,outputs=[a,b,c,e],metrics=metrics)
print("BOUNDED_REVIEW_COMPLETE",passed,flush=True)
