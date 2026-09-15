"""Read-only audit of screenshot counts and proof-label yield; all computation on Slurm."""
from pathlib import Path
from collections import Counter, defaultdict
import datetime, hashlib, json, os, re
from onebigjump.e1.artifacts import digest, finish, identity, read_json, verify_manifest, write_once
from onebigjump.e1.stages import generation_inputs
from onebigjump.e1.spans import mask_comments
from onebigjump.e1.verification import ALLOWED_AXIOMS

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/revision_2026_09_13/full-population-audit-v1"
ROOT = BASE / "runs/lean_reverification_20260913_local"
REPAIRED = BASE / "audit/revision_2026_09_13/speedup-v2/repaired"
SOURCE = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
MODELS = ("deepseek", "goedel", "kimina")
OUT = HERE / ("result-" + os.environ["SLURM_JOB_ID"])
INPUTS = [SOURCE, Path(__file__), HERE / "claims.json", HERE / "audit.sbatch"]
SEEN = set()


def add_manifest(path):
    verify_manifest(path, SEEN)
    INPUTS.append(path)


def rows(path):
    data = path.read_bytes()
    complete = [line for line in data.splitlines(keepends=True) if line.endswith(b"\n") and line.strip()]
    values = [json.loads(line) for line in complete]
    for row in values:
        saved = row.pop("row_sha256")
        assert identity(row) == saved, ("row digest", path, row["trace_id"])
        row["row_sha256"] = saved
    return values, dict(path=str(path), bytes=len(data), sha256_at_read=hashlib.sha256(data).hexdigest(),
                       complete_records=len(values), partial_final_line=bool(data and not data.endswith(b"\n")))


def native_only(row):
    live = re.sub(r"«[^»]*»", "", mask_comments(row.get("body", ""), mask_strings=True))
    hole = bool(re.search(r"\b(?:sorry|admit|sorryAx)\b", live))
    unexpected = [a for a in row.get("axioms", []) if a not in ALLOWED_AXIOMS]
    native = [a for a in unexpected if re.search(r"\._native\.native_decide\.ax(?:_\d+)?$", a)]
    return bool(row.get("whole_proof_ok") and row.get("replay_ok") and not hole
                and native and set(native) == set(unexpected))


def summarise(values):
    cats = Counter(r["category"] for r in values)
    tasks = defaultdict(list)
    for r in values:
        tasks[r["problem_id"]].append(r)
    n = len(values)
    return dict(attempts=n, categories=dict(cats), verified=cats["verified"],
                verified_fraction=cats["verified"]/n if n else None,
                tasks=len(tasks), tasks_with_at_least_one_verified=sum(
                    any(r["category"] == "verified" for r in group) for group in tasks.values()),
                whole_proof_ok=sum(r.get("whole_proof_ok") is True for r in values),
                whole_and_replay_ok=sum(r.get("whole_proof_ok") is True and r.get("replay_ok") is True for r in values),
                native_policy_only=sum(r.get("native_policy_only", False) for r in values),
                kernel_ok_but_other_category=dict(Counter(r["category"] for r in values
                    if r.get("whole_proof_ok") is True and r["category"] != "verified")),
                generation_length_stop=sum(r.get("finish_reason") == "length" for r in values),
                unexplained_disagreements=sum(r.get("unexplained_disagreement", False) for r in values))


def prefix_counter(values):
    result = [Counter()]
    for row in values:
        result.append(result[-1] + Counter({row["category"]: 1}))
    return result


def reconstruct_claim(model, claim, originals):
    first = originals[0] + originals[1]
    fixed = Counter(r["category"] for r in first)
    remaining = claim["processed"] - len(first)
    p2, p3 = prefix_counter(originals[2]), prefix_counter(originals[3])
    matches = []
    for n3 in range(max(0, remaining-len(originals[2])), min(remaining, len(originals[3]))+1):
        n2 = remaining - n3
        counts = fixed + p2[n2] + p3[n3]
        if counts["verified"] == claim["verified"] and counts["localized_tactic_failure"] == claim["localized_tactic_failure"]:
            matches.append(dict(prefix_rows_by_shard=[len(originals[0]),len(originals[1]),n2,n3], categories=dict(counts)))
    return dict(claim=claim, matching_prefix_allocations=matches,
        exact_counts_reproduced=bool(matches), timestamp_recovered=False,
        interpretation="Matches are a forensic check of a supplied historical count, not a new sampled cohort.")


