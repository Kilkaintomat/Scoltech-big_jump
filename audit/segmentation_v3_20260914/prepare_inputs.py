"""Freeze 20,016 existing answers with verified row identities; no Lean or LLM execution."""
import argparse,collections,json,os,subprocess
from pathlib import Path
from onebigjump.e1.artifacts import digest,identity,canonical
from onebigjump.e1.spans import formal_body,SourceExclusion
from onebigjump.e1.verification import trusted_prefix
from campaign_worker import atomic_json,read
MODELS=["deepseek","goedel","kimina"]
SAMPLE_FIELDS=["trace_id","completion","prompt_token_ids","completion_token_ids","model_id","model_revision","tokenizer_revision",
               "problem_id","role","temperature","attempt_index","finish_reason"]

def journal_rows(path):
    ctx=identity(read(path.with_suffix(".identity.json")));seen=set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.endswith("\n"):raise ValueError("torn upstream journal")
            raw=json.loads(line);h=raw.pop("row_sha256")
            if identity(raw)!=h or raw["context_sha256"]!=ctx:raise ValueError("upstream journal digest mismatch")
            if raw["trace_id"] in seen:raise ValueError("duplicate upstream trace")
            seen.add(raw["trace_id"]);yield raw,h

def check_outputs(path):
    m=read(path)
    for f,h in m["outputs"].items():
        if digest(Path(f))!=h:raise ValueError("upstream manifest output mismatch: "+f)

def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);args=p.parse_args()
    out=args.root;inp=out/"inputs";inp.mkdir(parents=True,exist_ok=True)
    repo=Path("/beegfs/home/denis.rakhmankin/onebigjump")
    nshards=8;shards={};counts={};origins={};source_identity=digest(out/"source-manifest.json")
    for mi,model in enumerate(MODELS):
        root=repo/"runs/lean_reverification_20260913_local"/model
        protocol=read(root/"main/protocol.json")
        problems={p["problem_id"]:p for p in read(root/"inputs/problems.json")}
        for f,h in protocol["inputs"].items():
            if digest(root/"inputs"/f)!=h:raise ValueError("protocol input changed")
        lm=root/"main/verification/manifest.json";check_outputs(lm)
        labels={r["trace_id"]:(r,h) for r,h in journal_rows(root/"main/verification/labels.jsonl")}
        if len(labels)!=6672:raise ValueError("unexpected label count")
        origins[model]={"labels_manifest":str(lm),"sha256":digest(lm),"protocol":digest(root/"main/protocol.json"),"generation_manifests":{}}
        streams={};model_counts=collections.Counter();seen=set()
        for si in range(nshards):
            task=3*si+mi;name=f"task-{task:03d}.jsonl"
            streams[si]=(inp/name).open("wb")
            tok_files={}
            for f in Path(protocol["model_path"]).iterdir():
                if f.is_file() and (f.name in ["tokenizer.json","tokenizer_config.json","special_tokens_map.json","vocab.json","merges.txt","added_tokens.json","config.json"]):
                    tok_files[f.name]=digest(f)
            shards[str(task)]={"file":name,"count":0,"model":model,"model_path":protocol["model_path"],"tokenizer_files":tok_files}
        try:
          for gm in sorted((root/"main/generation").glob("shard-*/manifest.json")):
            check_outputs(gm);origins[model]["generation_manifests"][str(gm)]=digest(gm)
            for sample,sample_hash in journal_rows(gm.parent/"samples.jsonl"):
                rid=sample["trace_id"]
                if rid in seen or rid not in labels:raise ValueError("duplicate or unexpected generation")
                seen.add(rid);label,label_hash=labels[rid];problem=problems[sample["problem_id"]]
                header=f"set_option maxHeartbeats {protocol['lean']['max_heartbeats']}\n{problem['directives']}\n{problem['statement']}"
                item={"trace_id":rid,"model":model,"problem_id":sample["problem_id"],"old_category":label["category"],
                    "old_whole_proof_ok":label.get("whole_proof_ok"),"sample":{k:sample[k] for k in SAMPLE_FIELDS if k in sample},
                    "sample_row_sha256":sample_hash,"label_row_sha256":label_hash,"label_origin":str(lm),
                    "source_identity":source_identity,"header":header,"n_old_blocks":len(label.get("steps",[]))}
                if label.get("body") is None or label["category"] in ["context_statement_mismatch","generation_truncation"]:
                    item["exclusion"]=label["category"]
                else:
                    try:parsed=formal_body(sample["completion"],problem["statement"],trusted_prefix(problem,protocol["lean"]["max_heartbeats"]))
                    except SourceExclusion as e:
                        item["exclusion"]="source_parser:"+e.category
                    else:
                        if parsed["body"]!=label["body"] or parsed["body_start"]!=label["body_start"]:
                            raise ValueError("source parser changed existing proof identity")
                        if label.get("replay",{}).get("header",header)!=header:raise ValueError("trusted header mismatch")
                        item.update(body=parsed["body"],body_start=parsed["body_start"])
                si=int(identity(rid)[:16],16)%nshards;task=3*si+mi
                streams[si].write(canonical(item)+b"\n");shards[str(task)]["count"]+=1
                model_counts[item.get("exclusion","observe")]+=1
        finally:
            for f in streams.values():f.flush();os.fsync(f.fileno());f.close()
        if seen!=set(labels):raise ValueError("missing generation")
        counts[model]={"total":len(seen),"preparation_categories":dict(model_counts)}
        print(model,json.dumps(counts[model]),flush=True)
    for r in shards.values():r["sha256"]=digest(inp/r["file"])
    manifest={"total":sum(s["count"] for s in shards.values()),"shards":shards,"origins":origins,"models":counts,
              "job":os.environ["SLURM_JOB_ID"],"validation_scope":"upstream row identities and immediate output manifests; original answer and trusted header identity"}
    if manifest["total"]!=20016:raise ValueError("corpus size mismatch")
    atomic_json(inp/"manifest.json",manifest)
    print("PREPARED",manifest["total"],flush=True)
if __name__=="__main__":main()
