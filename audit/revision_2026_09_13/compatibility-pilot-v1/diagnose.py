"""Bounded, separate native-evaluation and symbol-compatibility diagnostic."""
from pathlib import Path
from collections import defaultdict, Counter
import datetime, hashlib, io, json, os, re, tarfile, time, urllib.request
from onebigjump.e1.artifacts import read_json, write_once, finish, digest, identity, verify_manifest
from onebigjump.e1.spans import mask_comments
from onebigjump.e1.verification import theorem_name, trusted_prefix
from onebigjump.e1.stages import pilot_gate, lean_fingerprint
from onebigjump.lean.environment import discover
from onebigjump.lean.verifier import LeanREPL, ReplError, _errors

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/compatibility-pilot-v1"
PARENT=BASE/"audit/revision_2026_09_13/label-yield-audit-v1/result-8466260"
ROOT=BASE/"runs/lean_reverification_20260913_local"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
OUT=HERE/("result-"+os.environ["SLURM_JOB_ID"])
STRICT={"propext","Classical.choice","Quot.sound"}
ALIASES={"le_div_iff":"le_div_iff₀", "ZMod.nat_cast_self":"ZMod.natCast_self",
         "Nat.pow_le_pow_of_le_left":"Nat.pow_le_pow_left"}
SYMBOLS=["Real.sqrt_eq_iff_sq_eq",*ALIASES,*ALIASES.values()]
INPUTS=[SOURCE,Path(__file__),HERE/"protocol.json",HERE/"diagnostic.sbatch",HERE/"body.sh",PARENT/"manifest.json"]


def pick(rows,n,used):
    result=[]
    for row in sorted(rows,key=lambda r:identity(["compatibility-pilot-v1",r["model"],r["trace_id"]])):
        key=row["problem_id"]
        if key in used:continue
        used.add(key);result.append(row)
        if len(result)==n:break
    return result


def replace_live(body,old,new):
    masked=mask_comments(body,mask_strings=True)
    pattern=r"(?<![\w.])"+re.escape(old)+r"(?![\w.])"
    matches=list(re.finditer(pattern,masked))
    for match in reversed(matches):
        body=body[:match.start()]+new+body[match.end():]
    return body,len(matches)


def reference_sources():
    url="https://codeload.github.com/leanprover-community/mathlib4/tar.gz/refs/tags/v4.9.0"
    path=OUT/"mathlib-v4.9.0-reference.tar.gz"
    try:
        request=urllib.request.Request(url,headers={"User-Agent":"onebigjump-compatibility-audit"})
        with urllib.request.urlopen(request,timeout=30) as response:
            data=response.read(64*1024*1024+1)
        if len(data)>64*1024*1024:raise ValueError("reference archive exceeds bounded download")
        path.write_bytes(data)
        hits={s:[] for s in SYMBOLS}
        with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as tar:
            for member in tar:
                if not member.isfile() or not member.name.endswith(".lean") or member.size>4*1024*1024:continue
                stream=tar.extractfile(member)
                if stream is None:continue
                text=stream.read().decode("utf-8")
                for symbol in SYMBOLS:
                    bare=symbol.rsplit(".",1)[-1]
                    if re.search(r"\b(?:theorem|lemma|def|abbrev)\s+"+re.escape(bare)+r"(?=\s|\(|\{|:)",text):
                        hits[symbol].append(member.name)
        return dict(available=True,url=url,sha256=digest(path),declaration_name_hits=hits,
            limitation="Static tagged Mathlib source only; namespace/type equivalence and Lean 4.9 executable compatibility are not established.")
    except Exception as exc:
        return dict(available=False,url=url,error=repr(exc),limitation="No old toolchain installed or changed.")


def check(repl,source):
    start=time.monotonic()
    try:
        reply=repl.command(source,timeout_s=20)
        errors=_errors(reply)
        axiom_messages=[str(x.get("data","")) for x in reply.get("messages",[]) if "axioms" in str(x.get("data",""))]
        axioms=[]
        for message in axiom_messages:
            match=re.search(r"depends on axioms:\s*\[(.*?)\]",message,re.S)
            if match:axioms.extend(x.strip() for x in match.group(1).split(",") if x.strip())
        return dict(status="rejected" if errors else "accepted",errors=errors,reply=reply,
            axioms=axioms,axiom_audit_present=bool(axiom_messages),
            strict_axioms=not errors and bool(axiom_messages) and set(axioms)<=STRICT,
            elapsed_s=time.monotonic()-start)
    except (TimeoutError,ReplError) as exc:
        result=dict(status="timeout_or_repl_error",error=str(exc),elapsed_s=time.monotonic()-start)
        repl.restart()
        return result