def main():
    OUT.mkdir(parents=True)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    claims = read_json(HERE / "claims.json")
    add_manifest(SOURCE)
    for model in MODELS:
        merged = ROOT / model / "main/verification/manifest.json"
        add_manifest(merged)
        assert read_json(merged)["metrics"]["all_planned_attempts_accounted"]
        assert read_json(merged)["metrics"]["attempts"] == 6672
    manifests = {m: sorted((REPAIRED/m).glob("shard-*/manifest.json")) for m in MODELS}
    inventory = {m: [str(p) for p in paths] for m, paths in manifests.items()}
    inventory_file = write_once(OUT / "accepted-inventory.json", inventory)
    generated = {}
    accepted = {}
    forensic = {}
    raw_progress = {}
    transitions = {}
    repairs = {}
    examples = []
    inputs_info = {}
    for model in MODELS:
        root = ROOT / model
        samples, gen_manifests = generation_inputs(root, "main")
        for p in gen_manifests: add_manifest(p)
        config = read_json(root / "main/protocol.json")
        inputs_info[model] = dict(protocol=config, input_versions=read_json(root / "inputs/input-versions.json"))
        INPUTS.extend([root / "main/protocol.json",root / "inputs/input-versions.json"])
        info = {}
        for s in samples:
            info[s["trace_id"]] = dict(problem_id=s["problem_id"], role=s["role"],
                task_family=s["task_family"], temperature=s["temperature"], attempt_index=s["attempt_index"],
                finish_reason=s["finish_reason"], tokens=len(s["completion_token_ids"]), request_identity=identity(s))
        assert len(info)==len(samples)==6672
        assert len({s["problem_id"] for s in samples})==417
        generated[model] = dict(attempts=len(samples), tasks=len({s["problem_id"] for s in samples}),
            temperatures=dict(Counter(str(s["temperature"]) for s in samples)),
            task_roles=dict(Counter({p["problem_id"]:p["role"] for p in samples}.values())),
            finishes=dict(Counter(s["finish_reason"] for s in samples)),
            families=dict(Counter({p["problem_id"]:p["task_family"] for p in samples}.values())),
            length_stop_fraction=sum(s["finish_reason"]=="length" for s in samples)/len(samples))
        del samples
        originals = {}
        snapshots = []
        raw_categories = Counter()
        for path in sorted((root / "main/verification").glob("shard-*/labels.jsonl")):
            data, snap = rows(path)
            snapshots.append(snap)
            raw_categories.update(r["category"] for r in data)
            shard = int(path.parent.name.split("-")[1])
            originals[shard] = data
            if (path.parent / "manifest.json").exists():
                add_manifest(path.parent / "manifest.json")
            # Running rows are only a progress snapshot, never promoted to audited evidence.
        raw_progress[model] = dict(files=snapshots, categories=dict(raw_categories), attempts=sum(raw_categories.values()))
        forensic[model] = reconstruct_claim(model, claims["models"][model], originals)
        entries = []
        changes = Counter()
        repair_counts = Counter()
        for manifest in manifests[model]:
            add_manifest(manifest)
            meta = read_json(manifest)
            assert meta["metrics"]["unexplained_disagreements"]==0
            shard = int(manifest.parent.name.split("-")[1])
            previous = {r["trace_id"]:r for r in originals[shard]}
            values,_ = rows(manifest.parent / "labels.jsonl")
            assert len(values)==meta["metrics"]["attempts"]
            repair_counts["fresh_selected"] += meta["metrics"]["fresh_selected"]
            for r in values:
                sample = info[r["trace_id"]]
                assert r["request_sha256"] == sample["request_identity"]
                assert r["problem_id"] == sample["problem_id"]
                if r["category"]=="verified":
                    assert r["whole_proof_ok"] is True and r["replay_ok"] is True
                assert not r["unexplained_disagreement"]
                star=r.get("t_star")
                for step in r.get("steps",[]):
                    assert star is None or not (step["index"]>=star and step["valid"])
                    assert star is None or step["index"]<=star or step["status"]=="unreached"
                old=previous[r["trace_id"]]
                changes[old["category"]+" -> "+r["category"]]+=1
                clean={k:r.get(k) for k in ["trace_id","category","whole_proof_ok","replay_ok","unexplained_disagreement","t_star"]}
                clean.update(sample)
                clean["native_policy_only"]=native_only(r)
                clean["n_steps"]=len(r.get("steps",[]))
                error_messages=[str(x.get("data","")) for x in r.get("whole_reply",{}).get("messages",[]) if x.get("severity")=="error"]
                error_text="\n".join(error_messages+[str(r.get("error",""))])
                if star is not None and star<len(r.get("steps",[])):
                    step=r["steps"][star]
                    error_text+="\n"+str(step.get("message",""))
                clean["unknown_symbol_error"]=bool(re.search(r"unknown (?:identifier|constant|tactic|command)|invalid field",error_text,re.I))
                clean["error_first_line"]=next((s[:250] for s in error_text.splitlines() if s.strip()),"")
                entries.append(clean)
                if r["category"]!="verified" and len([e for e in examples if e["model"]==model and e["category"]==r["category"]])<3:
                    examples.append(dict(model=model,trace_id=r["trace_id"],category=r["category"],
                        native_policy_only=clean["native_policy_only"],axioms=r.get("axioms"),error=error_text[:3500],
                        proof_excerpt=r.get("body","")[:1500],source_manifest=str(manifest)))
        assert len({r["trace_id"] for r in entries})==len(entries)
        accepted[model]=entries
        transitions[model]=dict(changes)
        repairs[model]=dict(repair_counts)
        print("MODEL_AUDITED",model,len(entries),flush=True)
    assert len({json.dumps(generated[m]["families"],sort_keys=True) for m in MODELS})==1
    complete={}
    for model, entries in accepted.items():
        by_task=defaultdict(set)
        for r in entries:by_task[r["problem_id"]].add((r["temperature"],r["attempt_index"]))
        expected={(t,i) for t in (0.6,1.0) for i in range(8)}
        complete[model]={pid for pid,slots in by_task.items() if slots==expected}
    common=set.intersection(*(complete[m] for m in MODELS))
    assert len(common)==417 and all(len(accepted[m])==6672 for m in MODELS)
    matched={m:[r for r in accepted[m] if r["problem_id"] in common] for m in MODELS}
    groups={}
    for model, entries in matched.items():
        groups[model]={}
        for field in ("task_family","temperature","role"):
            groups[model][field]={str(value):summarise([r for r in entries if r[field]==value])
                for value in sorted({r[field] for r in entries})}
    n_claim=sum(c["processed"] for c in claims["models"].values())
    v_claim=sum(c["verified"] for c in claims["models"].values())
    total=sum(g["attempts"] for g in generated.values())
    historical_totals=dict(processed=n_claim, verified=v_claim,
        localized_tactic_failure=sum(c["localized_tactic_failure"] for c in claims["models"].values()),
        processed_fraction=n_claim/total, verified_per_processed=v_claim/n_claim,
        verified_per_all_generated=v_claim/total, not_yet_processed_at_claim=total-n_claim,
        all_model_counts_reproduced=all(x["exact_counts_reproduced"] for x in forensic.values()))
    summaries={m:summarise(r) for m,r in accepted.items()}
    matched_summary={m:summarise(r) for m,r in matched.items()}
    metrics=dict(started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        generated=generated,historical=forensic,historical_totals=historical_totals,
        raw_progress=raw_progress,accepted=summaries,matched_tasks=len(common),
        matched=matched_summary,matched_groups=groups,repairs=repairs,transitions=transitions,
        diagnostic_unknown_symbols={m:sum(r["unknown_symbol_error"] for r in rr) for m,rr in accepted.items()},
        diagnostic_error_heads={m:dict(Counter(r["error_first_line"] for r in rr if r["category"]!="verified").most_common(15)) for m,rr in accepted.items()},
        same_model_task_sets=True,statistics_are_descriptive=True,
        limitations=["All saved attempts are accounted for; this finite benchmark does not establish generalisation to other tasks.",
            "Attempt success rate differs from at-least-one success per task.",
            "Unknown-symbol diagnostics do not establish a causal toolchain effect.",
            "Native-policy-only counts do not validate axiom provenance or change the frozen policy.",
            "Historical prefix reconstruction does not recover an exact capture timestamp."])
    metric=write_once(OUT/"metrics.json",metrics)
    settings=write_once(OUT/"settings.json",inputs_info)
    sample_file=write_once(OUT/"examples.json",examples)
    row_file=write_once(OUT/"audited-row-summary.json",accepted)
    matched_file=write_once(OUT/"matched-task-ids.json",sorted(common))
    report=["# Полный аудит сохранённой популяции Lean", "", "Срез: "+started, "",
        "Все приведённые ниже числа автоматически пересчитаны из журналов. Основные метки и протоколы не изменены.", "",
        "## Снимок с рисунка", "",
        "| Модель | Обработано | verified | verified / обработано | Локализована ошибка |",
        "|---|---:|---:|---:|---:|"]
    for model,c in claims["models"].items():
        report.append(f'| {model} | {c["processed"]} | {c["verified"]} | {c["verified"]/c["processed"]:.2%} | {c["localized_tactic_failure"]} |')
    report += ["",json.dumps(historical_totals,ensure_ascii=False,indent=2),"",
        "Исторические счётчики проверяются реконструкцией префиксов неизменённых исходных журналов; точное время снимка не восстановлено.",
        "Значение «принятые доказательства» на рисунке соответствует verified. Принятая запись обработки может иметь любой подтверждённый исход.", "",
        "## Текущие завершённые и проверенные порции", "",
        "| Модель | Записей с проверенным происхождением | verified | Доля verified |",
        "|---|---:|---:|---:|"]
    for m,s in summaries.items():
        report.append(f'| {m} | {s["attempts"]} | {s["verified"]} | {s["verified_fraction"]:.2%} |')
    report+=["","## Сравнение на одинаковых задачах","",f'Общих полностью проверенных задач: {len(common)}. На каждую модель и задачу приходится 16 попыток: по 8 при каждой из двух температур.',"",
        "| Модель | Попыток | verified | Доля | Задач с хотя бы одним verified |",
        "|---|---:|---:|---:|---:|"]
    for m,s in matched_summary.items():
        report.append(f'| {m} | {s["attempts"]} | {s["verified"]} | {s["verified_fraction"]:.2%} | {s["tasks_with_at_least_one_verified"]} / {s["tasks"]} |')
    report+=["","### Все категории на одинаковых задачах","",
        "| Категория | deepseek | goedel | kimina |","|---|---:|---:|---:|"]
    categories=sorted(set().union(*(set(s["categories"]) for s in matched_summary.values())))
    for cat in categories:
        report.append("| "+cat+" | "+" | ".join(str(matched_summary[m]["categories"].get(cat,0)) for m in MODELS)+" |")
    report+=["","### Разбиение по семейству задач","",
        "| Модель | Семейство | Задач | Попыток | verified | Доля verified |","|---|---|---:|---:|---:|---:|"]
    for m in MODELS:
        for family,s in groups[m]["task_family"].items():
            report.append(f'| {m} | {family} | {s["tasks"]} | {s["attempts"]} | {s["verified"]} | {s["verified_fraction"]:.2%} |')
    report+=["","Подробности по температуре, роли задачи, ограничениям ресурсов, native-policy-only и изменениям после исправлений — в metrics.json. Примеры с исходными сообщениями Lean — в examples.json.",
        "","Ограничения: "+ " ".join(metrics["limitations"])]
    report_file=OUT/"REPORT.md";report_file.write_text("\n".join(report)+"\n",encoding="utf-8")
    finish(OUT,stage="full-population-label-read-only-audit",context=dict(source=digest(SOURCE),scope="diagnostic only"),
        inputs=list(dict.fromkeys(INPUTS)),outputs=[metric,settings,sample_file,row_file,matched_file,inventory_file,report_file],
        metrics=dict(passed_integrity=True,generated=total,accepted=sum(s["attempts"] for s in summaries.values()),
                     matched_tasks=len(common),historical_counts_reproduced=historical_totals["all_model_counts_reproduced"]))
    print("AUDIT_COMPLETE",json.dumps(dict(historical=historical_totals,accepted=summaries,matched=matched_summary),ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
