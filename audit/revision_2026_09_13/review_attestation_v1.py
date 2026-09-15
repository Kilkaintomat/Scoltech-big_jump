"""Assistant source-review attestation of the fixed gate packets; no human signoff."""
from pathlib import Path
from collections import Counter
import os
from onebigjump.e1.artifacts import read_json,write_once,finish,digest
base=Path("/beegfs/home/denis.rakhmankin/onebigjump");audit=base/"audit/revision_2026_09_13"
root=audit/"8466072-compiler-review";source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
records=read_json(root/"results.json");m=read_json(root/"metrics.json")
notes={
 ("kimina",6):"Length stop; no closed Lean block. No formal step/t* is available.",
 ("kimina",7):"Length stop; no closed Lean block. No formal step/t* is available.",
 ("deepseek",4):"Length stop inside the final theorem header. Earlier closed blocks are exposition, not a completed final proof. Truncation takes precedence.",
 ("deepseek",5):"Length stop in natural-language reasoning without a closed Lean block.",
 ("goedel",6):"Final block changes only theorem name (apatap to apap); proposition text is preserved. Strict header identity excludes it; not evidence of a false proposition.",
 ("goedel",7):"Final block renames theorem to lean_workbook_79784; proposition is preserved. Strict header identity excludes it; not evidence of a false proposition.",
 ("goedel",8):"Length stop in natural-language reasoning without a closed Lean block.",
 ("goedel",9):"Length stop after several conflicting proof sketches; changed summation notation and theorem name occur. No unique completed eligible final proof.",
 ("deepseek",9):"Standalone whole proof reproduces deterministic 400000-heartbeat exhaustion. Saved step replay succeeds; t* stays absent. Resource exclusion is retained without inventing a failed step."
}
review=[]
for r in records:
 key=(r["model"],r["packet_index"]);state=r["status"]
 note=notes.get(key)
 if note is None:
  if state=="verified_reproduced":note="Standalone compiler accepts original proof in trusted context with the original allowed axiom set."
  elif state=="first_rejection_reproduced":note="Prefix before t* elaborates; prefix including t* rejects. Appended diagnostic sorry closes remaining goals only and is never an accepted model proof."
  elif state=="compiler_rejection_reproduced":note="Standalone compiler reproduces parser rejection; original Lean error concerns obsolete summation syntax."
  elif state=="native_policy_exclusion_reproduced":note="Original native_decide proof compiles and step replay succeeds. Rejection is the frozen whitelist's native auxiliary axiom policy, not a literal sorry or a failed tactic."
  else:raise RuntimeError("Unreviewed case "+str(key))
 review.append({"model":r["model"],"trace_id":r["trace_id"],"category":r["category"],"compiler_status":state,"assessment":note})
special=next(r for r in records if any(c["name"].endswith("_diagnostic_decide") for c in r["checks"]))
dec=next(c for c in special["checks"] if c["name"].endswith("_diagnostic_decide"))
false=next(c for c in special["checks"] if c["name"].endswith("_diagnostic_false"))
assert dec["success"] and not false["success"] and not false["infrastructure_error"] and not false["timeout"]
resource=next(r for r in records if (r["model"],r["packet_index"])==("deepseek",9))
assert "maximum number of heartbeats" in (root/resource["checks"][0]["log"]).read_text(encoding="utf-8")
assert len(records)==36 and not m["absorbing_violations"] and not m["infrastructure_errors"] and not m["compiler_timeouts"]
metrics={"packet_review_completed":True,"reviewer":"assistant source inspection plus independent standalone compiler; not human signoff",
 "reviewed_examples":len(review),"compilations":m["compilations"],"statuses":dict(Counter(r["compiler_status"] for r in review)),
 "native_policy_only_pilot_counts":{model:d["native_policy_only"] for model,d in m["pilot_inventory"].items()},
 "main_labels_edited":False,"primary_policy_changed":False,
 "release_status":"collection may continue; main scientific claims pending complete main/controls and explicit native-policy limitation",
 "limitations":["Gate-selected examples are not random and do not validate all main traces.",
 "Native diagnostics do not authorize accepting arbitrary axioms by name pattern.",
 "Name-only header exclusions reflect strict identity rather than a changed proposition.",
 "Original verified labels concern formal Lean statements, not informal reasoning or benchmark fidelity."],
 "next_steps":["Finish immutable v7 main and prespecified controls.",
 "Report native-policy exclusions separately and quantify their frequency in completed main labels.",
 "Evaluate any native-inclusive sensitivity as a separately versioned protocol; never relabel silently.",
 "Audit benchmark formalization issues separately from model tactic errors."]}
out=audit/(os.environ["SLURM_JOB_ID"]+"-review-attestation")
a=write_once(out/"metrics.json",metrics);b=write_once(out/"case-review.json",review)
lines=["# Ревью пилотных Lean-трасс завершено",
 f"Проверены {len(review)} фиксированных примеров из пакетов gate; выполнено {m['compilations']} отдельных компиляций.",
 "Ревью выполнено ассистентом с независимым запуском обычного компилятора Lean. Это не подпись человека и не случайная выборка из всей основной серии.",
 "Сохранены исходные доказательства, основная политика аксиом и метки. Подробные решения по каждому примеру: case-review.json.",
 "","| Модель | Исключения только из-за native-аксиомы во всём пилоте |","|---|---:|"]
for model,count in metrics["native_policy_only_pilot_counts"].items():lines.append(f"| {model} | {count} |")
lines += ["","native_decide в закреплённом Lean создаёт вспомогательную аксиому. Оба примера из пакета проходят обычный компилятор; диагностическая замена на decide тоже проходит и использует только стандартные аксиомы. Эта замена не является выходом модели и не включается в анализ.",
 "Все такие исключения Kimina в полном пилотном журнале не имеют буквального sorry и проходят whole/replay. Категорию sorry_invalid_proof нельзя здесь переводить как математическую ошибку модели.",
 "Два разобранных исключения Goedel меняют имя теоремы, сохраняя условие. Текущая строгая политика сохраняется, но смысл исключений должен быть указан.",
 "Один пример DeepSeek исчерпывает общий лимит heartbeats при успешном пошаговом replay. Это ресурсное расхождение без локализованного t*; оно не используется для искусственного ошибочного шага.",
 "","До научных выводов нужны полная основная серия, все контроли и явное описание ограничений native-политики. Содержательное ревью выявило селективность допуска, которую нельзя скрывать общей категорией неверных доказательств."]
report=out/"REPORT.md";report.write_text("\n".join(lines)+"\n",encoding="utf-8")
finish(out,stage="assistant-pilot-review-attestation",context={"source":digest(source)},
 inputs=[source,Path(__file__),root/"manifest.json"],outputs=[a,b,report],metrics=metrics)
print("REVIEW_ATTESTED",out,flush=True)
