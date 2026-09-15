import json,re,datetime,hashlib
from pathlib import Path
from stage_support import read,digest
from artifact_bridge import finish_artifact
R=Path("/beegfs/home/denis.rakhmankin/onebigjump")
OUT=R/"runs/followthrough_recovery_20260916_v2/report_v2"
OUT.mkdir(exist_ok=False)
F=R/"runs/followthrough_20260915_v1"
old=R/"runs/result_review_20260914_v1/report_v3"
follow=F/"followthrough_report_v2"
for root in [old,follow]:
 manifest=read(root/"manifest.json")
 for name,h in manifest["outputs"].items():assert digest(name)==h,name
text=(old/"REPORT_RU.md").read_text(encoding="utf-8")
def table_after(marker):
 tail=text.split(marker,1)[1].lstrip()
 return tail.split("\n\n",1)[0]
main=table_after("**Разные знаменатели**")
p2=table_after("**Выбранная ячейка; все допустимые evaluation-трассы с ошибкой**")
def inventory(path):
 if not path.exists():return {"saved":0,"ids":[],"partial_final_line":False}
 raw=path.read_bytes();parts=raw.splitlines(keepends=True);partial=bool(parts and not parts[-1].endswith(b"\n"))
 if partial:parts=parts[:-1]
 rows=[json.loads(x) for x in parts]
 assert len({x["trace_id"] for x in rows})==len(rows)
 return {"saved":len(rows),"ids":[x["trace_id"] for x in rows],"partial_final_line":partial,"read_sha256":hashlib.sha256(raw).hexdigest(),"alignment_exclusions":sum(not x.get("original_token_alignment",{"passed":True})["passed"] for x in rows)}
inv={};newrows=[]
for model in ["deepseek","goedel"]:
 reqs=read(F/"p2_pipeline"/(model+"-requests.json"))
 for role in ["pilot","evaluation"]:
  label=model+"/"+role;inv[label]=inventory(F/"p2_pipeline"/model/role/"generation/samples.jsonl")
  inv[label]["expected"]=sum(x["role"]==role for x in reqs)
  newrows.append("| "+model+" | "+("Технический пилот" if role=="pilot" else "Оценочная часть")+" | "+str(inv[label]["saved"])+" / "+str(inv[label]["expected"])+" |")
p5=inventory(F/"p5_calibration/main/generation/shard-000-of-001/samples.jsonl")
p5plan=read(R/"audit/followthrough_20260915_v1/p5-plan.json")
p5metrics={}
for stage in ["generation/shard-000-of-001","verification","extraction"]:
 p=F/"p5_calibration/main"/stage/"metrics.json"
 if p.exists():p5metrics[stage]=read(p)
