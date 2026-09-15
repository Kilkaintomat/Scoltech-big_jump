"""Checked adapter from semantic observations to original-token model requests."""
import gzip,json,os
from pathlib import Path
from bisect import bisect_right
from onebigjump.e1.artifacts import canonical,digest,identity,environment

REPO=Path("/beegfs/home/denis.rakhmankin/onebigjump")
AUDIT=REPO/"audit/segmentation_extraction_20260914_v1"
RUN=REPO/"runs/segmentation_states_20260914_v1"
SEG=REPO/"runs/segmentation_20260914_v3_recovery1"
MODELS=["deepseek","goedel","kimina"]
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def atomic(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+".tmp")
    with tmp.open("wb") as f:f.write(canonical(x)+b"\n");f.flush();os.fsync(f.fileno())
    tmp.replace(p)
def checked_rows(p,context):
    seen=set()
    with Path(p).open("rb") as stream:
        for line in stream:
            if not line.endswith(b"\n"):raise ValueError("unfinished journal")
            r=json.loads(line);h=r.pop("row_sha256")
            if identity(r)!=h or r["context_sha256"]!=identity(context):raise ValueError("corrupt journal")
            if r["trace_id"] in seen:raise ValueError("duplicate trace")
            seen.add(r["trace_id"]);r["row_sha256"]=h;yield r
def check_manifest(p):
    m=read(p)
    for name,h in m["outputs"].items():
        if digest(name)!=h:raise ValueError("corrupt upstream: "+name)
    return m
def check_source():
    m=read(RUN/"source-manifest.json")
    for name,h in m["files"].items():
        if digest(name)!=h:raise ValueError("changed frozen source: "+name)
    if digest(SEG/"inputs/manifest.json")!=m["segmentation_inputs_sha256"]:raise ValueError("inputs changed")
    return m
def finish(out,metrics,inputs,outputs):
    atomic(out/"metrics.json",metrics)
    source=read(RUN/"source-manifest.json")
    atomic(out/"manifest.json",{"config":read(RUN/"config.json"),"source_control":source["source_control"],
        "source_manifest_sha256":digest(RUN/"source-manifest.json"),"environment":environment(),
        "inputs":{str(p):digest(p) for p in inputs},
        "outputs":{str(p):digest(p) for p in [out/"metrics.json",*outputs]},"metrics":metrics})
def shard_items(task):
    meta=read(SEG/"inputs/manifest.json")["shards"][str(task)]
    p=SEG/"inputs"/meta["file"]
    if digest(p)!=meta["sha256"]:raise ValueError("changed original IDs")
    with p.open(encoding="utf-8") as f:items=[json.loads(x) for x in f]
    if len(items)!=meta["count"]:raise ValueError("input count mismatch")
    folder=SEG/"shards"/f"{task:03d}"
    m=check_manifest(folder/"manifest.json")
    if not m["metrics"]["all_accounted"]:raise ValueError("shard incomplete")
    rows={r["trace_id"]:r for r in checked_rows(folder/"observations.jsonl",m["context"])}
    if set(rows)!={x["trace_id"] for x in items}:raise ValueError("annotation coverage mismatch")
    for item in items:
        row=rows[item["trace_id"]]
        if row["input_sha256"]!=identity(item):raise ValueError("annotation/input mismatch")
        path=folder/row["artifact"]
        if digest(path)!=row["artifact_sha256"]:raise ValueError("corrupt observation")
        yield item,row,path
def load_export(item,row,path):
    with gzip.open(path,"rt",encoding="utf-8") as f:blob=json.load(f)
    if blob["input_sha256"]!=identity(item):raise ValueError("artifact input mismatch")
    e=blob["detail"]["export"];s=item["sample"]
    from segmenter_v2 import digest_text
    if e["completion_sha256"]!=digest_text(s["completion"]):raise ValueError("completion changed")
    for name in ["prompt_token_ids","completion_token_ids"]:
        h=digest_text(json.dumps(s[name],separators=(",",":")))
        if e[name+"_sha256"]!=h:raise ValueError("original token IDs changed")
    if e["model_revision"]!=s["model_revision"] or e["model_id"]!=s["model_id"]:raise ValueError("model mismatch")
    return e
def alignment(item,export,tokenizer):
    from onebigjump.e1.spans import original_token_spans
    sample=item["sample"];n=len(sample["prompt_token_ids"]);ids=sample["prompt_token_ids"]+sample["completion_token_ids"]
    positions=export["positions_with_original_prompt_baseline"]
    obs=export["observation_rows"]
    if positions!=[n-1]+[o["token_position"] for o in obs]:raise ValueError("position contract")
    if len(positions)<2 or positions!=sorted(set(positions)) or positions[-1]>=len(ids):raise ValueError("invalid positions")
    if sample["completion"][item["body_start"]:item["body_start"]+len(item["body"])]!=item["body"]:
        raise ValueError("body changed")
    offsets=original_token_spans(tokenizer,sample["completion_token_ids"],sample["completion"])
    ends=[b for a,b in offsets];spans=[]
    for o in obs:
        start=min(p["span_start"] for p in o["source_points"])
        char=item["body_start"]+start-2
        byte=len(sample["completion"][:char].encode("utf-8"))
        lo=bisect_right(ends,byte);hi=o["completion_token_index"]
        if not 0<=lo<=hi<len(offsets):raise ValueError("invalid surprisal source span")
        spans.append([lo,hi])
    formal=export["optional_formal_entry_baseline"]
    all_positions=sorted(set(positions+([] if formal is None else [formal["token_position"]])))
    return {"positions":positions,"capture_positions":all_positions,"source_token_spans_inclusive":spans,
            "formal_position":None if formal is None else formal["token_position"]}
