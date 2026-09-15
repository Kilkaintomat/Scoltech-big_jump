"""Audit every fresh deduction attempt with the unchanged symbolic verifier."""
from pathlib import Path
from collections import Counter, defaultdict
import os
from onebigjump.e1.artifacts import read_json, verify_manifest, write_once, finish, digest
from onebigjump.e1.stages import rows
from onebigjump.readiness.deduction import check
base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
root = base / "runs/development_20260913_exactlength/deduction"
generation = root / "pilot/generation/shard-000-of-001/manifest.json"
labels_manifest = root / "pilot/verification/manifest.json"
for p in (source, generation, labels_manifest): verify_manifest(p)
samples = rows(generation.parent / "samples.jsonl")
labels = {r["trace_id"]: r for r in rows(labels_manifest.parent / "labels.jsonl")}
assert len(samples) == len(labels) and set(labels) == {s["trace_id"] for s in samples}
old_source = base / "audit/revision_2026_09_13/deduction-before.py"
new_source = Path(os.environ["E1_SNAPSHOT"]) / "src/onebigjump/readiness/deduction.py"
def checker_body(p):
    text = p.read_text(encoding="utf-8")
    return text[text.index("def check("):text.index("\n\ndef population(")]
assert checker_body(old_source) == checker_body(new_source)
groups = defaultdict(Counter)
first_errors = Counter()
format_delta=Counter();unknown_lines=Counter();format_cases=0
gold = []
examples = []
for s in samples:
    p = s["problem"]
    result = check(s["completion"], p)
    label = labels[s["trace_id"]]
    if s["finish_reason"] != "length":
        assert result["category"] == label["category"]
        assert result["t_star"] == label["t_star"] and result["steps"] == label["steps"]
    proof = "\n".join("Mira is " + x + "." for x in p["gold_chain"]) + "\nAnswer: true"
    gold.append(check(proof, p)["verified"])
    for name in ("all", "temperature:" + str(s["temperature"]), "length:" + str(p["length"])):
        groups[name]["attempts"] += 1
        groups[name][label["category"]] += 1
        groups[name]["format_eligible"] += bool(label["format_eligible"])
    if label["category"] == "format_error":
        format_cases += 1
        format_delta[str(label["observed_steps"]-p["length"])] += 1
        unknown_lines.update(label["unknown_lines"])
    if label["category"] == "invalid_inference":
        bad = label["steps"][label["t_star"]]
        first_errors["t_star:" + str(label["t_star"])] += 1
        first_errors["repeats_given" if bad["fact"] == p["initial"] else "other"] += 1
    if label["category"] != "verified" and len(examples) < 12:
        examples.append({"trace_id": s["trace_id"], "problem": p, "completion": s["completion"], "label": label})
assert all(gold)
summary = {k: dict(v) for k, v in groups.items()}
for values in summary.values():
    values["format_fraction"] = values["format_eligible"] / values["attempts"]
    values["verified_fraction"] = values.get("verified", 0) / values["attempts"]
metrics = {"format_errors":format_cases,"format_step_delta":dict(format_delta),"unknown_lines":dict(unknown_lines),"groups": summary, "first_errors": dict(first_errors), "gold_checks": len(gold),
           "gold_passed": sum(gold), "checker_unchanged": True,
           "format_gate": read_json(root / "protocol.json")["format_gate"],
           "format_gate_passed": summary["all"]["format_fraction"] >= read_json(root / "protocol.json")["format_gate"],
           "allow_main": read_json(root / "protocol.json")["allow_main"],
           "interpretation": "technical development pilot; fresh unpaired tasks; no confirmatory scientific inference"}
folder = base / "audit/revision_2026_09_13" / (os.environ["SLURM_JOB_ID"] + "-deduction-review")
out = write_once(folder / "metrics.json", metrics)
example = write_once(folder / "examples-server-only.json", examples)
finish(folder, stage="fresh-deduction-verifier-audit", context={"source": digest(source)},
       inputs=[source, generation, labels_manifest, old_source, new_source, root / "protocol.json", Path(__file__)],
       outputs=[out, example], metrics=metrics)
print(metrics, flush=True)
print("DEDUCTION_REVIEW", folder, flush=True)