gate=F/"p5_calibration/calibration_gate/metrics.json"
p5gate=read(gate) if gate.exists() else None
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%d.%m.%Y %H:%M МСК")
m={"as_of":now,"p2":inv,"p5_saved":p5,"p5_stage_metrics":p5metrics,"p5_gate":p5gate}
(OUT/"metrics.json").write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8")
summary="""# Состояние One Big Jump

Срез: AS_OF.

Основная серия на miniF2F завершила сбор ответов и последующий анализ. Новая проверка переноса на ProofNet-Verified и расширенная калибровка логической дедукции были остановлены техническими сбоями; их продолжение восстановлено. Новых окончательных выводов по этим двум сериям пока нет.

## Что мы проверяем

Модель сама генерирует формальное доказательство. Проверяющая система Lean устанавливает, принято ли доказательство и где воспроизводится первый отказ. На границах шагов мы измеряем изменение скрытого вектора модели. «Скачок» — величина такого изменения. Surprisal — насколько неожиданны для модели токены шага. Сравнение со surprisal проверяет, даёт ли геометрия скрытых состояний пользу сверх обычной неуверенности модели.

P1 — различаются ли хвосты распределений скачков у верных и ошибочных решений. P2 — совпадает ли самый большой скачок с первым ошибочным шагом. P3 — можно ли надёжно оценить редкие превышения порога и их хвост. P4 — меняется ли хвостовой показатель при появлении обобщения у обучаемой модели. P5 — как меняется успешность логического вывода с длиной цепочки.

## Уже полученные результаты

MAIN_TABLE

«Ответы» — сохранённые попытки LLM. «Извлечены» — ответы, для которых получены результаты прохода модели. Научная таблица требует дополнительных условий пригодности. Последний столбец относится только к ошибочным оценочным трассам выбранной температуры; эти знаменатели не следует путать с общей долей решённых задач.

P2: доля ответов, в которых максимум точно попал в первую ошибку:

P2_TABLE

Это исходная выбранная ячейка завершённого анализа, а не результаты нового ProofNet. На старых данных преимущество Goedel над surprisal сохранялось после поправки при равном весе попыток; при равном весе задач вывод слабее. Последующие проверки с раздельной калибровкой и формальным началом доказательства сохраняют зависимость от выбранного разбиения. Старые данные уже использованы для выбора уточнений, поэтому требуется новое подтверждение.

P1 не дал устойчивого общего разделения верных и ошибочных решений. Для P3 выявлена проблема повторного использования одних калибровочных наблюдений при нормировке и выборе порога. Разделение этих задач заметно уменьшает ложные тревоги, но также снижает обнаружение ошибок. Для P4 обучение и обобщение получены, однако надёжного хвостового признака перехода не обнаружено. Совокупность результатов пока не подтверждает общий тяжёлохвостый механизм ошибки.

Случайный стратифицированный аудит повторил исходные категории всех выбранных ответов; отдельная проверка прямым компилятором также не выявила несогласия категорий вне ресурсных ограничений. Это повышает доверие к проверенным меткам, но не заменяет независимого воспроизведения научного эффекта.

## Что сейчас продолжается

P2: DeepSeek и Goedel решают новый для истории генераций проекта набор ProofNet-Verified. В нём учебниковые задачи с формальными математическими утверждениями и предварительно проверенными эталонами; эталонные доказательства в запрос модели не передаются. Набор охватывает иную область задач, поэтому это проверка переноса. Отсутствие этих задач в предобучении моделей не установлено.

| Модель | Часть | Сохранено / назначено |
| --- | --- | --- |
NEW_ROWS

P5: Qwen решает искусственные цепочки правил вида «если A, то B; если B, то C», начиная с известного факта. Случайные имена и порядок правил меняются; формат ответа ограничен грамматикой, а логическую правильность проверяет отдельный алгоритм. Ограничение формата не подсказывает верный следующий вывод. Сейчас собирается отдельная калибровочная часть: P5_SAVED сохранённых ответов. Оценочная часть допускается только после проверки формата, извлечения состояний и достаточного числа независимо решённых калибровочных задач в каждой группе. P5_GATE

Восстановление P2 сохраняет исходные токены и явно учитывает ответы, для которых нельзя надёжно совместить текст с токенами. Такие ответы остаются в общем числе попыток, но не объявляются математическими ошибками. Уже записанные ответы не генерируются заново. Часть ответов не успела сохраниться при прежних сбоях; они повторяются с прежними назначенными seed, но побитовое воспроизведение утраченных ответов не гарантируется. Это ограничение нужно сохранить при интерпретации.

## Что делать дальше для статьи

1. Завершить новый P2 по зафиксированному протоколу: проверить доказательства, извлечь состояния и оценить заранее выбранные сравнения на независимых группах задач. Не выбирать лучший слой, порог или способ взвешивания по новым ответам.
2. Довести P5 до калибровочного допуска. Если верных независимых задач недостаточно, зафиксировать это как ограничение и не подменять независимую оценку повторной подгонкой.
3. Для P3 проверить точность интервалов и частоту ложных тревог при раздельном обучении преобразования и порога. Увеличение числа ответов само по себе ошибку калибровки не устраняет.
4. Формулировать статью вокруг реально поддержанных утверждений: ограниченного сигнала локализации, его переносимости и границ хвостового объяснения. Отрицательный результат P4 и нестабильность P1/P3 важны для проверки теории.

Валидность доказательств повышать нужно прежде всего независимыми задачами, корректными знаменателями, проверкой меток и заранее выбранными сравнениями. Простое увеличение числа попыток на старых задачах даёт меньше новой информации. Более широкие эксперименты разумно выбирать после результатов этой проверки переноса и калибровки.
"""
summary=summary.replace("AS_OF",now).replace("MAIN_TABLE",main).replace("P2_TABLE",p2).replace("NEW_ROWS","\n".join(newrows)).replace("P5_SAVED",str(p5["saved"]))
summary += "\nСводка проверяет контрольные суммы готовых отчётов и их метрик и фиксирует текущие журналы. Она не является новым пересчётом основных эффектов или повторной проверкой каждого доказательства.\n"
summary=summary.replace("P5_GATE",("Допуск ещё не рассчитан." if p5gate is None else "Результат допуска: "+("пройден." if p5gate["ready_for_evaluation"] else "не пройден.")))
(OUT/"REPORT_RU.md").write_text(summary,encoding="utf-8")
finish_artifact(OUT,stage="dated-experiment-status-report",context={"as_of":now},inputs=[Path(__file__),old/"REPORT_RU.md",old/"metrics.json",follow/"REPORT_RU.md",follow/"metrics.json",R/"runs/followthrough_recovery_20260916_v2/preflight/manifest.json"],outputs=[OUT/"metrics.json",OUT/"REPORT_RU.md"],metrics={"as_of":now,"p2_saved":sum(x["saved"] for x in inv.values()),"p2_expected":sum(x["expected"] for x in inv.values()),"p5_calibration_saved":p5["saved"]})
print(json.dumps({"report":str(OUT),"as_of":now,"p2_saved":sum(x["saved"] for x in inv.values()),"p5_saved":p5["saved"],"p5_gate":p5gate},ensure_ascii=False),flush=True)
