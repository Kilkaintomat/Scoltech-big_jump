"""Export cached v2 observations without re-running Lean or any model."""
from pathlib import Path
import argparse,json
from bisect import bisect_left
from segmenter_v2 import digest_text
from onebigjump.e1.spans import original_token_spans

def export(result,sample,tokenizer,body_start):
    a=result["token_alignment"];raw=sample["completion"].encode("utf-8")
    body=result["source"][2:]
    if body_start<0 or sample["completion"][body_start:body_start+len(body)]!=body:
        raise ValueError("cached source does not match sample body")
    if digest_text(sample["completion"])!=a["completion_sha256"]:
        raise ValueError("cached completion hash mismatch")
    if digest_text(json.dumps(sample["completion_token_ids"],separators=(",",":")))!=a["completion_token_ids_sha256"]:
        raise ValueError("cached original token IDs mismatch")
    if a["prompt_position"]!=len(sample["prompt_token_ids"])-1:
        raise ValueError("cached prompt length mismatch")
    offsets=original_token_spans(tokenizer,sample["completion_token_ids"],sample["completion"])
    n_prompt=len(sample["prompt_token_ids"])
    boundary=len(sample["completion"][:body_start].encode("utf-8"))
    idx=bisect_left([b for _,b in offsets],boundary)
    formal=None
    if idx<len(offsets):
        suffix=raw[boundary:offsets[idx][1]]
        pos=n_prompt+idx
        if not suffix.strip() and (not a["observations"] or pos<a["observations"][0]["token_position"]):
            formal={"token_position":pos,"boundary_kind":"exact" if not suffix else "trailing_whitespace",
                    "completion_bytes_before_body":boundary,"trailing_whitespace_bytes":len(suffix)}
    rows=[];prev=None
    for observation in a["observations"]:
        ids=observation["point_indices"];pts=[result["points"][i] for i in ids]
        skipped=[] if prev is None else list(range(max(prev["point_indices"])+1,min(ids)))
        row={**observation,"source_points":[{k:v for k,v in p.items() if k not in ["text","replay_evidence"]} for p in pts],
             "skipped_source_point_indices_before":skipped,
             "delta_spans_omitted_boundaries":bool(skipped)}
        rows.append(row);prev=observation
    return {"schema":"obj-segmentation-v2-observation-export","trace_id":sample["trace_id"],
        "model_id":sample.get("model_id"),"model_revision":sample.get("model_revision"),
        "tokenizer_revision":sample.get("tokenizer_revision"),
        "completion_sha256":digest_text(sample["completion"]),
        "prompt_token_ids_sha256":digest_text(json.dumps(sample["prompt_token_ids"],separators=(",",":"))),
        "completion_token_ids_sha256":a["completion_token_ids_sha256"],
        "source_sha256":result["source_sha256"],"header_sha256":result["header_sha256"],
        "localization_status":result["localization_status"],
        "observation_rows":rows,"rejected_boundaries":a["rejected"],
        "positions_with_original_prompt_baseline":a["positions"],
        "optional_formal_entry_baseline":formal,
        "positions_with_formal_entry_baseline":None if formal is None else [formal["token_position"]]+[r["token_position"] for r in rows],
        "baseline_warning":"The prompt baseline includes informal reasoning and the generated theorem header in the first increment. The formal-entry baseline is a separate analysis choice.",
        "generation_unchanged":True,"new_generation_required":False,
        "activation_extraction":"forward the same original prompt+completion token IDs; collect requested positions; no sampling",
        "production_label_certificate":False,
        "semantics":"source order with lexical scopes; independent local snapshot replays do not constitute a fresh chronological proof replay"}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("case",type=Path);p.add_argument("sample",type=Path);p.add_argument("--body-start",type=int,required=True)
    p.add_argument("--tokenizer",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    from transformers import AutoTokenizer
    result=json.loads(args.case.read_text(encoding="utf-8"));sample=json.loads(args.sample.read_text(encoding="utf-8"))
    x=export(result,sample,AutoTokenizer.from_pretrained(args.tokenizer,local_files_only=True),args.body_start)
    args.output.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
