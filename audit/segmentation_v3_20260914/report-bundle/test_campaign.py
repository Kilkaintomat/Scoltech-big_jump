from pathlib import Path
import collections,hashlib,json,os,subprocess,sys
from onebigjump.e1.artifacts import canonical,digest,identity
from campaign_worker import read,atomic_json,load_artifact
O=Path(__file__).parent;ROOT=O.parents[1];T=O/"batch-pilot"
(T/"inputs").mkdir(parents=True,exist_ok=True)
labels=read(O/"sample.json");samples={(x["model"],x["trace_id"]):x for x in read(O/"frozen-generations-small.json")}
config={"observer_timeout_s":300,"replay_budget_s":300,"shard_wall_budget_s":72000}
atomic_json(T/"config.json",config)
modules=["segmenter.py","segmenter_v2.py","segmenter_fast.py","syntax_command.lean","export_observations.py","campaign_annotation.py","campaign_worker.py"]
src={"files":{str(O/f):digest(O/f) for f in modules},"observer_binary_sha256":digest(O/"repl-observer")}
atomic_json(T/"source-manifest.json",src)
model_paths={};tokenizer_files={};shards={};selected=[0,5,17,21,23]
for task,idx in enumerate(selected):
    label=labels[idx];m=label["model"];s=samples[(m,label["trace_id"])]
    proto=read(ROOT/"runs/lean_reverification_20260913_local"/m/"main/protocol.json")
    token_files={p.name:digest(p) for p in Path(proto["model_path"]).iterdir() if p.is_file() and p.name in ["tokenizer.json","tokenizer_config.json","special_tokens_map.json","vocab.json","merges.txt","added_tokens.json","config.json"]}
    item={"trace_id":s["trace_id"],"model":m,"problem_id":s["problem_id"],"old_category":label["category"],
          "sample":s,"label_row_sha256":label["row_sha256"],"label_origin":"frozen-small-regression",
          "source_identity":digest(T/"source-manifest.json"),"header":label["replay"]["header"],"body":label["body"],
          "body_start":label["body_start"],"n_old_blocks":len(label["steps"])}
    path=T/"inputs"/f"{task}.jsonl";path.write_bytes(canonical(item)+b"\n")
    shards[str(task)]={"file":path.name,"sha256":digest(path),"count":1,"model_path":proto["model_path"],"tokenizer_files":token_files}
atomic_json(T/"inputs/manifest.json",{"shards":shards,"total":len(selected)})
checks={}
for task in range(len(selected)):
    cmd=[sys.executable,str(O/"campaign_worker.py"),"--root",str(T),"--task",str(task)]
    subprocess.run(cmd,check=True)
    out=T/"shards"/f"{task:03d}"
    rows=[json.loads(x) for x in (out/"observations.jsonl").read_text(encoding="utf-8").splitlines()]
    checks[f"task_{task}_accounted"]=len(rows)==1 and rows[0]["status"]==("parse_unsupported" if task==4 else "annotated")
    if task==2:checks["heavy_verified_no_redundant_replay"]=rows[0]["n_replays"]==0 and rows[0]["n_positions"]==8
    if task==1:checks["heavy_refuted_localized"]=rows[0]["p2_eligible"]
# Simulate a crash after blob rename but before journal append, plus a torn final row.
out=T/"shards/000";journal=out/"observations.jsonl"
row=json.loads(journal.read_text(encoding="utf-8").splitlines()[0]);before=digest(out/row["artifact"])
journal.write_bytes(b'{"incomplete"')
subprocess.run([sys.executable,str(O/"campaign_worker.py"),"--root",str(T),"--task","0"],check=True)
checks["orphan_blob_reused"]=digest(out/row["artifact"])==before
checks["torn_journal_quarantined"]=bool(list(out.glob("observations.jsonl.torn-*")))
before_j=digest(journal)
subprocess.run([sys.executable,str(O/"campaign_worker.py"),"--root",str(T),"--task","0"],check=True)
checks["finished_resume_is_noop"]=digest(journal)==before_j
data=(T/"inputs/0.jsonl").read_bytes();(T/"inputs/0.jsonl").write_bytes(data+b" ")
rejected=subprocess.run([sys.executable,str(O/"campaign_worker.py"),"--root",str(T),"--task","0"],capture_output=True,text=True)
(T/"inputs/0.jsonl").write_bytes(data)
checks["changed_input_refused"]=rejected.returncode!=0 and "changed frozen input shard" in rejected.stderr
checks["all_curated_checks"]=all(r["checks_passed"] for r in read(O/"validation/cases-summary.json") if r["group"]=="curated")
checks["four_previous_timeouts_collected"]=all("exception" not in r for r in read(O/"profile/results.json")["results"] if r["mode"]=="selected")
gate={"job":os.environ["SLURM_JOB_ID"],"checks":checks,"passed":all(checks.values()),"source":src,
      "profile":read(O/"profile/results.json"),"note":"Prior regression computations completed; its final manifest writer used an old filename and was corrected without discarding outcomes."}
atomic_json(O/"quality-gate.json",gate)
print(json.dumps(gate),flush=True)
if not gate["passed"]:raise RuntimeError("batch quality gate failed")
