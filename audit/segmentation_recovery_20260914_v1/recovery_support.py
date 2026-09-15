"""Import an immutable parent journal into a new source/config context."""
import json
from pathlib import Path
from onebigjump.e1.artifacts import digest,identity

def inherit(journal,parent_out,input_sha):
    parent_out=Path(parent_out)
    parent_context=json.loads((parent_out/"observations.identity.json").read_text(encoding="utf-8"))
    if parent_context["input_shard"]!=input_sha:raise ValueError("parent shard differs")
    seen=set()
    with (parent_out/"observations.jsonl").open("rb") as stream:
        for line in stream:
            if not line.endswith(b"\n"):raise ValueError("parent journal is torn; preserve and audit first")
            old=json.loads(line);rh=old.pop("row_sha256")
            if identity(old)!=rh or old["context_sha256"]!=identity(parent_context):
                raise ValueError("parent journal corrupt")
            rid=old["trace_id"]
            if rid in seen:raise ValueError("duplicate parent trace")
            seen.add(rid)
            artifact=(parent_out/old["artifact"]).resolve()
            if digest(artifact)!=old["artifact_sha256"]:raise ValueError("parent artifact corrupt")
            previous=journal.existing(rid,old["request_sha256"])
            if previous is not None:
                if previous.get("inherited_parent_row_sha256")!=rh:raise ValueError("parent row changed")
                continue
            copied={**old,"artifact":str(artifact),"inherited_parent_row_sha256":rh,
                    "inherited_parent_context":parent_context}
            journal.append(copied,old["request_sha256"])
    return len(seen)
