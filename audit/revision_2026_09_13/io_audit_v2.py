"""Read-only audit of existing labels and a bounded storage probe in Slurm."""
from pathlib import Path
import collections, datetime, hashlib, json, os, re, subprocess, time
from onebigjump.e1.artifacts import finish
root=Path("/beegfs/home/denis.rakhmankin/onebigjump")
out=root/"audit/revision_2026_09_13"/("io-audit-"+os.environ["SLURM_JOB_ID"])
out.mkdir(exist_ok=False)
raw=out/"captured"; raw.mkdir()
def dump(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
pattern=re.compile(r"remote i/o|input/output error|stale file handle|too many open files|errno 121|errno 23|errno 24",re.I)
def diagnostics(x,key=""):
    if isinstance(x,dict):
        for k,v in x.items():
            if k in {"completion","body","replay_body","header","statement","tactic","source","text"}:continue
            yield from diagnostics(v,k)
    elif isinstance(x,list):
        for v in x:yield from diagnostics(v,key)
    elif isinstance(x,str) and pattern.search(x):yield x
metrics={"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"node":os.uname().nodename,"labels":[],"log_errors":[],"probe":[],"snapshots_are_partial":True,"root_cause_established":False}
queue=root/"runs/lean_reverification_20260913/queue.json"
q=json.loads(queue.read_text(encoding="utf-8"));dump(raw/"queue.json",q)
metrics["queue_counts"]=q["counts"]
metrics["jobs"]={k:{a:t.get(a) for a in ("job_id","state")} for k,t in q["tasks"].items() if "/main-verify-" in k}
suspect=[]
for p in sorted((root/"runs/lean_reverification_20260913").glob("*/main/verification/shard-*/labels.jsonl")):
    info={"path":str(p),"categories":{},"diagnostic_matches":0,"errors":[]}
    try:
        payload=p.read_bytes(); target=raw/("--".join(p.relative_to(root/"runs/lean_reverification_20260913").parts))
        target.write_bytes(payload)
        cats=collections.Counter();rows=0
        for i,line in enumerate(payload.splitlines(),1):
            try:r=json.loads(line)
            except Exception as e: info["errors"].append({"line":i,"error":repr(e)});continue
            rows+=1;cats[r.get("category","MISSING")]+=1
            ds=list(diagnostics(r))
            if ds:
                info["diagnostic_matches"]+=1
                suspect.append({"file":str(p),"line":i,"trace_id":r.get("trace_id"),"category":r.get("category"),"t_star":r.get("t_star"),"diagnostics":ds})
        info.update(rows=rows,categories=dict(cats),sha256=hashlib.sha256(payload).hexdigest())
    except Exception as e: info["errors"].append(repr(e))
    metrics["labels"].append(info)
paths=set()
for p in sorted((root/"runs/lean_reverification_20260913/logs").glob("*")):
    if not p.is_file():continue
    try:
        payload=p.read_bytes();txt=payload.decode("utf-8",errors="replace")
        hits=[x[-3000:] for x in txt.splitlines() if pattern.search(x)]
        if hits:
            (raw/("log--"+p.name)).write_bytes(payload)
            metrics["log_errors"].append({"path":str(p),"count":len(hits),"last":hits[-5:]})
        for x in re.findall(r"(/beegfs/[^\s'\"\),:]+)",txt):
            if "/.elan/" in x:paths.add(x)
    except Exception as e:metrics["log_errors"].append({"path":str(p),"read_error":repr(e)})
metrics["suspect_label_count"]=len(suspect)
metrics["total_rows"]=sum(x.get("rows",0) for x in metrics["labels"])
assert metrics["total_rows"] > 0, "label audit matched no rows"
metrics["file_nr"] = Path("/proc/sys/fs/file-nr").read_text().strip()
metrics["file_max"] = Path("/proc/sys/fs/file-max").read_text().strip()
metrics["df"]=subprocess.run(["df","-h",str(root),str(root/"runs/lean_reverification_20260913")],capture_output=True,text=True).stdout
metrics["mounts"]=[x for x in Path("/proc/mounts").read_text().splitlines() if any(k in x for k in ("beegfs","gpfs","trinity"))]
for p in [root/"configs/repl_runtime.json",*map(Path,sorted(paths)[:12])]:
    record={"path":str(p),"trials":[]}
    for _ in range(3):
        t=time.monotonic()
        try:
            with p.open("rb") as f: data=f.read(1048576)
            record["trials"].append({"ok":True,"bytes":len(data),"sha256_prefix":hashlib.sha256(data).hexdigest(),"elapsed_s":time.monotonic()-t})
        except Exception as e:record["trials"].append({"ok":False,"error":repr(e)})
    metrics["probe"].append(record)
for folder in [out,root/"runs/lean_reverification_20260913"/("io-probe-"+os.environ["SLURM_JOB_ID"])]:
    folder.mkdir(exist_ok=True)
    record={"directory":str(folder),"write_trials":[]}
    for i in range(3):
        p=folder/("probe-"+str(i)+".bin");data=os.urandom(4096)
        try:
            with p.open("xb") as f:f.write(data);f.flush();os.fsync(f.fileno())
            record["write_trials"].append({"ok":p.read_bytes()==data,"path":str(p)})
        except Exception as e:record["write_trials"].append({"ok":False,"error":repr(e)})
    metrics["probe"].append(record)
dump(out/"suspect-labels.json",suspect)
metrics["finished_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
dump(out/"metrics.json",metrics)
finish(out,stage="io_incident_audit",context={"source_snapshot":os.environ["E1_SNAPSHOT"],"read_only_existing_artifacts":True,"snapshot_labels_not_scientifically_accepted":True},inputs=[Path(__file__)],outputs=[out/"metrics.json",out/"suspect-labels.json",*raw.iterdir()],metrics=metrics)
print(json.dumps({"output":str(out),"rows":metrics["total_rows"],"suspect_labels":len(suspect),"queue":metrics["queue_counts"],"probe":metrics["probe"]},ensure_ascii=False))
