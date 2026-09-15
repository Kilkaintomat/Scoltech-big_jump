"""Validated incremental repair of saved labels; never changes source journals."""
from pathlib import Path
import argparse, collections, importlib.util, json, os, sys, types, time
from onebigjump.e1.artifacts import Journal, digest, finish, identity, read_json, write_once, verify_manifest
from onebigjump.e1.stages import configuration, generation_inputs, rows, pilot_gate
from onebigjump.e1.generation import planned_requests
from onebigjump.e1.parallel_verification import verify_stream
from onebigjump.e1.spans import formal_body
from onebigjump.e1.verification_reuse import rerun_reasons
from onebigjump.e1.smoke import run as smoke

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/speedup-v2"
ROOT=BASE/"runs/lean_reverification_20260913_local"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"

def old_parser(source):
    outputs=read_json(source)["outputs"]
    path=next(Path(p) for p in outputs if p.endswith("/onebigjump/lean/segmentation.py"))
    name="onebigjump.lean._archived_segmentation_"+digest(path)[:12]
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    module=sys.modules[name]
    return types.FunctionType(formal_body.__code__,dict(formal_body.__globals__,segment_proof=module.segment_proof))

def semantic(r):
    keys=["trace_id","category","whole_proof_ok","replay_ok","t_star","unexplained_disagreement",
          "resource_limited","explained_resource_disagreement","budget","stop_reason","axioms",
          "body","replay_body","step_spans","pre_truncation_category"]
    return {**{k:r.get(k) for k in keys},
            "steps":[{k:v for k,v in s.items() if k not in {"elapsed_s","message"}} for s in r.get("steps",[])]}

def acceptance():
    out=HERE/"acceptance"
    if (out/"manifest.json").exists():
        verify_manifest(out/"manifest.json");assert read_json(out/"metrics.json")["passed"];return
    import xml.etree.ElementTree as ET
    xml=HERE/"tests-8466207.xml";tree=ET.parse(xml)
    suites=list(tree.getroot().iter("testsuite"))
    assert suites and all(int(s.get(k,"0"))==0 for s in suites for k in ("failures","errors","skipped"))
    inputs=[SOURCE,Path(__file__),xml,HERE/"diagnostic/manifest.json"]
    for model in ("deepseek","goedel","kimina"):
        root=ROOT/model
        path=root/"checks"/("lean-smoke-"+SOURCE.parent.name)/"manifest.json"
        if not path.exists():smoke(root,SOURCE)
        inputs.append(pilot_gate(root,SOURCE))
    bad=read_json(HERE/"diagnostic/bad-full.json");replays=[]
    for model in ("deepseek","goedel","kimina"):
        root=ROOT/model;samples,manifests=generation_inputs(root,"main");inputs.extend(manifests)
        wanted={b["row"]["trace_id"] for b in bad if b["model"]==model}
        selected=[s for s in samples if s["trace_id"] in wanted]
        problems={p["problem_id"]:p for p in read_json(root/"inputs/problems.json")}
        settings=configuration(root,"main")["lean"]
        for r in verify_stream(selected,problems,settings,2):
            replays.append({"model":model,"result":r})
            print("REGRESSION",model,r["trace_id"],r["category"],r["unexplained_disagreement"],flush=True)
    passed=len(replays)==len(bad) and all(r["result"]["category"]=="verified" and
          not r["result"]["unexplained_disagreement"] for r in replays)
    # Old pilot labels must remain semantically identical before reusing their measurements.
    pilot_checks=[]
    for model in ("deepseek","goedel","kimina"):
        root=ROOT/model;samples,manifests=generation_inputs(root,"pilot");inputs.extend(manifests)
        manifest=root/"pilot/verification/manifest.json";verify_manifest(manifest);inputs.append(manifest)
        previous={r["trace_id"]:r for r in rows(manifest.parent/"labels.jsonl")}
        source=next(Path(p) for p in read_json(manifest)["inputs"] if p.endswith("/source-manifest.json"))
        parser=old_parser(source);problems={p["problem_id"]:p for p in read_json(root/"inputs/problems.json")}
        settings=configuration(root,"pilot")["lean"]
        decisions=[{"trace_id":s["trace_id"],"reasons":rerun_reasons(s,problems[s["problem_id"]],settings,previous[s["trace_id"]],parser)} for s in samples]
        assert set(previous)=={s["trace_id"] for s in samples}
        pilot_checks.append({"model":model,"attempts":len(samples),"changed":sum(bool(d["reasons"]) for d in decisions)})
        passed=passed and not any(d["reasons"] for d in decisions)
    metrics={"passed":passed,"full_test_count":sum(int(s.get("tests","0")) for s in suites),
             "original_disagreements":len(bad),"fresh_verified":sum(r["result"]["category"]=="verified" for r in replays),
             "pilot_compatibility":pilot_checks,"budgets_unchanged":True}
    a=write_once(out/"metrics.json",metrics);b=write_once(out/"replays.json",replays)
    finish(out,stage="saved-label-repair-acceptance",context={"source":digest(SOURCE)},inputs=list(dict.fromkeys(inputs)),outputs=[a,b],metrics=metrics)
    if not passed:raise RuntimeError("repair acceptance failed")
    print("ACCEPTANCE_PASSED",json.dumps(metrics),flush=True)

