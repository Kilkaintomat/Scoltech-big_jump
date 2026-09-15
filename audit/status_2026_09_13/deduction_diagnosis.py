"""Describe format failures without changing or relabelling saved model outputs."""
from pathlib import Path
from collections import Counter
from onebigjump.e1.artifacts import read_json,finish,write_once,verify_manifest
from onebigjump.e1.stages import rows
from onebigjump.readiness.deduction import check
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
root=base/"runs/expansion_20260911/deduction/pilot"
generation=root/"generation/shard-000-of-001/manifest.json"
verification=root/"verification/manifest.json"
for p in (generation,verification):verify_manifest(p)
samples=rows(generation.parent/"samples.jsonl")
labels={r["trace_id"]:r for r in rows(verification.parent/"labels.jsonl")}
m={"attempts":len(samples),"unique_tasks":len({s["problem"]["problem_id"] for s in samples}),
   "categories":dict(Counter(r["category"] for r in labels.values())),
   "eligible_initial_fact_repetitions":0,"eligible_first_failure_at_zero":0,
   "gold_checker_passes":0,"format_wrong_length":0,"format_unknown_lines":0,
   "finish_reasons":dict(Counter(str(s.get("finish_reason")) for s in samples)),
   "scope":"diagnostic only; saved generations and primary labels unchanged"}
for s in samples:
 r=labels[s["trace_id"]];problem=s["problem"]
 gold="\n".join("Mira is "+x+"." for x in problem["gold_chain"])+"\nAnswer: true"
 m["gold_checker_passes"]+=int(check(gold,problem)["verified"])
 if r["format_eligible"]:
  m["eligible_initial_fact_repetitions"]+=int(r["steps"][0]["fact"]==problem["initial"])
  m["eligible_first_failure_at_zero"]+=int(r["t_star"]==0)
 else:
  m["format_wrong_length"]+=int(r["observed_steps"]!=problem["length"])
  m["format_unknown_lines"]+=int(bool(r.get("unknown_lines")))
folder=base/"audit/status_2026_09_13/deduction-diagnosis"
path=write_once(folder/"metrics.json",m)
finish(folder,stage="deduction-format-diagnosis",context={},inputs=[Path(__file__),generation,verification],outputs=[path],metrics=m)
print(m,flush=True)