def main():
    OUT.mkdir()
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    verify_manifest(PARENT/"manifest.json")
    allrows=[dict(r,model=m) for m,rr in read_json(PARENT/"audited-row-summary.json").items() for r in rr]
    selected=[];used=set()
    for row in pick([r for r in allrows if r["native_policy_only"] and r["category"]=="sorry_invalid_proof"],8,used):
        selected.append(dict(row,group="native",old="native_decide",replacement="decide +kernel"))
    for old,new in ALIASES.items():
        candidates=[r for r in allrows if r["unknown_symbol_error"] and old in r["error_first_line"]]
        for row in pick(candidates,2,used):
            selected.append(dict(row,group="symbol",old=old,replacement=new))
    for model in ("deepseek","goedel","kimina"):
        for row in pick([r for r in allrows if r["model"]==model and r["category"]=="verified"],1,used):
            selected.append(dict(row,group="positive_control"))
    selection=write_once(OUT/"selection.json",selected)
    print("SELECTED",[(r["group"],r["model"],r["trace_id"]) for r in selected],flush=True)
    reference=reference_sources()
    reference_file=write_once(OUT/"reference-sources.json",reference)
    print("REFERENCE",reference,flush=True)
    wanted={(r["model"],r["trace_id"]) for r in selected}
    labels={}
    inventory=read_json(PARENT/"accepted-inventory.json")
    for model,manifests in inventory.items():
        for manifest in manifests:
            p=Path(manifest)
            with (p.parent/"labels.jsonl").open(encoding="utf-8") as stream:
                for line in stream:
                    r=json.loads(line)
                    key=(model,r["trace_id"])
                    if key in wanted:
                        labels[key]=r;INPUTS.append(p)
    assert set(labels)==wanted
    problems={m:{p["problem_id"]:p for p in read_json(ROOT/m/"inputs/problems.json")} for m in ("deepseek","goedel","kimina")}
    config=read_json(ROOT/"deepseek/main/protocol.json")
    for model in ("deepseek","goedel","kimina"):
        INPUTS.extend([ROOT/model/"inputs/problems.json",ROOT/model/"main/protocol.json",pilot_gate(ROOT/model,SOURCE)])
    records=[];probes={}
    runtime=lean_fingerprint(config["lean"])
    with LeanREPL(discover(config["lean"]["workspace"]),imports="import Mathlib\nimport Aesop",
                  default_timeout_s=20,drain_timeout_s=5,startup_attempts=1) as repl:
        fixtures={}
        for name,body in [("positive","theorem obj_diag_positive : True := by trivial\n#print axioms obj_diag_positive"),
                          ("negative","theorem obj_diag_negative : False := by decide\n#print axioms obj_diag_negative"),
                          ("unsolved","theorem obj_diag_unsolved (P Q : Prop) (h : P) : P ∧ Q := by\n  constructor\n  · exact h\n#print axioms obj_diag_unsolved")]:
            fixtures[name]=check(repl,body)
        assert fixtures["positive"]["strict_axioms"]
        assert fixtures["negative"]["status"]=="rejected" and fixtures["unsolved"]["status"]=="rejected"
        for symbol in SYMBOLS:probes[symbol]=check(repl,"#check "+symbol)
        for chosen in selected:
            model=chosen["model"];tid=chosen["trace_id"];r=labels[(model,tid)]
            problem=problems[model][chosen["problem_id"]]
            name=theorem_name(problem)
            assert _errors(repl.command("#check "+name,timeout_s=20)), "benchmark answer already imported"
            prefix="set_option maxHeartbeats 400000\n"+problem["directives"]+"\n"+problem["statement"]
            suffix="\n#print axioms "+name+"\n"
            original_source=prefix+r["body"]+suffix
            source_file=OUT/(model+"-"+identity(tid)[:12]+"-original.lean")
            source_file.write_text(original_source,encoding="utf-8")
            original=check(repl,original_source)
            record=dict(group=chosen["group"],model=model,trace_id=tid,original_category=r["category"],
                        original_source=str(source_file),original=original)
            if chosen["group"] in {"native","symbol"}:
                changed,count=replace_live(r["body"],chosen["old"],chosen["replacement"])
                record.update(old=chosen["old"],replacement=chosen["replacement"],replacements=count)
                if count:
                    candidate_file=OUT/(model+"-"+identity(tid)[:12]+"-candidate.lean")
                    candidate_file.write_text(prefix+changed+suffix,encoding="utf-8")
                    record.update(candidate_source=str(candidate_file),candidate=check(repl,prefix+changed+suffix))
                else:record["candidate"]={"status":"not_applicable_no_literal_token"}
            records.append(record)
            print("CASE",record["group"],model,tid,original["status"],record.get("candidate",{}).get("status"),flush=True)
    outcomes=write_once(OUT/"cases.json",records)
    diagnostic=write_once(OUT/"fixtures-and-probes.json",dict(fixtures=fixtures,probes=probes))
    groups={}
    for group in ("native","symbol","positive_control"):
        rr=[r for r in records if r["group"]==group]
        groups[group]=dict(cases=len(rr),original_status=dict(Counter(r["original"]["status"] for r in rr)),
            candidate_status=dict(Counter(r.get("candidate",{}).get("status","not_requested") for r in rr)),
            candidate_strict_proofs=sum(r.get("candidate",{}).get("strict_axioms",False) for r in rr))
    metrics=dict(started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        runtime=runtime,groups=groups,fixtures_passed=True,reference_sources_available=reference["available"],
        main_labels_changed=False,main_jobs_changed=False,new_generations=0,
        diagnostic_budget=dict(command_timeout_s=20,max_heartbeats=400000,workers=1),
        limitations=["Selected diagnostic cases, not a random estimate of population rescue rate.",
            "Candidate proofs are edited diagnostic copies, not the original generated traces.",
            "No other Lean version was installed or executed. Static source lookup alone does not prove cross-version compatibility.",
            "A diagnostic timeout is not a mathematical rejection."])
    metric=write_once(OUT/"metrics.json",metrics)
    report=["# Отдельная диагностика native_decide и совместимости","",
        "Основные журналы, версии и задания сохранены. Новая генерация не запускалась. Проверены диагностические копии сохранённых доказательств.","",
        "## Результаты","",json.dumps(groups,ensure_ascii=False,indent=2),"",
        "Протокол: детерминированный выбор различных задач по хешу; восемь native-кандидатов, до двух примеров для каждого фиксированного соответствия имён, положительные контроли от каждой модели. "
        "В кандидатах заменяются только выбранные токены вне комментариев и строк; условие теоремы сохраняется. Бюджет каждого вызова — 20 секунд и 400000 heartbeats.",
        "","Точная конфигурация текущего Lean/Mathlib, все ответы компилятора, аксиомы, исходные и изменённые копии — рядом с этим отчётом.",
        "","Старые исходники Mathlib v4.9.0: "+json.dumps(reference,ensure_ascii=False,indent=2),
        "","## Следующий этап","",
        "Если диагностическая копия компилируется с базовыми аксиомами, это подтверждает возможность доказательства данной теоремы и конкретный путь исправления; исходная генерация при этом не становится автоматически успешной.",
        "Проверка другой версии требует отдельного совместимого Lean + Mathlib + проверяющего окружения. Просто повысить номер Lean недостаточно: текущая версия уже новее опубликованной конфигурации Goedel.",
        "Следующий GPU-пилот следует запускать после основного извлечения активаций: фиксированный набор задач для разработки, сравнение бюджетов 8192 и 16384 при остальных одинаковых настройках, учёт GPU-времени. "
        "Не ограничивать выбор задач уже решёнными; их можно включить как положительные контроли.",
        "","Ограничения: "+" ".join(metrics["limitations"])]
    report_file=OUT/"REPORT.md";report_file.write_text("\n".join(report)+"\n",encoding="utf-8")
    outputs=[p for p in OUT.iterdir() if p.is_file()]
    finish(OUT,stage="isolated-compatibility-pilot",context=dict(source=digest(SOURCE),protocol=digest(HERE/"protocol.json")),
        inputs=list(dict.fromkeys(INPUTS)),outputs=outputs,metrics=metrics)
    print("DIAGNOSTIC_COMPLETE",OUT,groups,flush=True)


if __name__=="__main__":main()