def repair(model,shard):
    root=ROOT/model;out=HERE/"repaired"/model/("shard-%03d-of-008"%shard)
    if (out/"manifest.json").exists():
        verify_manifest(out/"manifest.json")
        if read_json(out/"manifest.json")["metrics"]["unexplained_disagreements"]:raise RuntimeError("recorded unresolved repair")
        return
    original=root/("main/verification/shard-%03d-of-008/manifest.json"%shard)
    verify_manifest(original)
    meta=read_json(original);oldsource=next(Path(p) for p in meta["inputs"] if p.endswith("/source-manifest.json"))
    verify_manifest(oldsource)
    samples,manifests=generation_inputs(root,"main");config=configuration(root,"main")
    expected={r["trace_id"] for r in planned_requests(root,"main",config,shard,8)}
    selected=[s for s in samples if s["trace_id"] in expected]
    previous={r["trace_id"]:r for r in rows(original.parent/"labels.jsonl")}
    assert set(previous)==expected and len(selected)==len(expected)
    problems={p["problem_id"]:p for p in read_json(root/"inputs/problems.json")}
    parser=old_parser(oldsource);settings=config["lean"];gate=pilot_gate(root,SOURCE)
    decisions=[];byid={s["trace_id"]:s for s in selected}
    for s in selected:
        r=previous[s["trace_id"]]
        assert r["request_sha256"]==identity(s)
        reasons=([] if digest(oldsource)==digest(SOURCE) and not r["unexplained_disagreement"] and r["category"]!="infrastructure_error"
                 else rerun_reasons(s,problems[s["problem_id"]],settings,r,parser))
        decisions.append({"trace_id":s["trace_id"],"rerun_reasons":reasons,"original_row_identity":identity(r)})
    context={"source":digest(SOURCE),"original":digest(original),"config":digest(root/"main/protocol.json"),"execution":{"workers":2}}
    with Journal(out/"labels.jsonl",context) as journal:
        todo=[]
        for d in decisions:
            s=byid[d["trace_id"]]
            if journal.existing(s["trace_id"],identity(s)) is not None:continue
            if d["rerun_reasons"]:todo.append(s)
            else:
                r=dict(previous[s["trace_id"]])
                r["verification_origin"]={"mode":"reused_unchanged_verifier_inputs","manifest":str(original),"manifest_sha256":digest(original),"row_identity":d["original_row_identity"]}
                journal.append(r,identity(s))
        for r in verify_stream(todo,problems,settings,2):
            s=byid[r["trace_id"]]
            r["verification_origin"]={"mode":"fresh_kernel_repair","original_manifest":str(original),"original_manifest_sha256":digest(original)}
            journal.append(r,identity(s))
            print("REPAIRED",model,shard,r["trace_id"],r["category"],flush=True)
        values=list(journal.rows.values())
    assert {r["trace_id"] for r in values}==expected
    metrics={"attempts":len(values),"fresh_selected":sum(bool(d["rerun_reasons"]) for d in decisions),
             "reused":sum(not d["rerun_reasons"] for d in decisions),
             "categories":dict(collections.Counter(r["category"] for r in values)),
             "unexplained_disagreements":sum(r["unexplained_disagreement"] for r in values),
             "resource_limited":sum(r["resource_limited"] for r in values),
             "explained_resource_disagreements":sum(r["explained_resource_disagreement"] for r in values)}
    decision_file=write_once(out/"decisions.json",decisions);metric_file=write_once(out/"metrics.json",metrics)
    finish(out,stage="verification-repair",context=context,inputs=[SOURCE,Path(__file__),HERE/"acceptance/manifest.json",original,gate,root/"main/protocol.json",*manifests],
           outputs=[out/"labels.jsonl",out/"labels.identity.json",decision_file,metric_file],metrics=metrics)
    if metrics["unexplained_disagreements"]:raise RuntimeError("unresolved whole/replay disagreement")
    print("SHARD_ACCEPTED",model,shard,json.dumps(metrics),flush=True)

def merge(model):
    root=ROOT/model;out=root/"main/verification"
    paths=[HERE/"repaired"/model/("shard-%03d-of-008/manifest.json"%i) for i in range(8)]
    if not all(p.exists() for p in paths):return
    if (out/"manifest.json").exists():verify_manifest(out/"manifest.json");return
    config=configuration(root,"main");samples,gen=generation_inputs(root,"main")
    expected={s["trace_id"] for s in samples};values=[]
    for p in paths:
        verify_manifest(p);assert read_json(p)["metrics"]["unexplained_disagreements"]==0
        values.extend(rows(p.parent/"labels.jsonl"))
    assert len(values)==len(expected) and {r["trace_id"] for r in values}==expected
    context={"source":digest(SOURCE),"children":{str(p):digest(p) for p in paths},"config":digest(root/"main/protocol.json"),"repair_acceptance":digest(HERE/"acceptance/manifest.json")}
    with Journal(out/"labels.jsonl",context) as journal:
        for r in values:
            if journal.existing(r["trace_id"],r["request_sha256"]) is None:journal.append(r,r["request_sha256"])
    metrics={"attempts":len(values),"categories":dict(collections.Counter(r["category"] for r in values)),
             "unexplained_disagreements":0,"all_planned_attempts_accounted":True,
             "fresh_repaired":sum(read_json(p)["metrics"]["fresh_selected"] for p in paths)}
    a=write_once(out/"metrics.json",metrics)
    finish(out,stage="gather-verification-repaired",context=context,inputs=[SOURCE,Path(__file__),HERE/"acceptance/manifest.json",root/"main/protocol.json",*paths,*gen],outputs=[out/"labels.jsonl",out/"labels.identity.json",a],metrics=metrics)
    print("MODEL_MERGED",model,len(values),flush=True)

def main():
    acceptance()
    for shard in range(8):
        for model in ("deepseek","goedel","kimina"):
            original=ROOT/model/("main/verification/shard-%03d-of-008/manifest.json"%shard)
            if original.exists():repair(model,shard)
    for model in ("deepseek","goedel","kimina"):merge(model)

if __name__=="__main__":main()
