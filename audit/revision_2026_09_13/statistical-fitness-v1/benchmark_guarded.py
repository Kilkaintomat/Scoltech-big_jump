from pathlib import Path
import os,time,json,threading
import psutil
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,identity,verify_manifest
from onebigjump.e1.stages import generation_inputs,rows
from onebigjump.e1.parallel_verification import verify_stream

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/statistical-fitness-v1"
OUT=HERE/"benchmark-guarded"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
protocol=read_json(HERE/"guarded-protocol.json")
inputs=[SOURCE,HERE/"protocol.json",Path(__file__)]
records=[];measurements=[];comparisons=[];chosen=[]
process=psutil.Process()

def semantic(r):
    fields=["trace_id","category","whole_proof_ok","replay_ok","t_star","unexplained_disagreement",
            "resource_limited","explained_resource_disagreement","budget","stop_reason",
            "axioms","body","replay_body","step_spans","pre_truncation_category"]
    return {**{k:r.get(k) for k in fields},
       "steps":[{k:v for k,v in s.items() if k not in {"elapsed_s","message"}} for s in r.get("steps",[])]}

for model in ["deepseek","goedel","kimina"]:
    root=BASE/"runs/lean_reverification_20260913_local"/model
    config=read_json(root/"main/protocol.json")
    samples,manifests=generation_inputs(root,"main")
    inputs.extend(manifests+[root/"main/protocol.json",root/"inputs/problems.json"])
    archived={}
    for shard in [0,1]:
        manifest=root/("main/verification/shard-%03d-of-008/manifest.json"%shard)
        verify_manifest(manifest);inputs.append(manifest)
        archived.update({r["trace_id"]:r for r in rows(manifest.parent/"labels.jsonl")})
    selected=sorted([s for s in samples if s["trace_id"] in archived],
                    key=lambda s:identity([protocol["seed"],model,s["trace_id"]]))[:16]
    chosen.extend([{"model":model,"trace_id":s["trace_id"],"request_sha256":identity(s)} for s in selected])
    problems={p["problem_id"]:p for p in read_json(root/"inputs/problems.json")}
    result={}
    for workers in protocol["benchmark"]["workers"]:
        stop=threading.Event();peak=[0]
        def monitor():
            while not stop.wait(.10):
                resident=0
                for p in [process,*process.children(recursive=True)]:
                    try:resident+=p.memory_info().rss
                    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                peak[0]=max(peak[0],resident)
        watch=threading.Thread(target=monitor);watch.start()
        started=time.monotonic()
        try:
            values=list(verify_stream(selected,problems,config["lean"],workers))
        finally:
            elapsed=time.monotonic()-started;stop.set();watch.join()
        result[workers]={r["trace_id"]:r for r in values}
        assert len(values)==len(selected)==len(result[workers])
        measurements.append({"model":model,"workers":workers,"seconds":elapsed,"attempts":len(values),
                            "peak_total_process_rss_bytes":peak[0],
                            "resource_limited":sum(r["resource_limited"] for r in values),
                            "unexplained_disagreements":sum(r["unexplained_disagreement"] for r in values)})
        records.extend([{"model":model,"workers":workers,"result":r} for r in values])
        print("MEASURED",model,workers,elapsed,flush=True)
    for sample in selected:
        rid=sample["trace_id"]
        comparisons.append({"model":model,"trace_id":rid,
            "serial_parallel_equal":semantic(result[1][rid])==semantic(result[2][rid]),
            "serial_archive_equal":semantic(result[1][rid])==semantic(archived[rid])})
serial=sum(r["seconds"] for r in measurements if r["workers"]==1)
parallel=sum(r["seconds"] for r in measurements if r["workers"]==2)
speedup=serial/parallel
equal=all(r["serial_parallel_equal"] and r["serial_archive_equal"] for r in comparisons)
passed=equal and speedup>=protocol["benchmark"]["minimum_speedup"]
metrics={"measurements":measurements,"serial_seconds":serial,"parallel_seconds":parallel,"speedup":speedup,
 "sampled_traces":len(chosen),"semantic_equal":sum(r["serial_parallel_equal"] for r in comparisons),
 "archived_equal":sum(r["serial_archive_equal"] for r in comparisons),"passed":passed,
 "scope":"one fixed sample and one timing round; unchanged verifier; excludes node staging; no general speed guarantee",
 "settings_unchanged":True,"source_segmentation_fix":False,"parallel_workers":2}
a=write_once(OUT/"metrics.json",metrics)
b=write_once(OUT/"comparisons.json",comparisons)
c=write_once(OUT/"replays.json",records)
d=write_once(OUT/"selection.json",chosen)
finish(OUT,stage="verification-concurrency-benchmark",context={"source":digest(SOURCE)},
       inputs=list(dict.fromkeys(inputs)),outputs=[a,b,c,d],metrics=metrics)
print("BENCHMARK_COMPLETE",json.dumps(metrics),flush=True)
if not passed:raise RuntimeError("benchmark does not authorize activation")
