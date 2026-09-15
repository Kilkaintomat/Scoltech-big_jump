"""Restartable, one-writer batch segmentation. CPU only; no generation."""
import argparse,collections,gzip,hashlib,json,os,platform,signal,time
from pathlib import Path
from onebigjump.e1.artifacts import Journal,identity,digest,canonical
from onebigjump.lean import LeanREPL,discover
from segmenter_fast import SegmenterFast
from campaign_annotation import annotate

def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def atomic_json(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+".tmp")
    with tmp.open("wb") as f:f.write(canonical(x)+b"\n");f.flush();os.fsync(f.fileno())
    tmp.replace(p)
def load_artifact(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:return json.load(f)
def write_artifact(path,value):
    temp=path.with_name(path.name+".tmp")
    with temp.open("wb") as f:
        with gzip.GzipFile(fileobj=f,mode="wb",mtime=0) as z:z.write(canonical(value))
        f.flush();os.fsync(f.fileno())
    temp.replace(path)

def main():
    from transformers import AutoTokenizer
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--task",type=int,required=True)
    p.add_argument("--max-new",type=int,default=0);args=p.parse_args()
    root=args.root;config=read(root/"config.json");inputs=read(root/"inputs/manifest.json")
    shard=inputs["shards"][str(args.task)];source=root/"inputs"/shard["file"]
    if digest(source)!=shard["sha256"]:raise RuntimeError("changed frozen input shard")
    code=read(root/"source-manifest.json")
    for name,h in code["files"].items():
        if digest(Path(name))!=h:raise RuntimeError("changed frozen source: "+name)
    env=discover()
    if digest(env.repl_binary)!=code["observer_binary_sha256"]:raise RuntimeError("active observer binary mismatch")
    tok=AutoTokenizer.from_pretrained(shard["model_path"],local_files_only=True)
    for name,h in shard["tokenizer_files"].items():
        if digest(Path(shard["model_path"])/name)!=h:raise RuntimeError("tokenizer changed: "+name)
    out=root/"shards"/f"{args.task:03d}";out.mkdir(parents=True,exist_ok=True)
    blobs=out/"records";blobs.mkdir(exist_ok=True)
    ctx={"input_shard":shard["sha256"],"source_manifest":digest(root/"source-manifest.json"),"config":digest(root/"config.json")}
    stop={"requested":False}
    def stopping(*_):stop["requested"]=True
    signal.signal(signal.SIGTERM,stopping);signal.signal(signal.SIGUSR1,stopping)
    started=time.monotonic();repl=None;s=None;processed=0;age=0
    try:
      with Journal(out/"observations.jsonl",ctx) as journal:
        with source.open(encoding="utf-8") as f:
          for line in f:
            item=json.loads(line);rid=item["trace_id"];request=identity(item)
            previous=journal.existing(rid,request)
            if previous is not None:
                if digest(out/previous["artifact"])!=previous["artifact_sha256"]:raise RuntimeError("existing record corrupted")
                continue
            if stop["requested"] or time.monotonic()-started>config["shard_wall_budget_s"]:break
            key=hashlib.sha256(rid.encode()).hexdigest();path=blobs/(key+".json.gz")
            if path.exists():
                cached=load_artifact(path)
                if cached["input_sha256"]!=request or cached["context"]!=ctx:raise RuntimeError("orphan identity mismatch")
                row=cached["row"]
            else:
                if not item.get("exclusion") and (repl is None or age>=16):
                    if repl is not None:repl.close()
                    repl=LeanREPL(env,imports="import Mathlib\nimport Aesop",startup_attempts=1,
                                  startup_timeout_s=90,default_timeout_s=config["observer_timeout_s"],drain_timeout_s=5)
                    repl.__enter__();s=SegmenterFast(repl,timeout_s=config["observer_timeout_s"]);age=0
                row,detail,restart=annotate(item,s,tok,config["replay_budget_s"]);age+=1
                if repl is not None and (restart or row.get("n_blocks",0)>128 or row.get("elapsed_s",0)>20):
                    repl.close();repl=None;s=None
                write_artifact(path,{"schema":"obj-observation-v3","input_sha256":request,"context":ctx,"row":row,"detail":detail})
            row={**row,"artifact":str(path.relative_to(out)),"artifact_sha256":digest(path),
                 "execution":{"job":os.environ.get("SLURM_JOB_ID"),"task":args.task,"host":platform.node()}}
            journal.append(row,request);processed+=1
            progress={"completed":len(journal.rows),"expected":shard["count"],"new_this_run":processed,
                      "last_trace":rid,"last_status":row["status"],"updated_unix":time.time(),
                      "job":os.environ.get("SLURM_JOB_ID"),"elapsed_s":time.monotonic()-started}
            atomic_json(out/"progress.json",progress);print(json.dumps(progress),flush=True)
            if args.max_new and processed>=args.max_new:break
        counts=collections.Counter(r["status"] for r in journal.rows.values());complete=len(journal.rows)==shard["count"]
        metrics={"completed":len(journal.rows),"expected":shard["count"],"all_accounted":complete,"statuses":dict(counts),
                 "p2_eligible":sum(r["p2_eligible"] for r in journal.rows.values()),"generation_calls":0,"model_forward_calls":0}
        atomic_json(out/"metrics.json",metrics)
        if complete:
            atomic_json(out/"manifest.json",{"context":ctx,"metrics":metrics,
                "outputs":{str(out/"observations.jsonl"):digest(out/"observations.jsonl"),
                           str(out/"observations.identity.json"):digest(out/"observations.identity.json")}})
        elif not args.max_new:raise SystemExit(75)
    finally:
        if repl is not None:repl.close()
if __name__=="__main__":main()
