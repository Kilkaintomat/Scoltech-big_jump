"""Render the CPU quality audit from measured metrics and explicitly scoped source review."""
import datetime,html,json,os,re,shutil,subprocess,sys
from pathlib import Path
from data import REPO,RUN as STATES,MODELS,read,atomic,digest,environment,check_manifest
HERE=REPO/"audit/segmentation_quality_20260914_v1"
ROOT=REPO/"runs/segmentation_quality_20260914_v1"
FOLLOW=REPO/"runs/segmentation_controls_20260914_v1"
OUT=ROOT/"report";OUT.mkdir(exist_ok=False)
check_manifest(ROOT/"manifest.json");check_manifest(ROOT/"enrichment-manifest.json")
metrics=read(ROOT/"metrics.json");enrich=read(ROOT/"review-enrichment.json");notes=read(HERE/"review-notes.json")
plan=read(HERE/"plan.json");queue=read(FOLLOW/"queue.json")
cases=[]
for model in MODELS:
    for c in read(ROOT/model/"review-cases.json"):
        if c["bucket"] not in notes[model]:raise ValueError("unreviewed case")
        cases.append({"model":model,"trace_id":c["trace_id"],"bucket":c["bucket"],"note":notes[model][c["bucket"]],
                     "artifact_sha256":c["artifact_sha256"],"review_status":"source_excerpts_and_saved_diagnostics_reviewed",
                     "scope":"qualitative targeted source review; not a fresh Lean replay or a random error-rate audit"})
review={"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"reviewer":"Codex source inspection",
        "scope":"source snippets, first-error diagnostics, selected branches, token rejection records and post-completion boundaries",
        "all_selected_cases_reviewed":True,"fresh_lean_replays":0,"cases":cases}
atomic(OUT/"review.json",review)
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).isoformat()
status=read(HERE/"report-queue-input.json")["squeue"]
atomic(OUT/"queue-snapshot.json",{"created_moscow":now,"squeue":status,"jobs":queue["jobs"],"original_job_ids":queue["original_jobs_retained"]})
def table(headers,rows):
 return "\n".join(["| "+" | ".join(headers)+" |","|"+"|".join(["---"]*len(headers))+"|",*["| "+" | ".join(map(str,row))+" |" for row in rows]])
def num(x):return f"{x:g}" if isinstance(x,float) else str(x)
def pct(x):return f"{100*x:.1f}%"
parts=["# ONE BIG JUMP — аудит новой сегментации и дальнейшие проверки",
       "Срез: "+now+". Отчёт сформирован из завершённых метрик и сохранённых исходных фрагментов.",
       f"Автоматически проверены все {metrics['all_attempts']:,} исходных ответов. Блокирующих нарушений привязки текста и токенов к запросам модели: {metrics['gpu_adapter_blockers']}. Это готовность данных к извлечению активаций, а не подтверждение гипотезы о больших скачках.",
       "**Что проверено**",
       "Проверены хеши входов и артефактов, оригинальные токены и версии моделей, соответствие старым меткам, полнота шардов и отсутствие дубликатов, разделение задач между калибровкой и оценкой, границы исходного кода, единственность первой ошибки и поглощающие метки. Активации и новые ответы в CPU-аудите не вычислялись.",
       table(["Модель","Всего ответов","Готовы к forward","Приняты для анализа","Локализованы P2","Задач P2"],[
         [m,v["overall"]["attempts"],v["overall"]["ready_for_forward"],v["overall"]["verified_accepted"],v["overall"]["p2_accepted"],v["overall"]["p2_tasks"]] for m,v in metrics["models"].items()]),
       "Эта таблица включает обе температуры и обе роли задач. «Приняты для анализа» — сохранённый вердикт verified плюс пригодность новой сегментации; это не новый подсчёт всех успешных генераций. Более узкий основной оценочный срез приведён ниже.",
       "**Размер основной выборки**",
       "Сохраняются исходные оценочные задачи, температура и средний слой. Длины до и после разбиения сопоставлены на одной и той же новой пригодной подвыборке ошибочных трасс.",
       table(["Модель","Трасс P2","Задач","Медиана L: старая → новая","Случайное точное попадание"],[
         [m,(g:=v["by_role_temperature"]["evaluation:T0.6"])["p2_accepted"],g["p2_tasks"],
          num(g["p2"]["median_old_L"])+" → "+num(g["p2"]["median_L"]),pct(g["p2"]["uniform_exact_chance"])] for m,v in metrics["models"].items()]),
       "Рост числа наблюдений не увеличивает число независимых задач. Поэтому шаги нельзя считать независимыми повторениями при оценке неопределённости. Появились более подробные позиции внутри прежних составных блоков; новая длина также зависит от структуры доказательства и наличия действий без открытых целей.",
       "**Границы и позиционные эффекты**",
       table(["Модель","Ошибка на первом","Ошибка на последнем","Оба соседа доступны","Задач в позиционном контроле"],[
         [m,(p:=v["by_role_temperature"]["evaluation:T0.6"]["p2"])["first_error_count"],p["last_error_count"],p["both_neighbors_count"],p["positional_null_tasks"]] for m,v in metrics["models"].items()]),
       "Числа ошибок на первом и последнем наблюдении могут пересекаться для трассы длины один. D = позиция максимума минус позиция первой ошибки. D = −1 означает максимум слева, D = +1 — справа. Недоступное смещение считается промахом в общей доле; дополнительно выводятся доли среди трасс с доступным соседом и на общей подвыборке с обоими соседями. Индексы не обрезаются и не переносятся на другой конец.",
       "Позиционный контроль выбирает одну трассу на задачу до просмотра оценок, затем перемешивает позиции ошибки между задачами с одинаковыми семейством и точной длиной. Одиночные группы исключаются с явным отчётом охвата. Этот контроль отделяет связь внутри доказательства от типичных позиций максимума и ошибки. Малое число сопоставимых задач ограничивает мощность и область вывода; группы не укрупняются после просмотра результата.",
       "**Просмотр конкретных доказательств**",
       f"Просмотрены исходные фрагменты и сохранённые сообщения для {len(cases)} детерминированно выбранных примеров. Это качественный разбор коротких и длинных трасс, ошибок у границ и внутри, ветвлений и отклонённых границ токенов. Отбор не является случайной выборкой: по нему нельзя оценивать долю ошибок разметки во всём наборе.",
       "В примерах сообщения Lean согласуются с отмеченными исходными фрагментами: неудачные rfl/linarith, неизвестные идентификаторы, перекрытие имени локальной гипотезы и native_decide с целью, содержащей свободные переменные. Последующие ветви сохраняют метку post. Записи диагностического восстановления Lean после ошибки не считаются заново успешно достигнутыми шагами.",
       "Токены, которые захватывают следующий непустой исходный код, не используются как допустимые границы. Просмотрены реальные случаи таких отклонений у каждой модели. Слияний нескольких наблюдений в один токен в пригодном наборе не оказалось; соответствующая страта просмотра отсутствует, а не отмечена как успешно проверенная.",
       "**Существенное ограничение: хвосты после закрытия цели**"]
k=enrich["counts"]["kimina"];longcase=next(c for c in enrich["cases"] if c["model"]=="kimina" and c["bucket"]=="verified_long")
parts += [
 f"У Kimina среди всех готовых к извлечению трасс {k['all_forward']['post_completion']['traces']} содержат post_completion; таких наблюдений {k['all_forward']['post_completion']['points']}. В оценочной роли при основной температуре это {k['evaluation_T0.6']['post_completion']['traces']} трасса и {k['evaluation_T0.6']['post_completion']['points']} наблюдения. Эти числа включают только готовые к извлечению ответы и не являются новой долей математических ошибок.",
 f"Конкретный пример: {longcase['trace_id']}. Всего наблюдений {longcase['L']}, из них {longcase['post_completion_observations']} — повторения all_goals norm_num после уже закрытой цели. Содержательная часть заканчивается раньше этого хвоста. Общее доказательство при этом остаётся принятым.",
 "Текущий замороженный конвейер сохраняет этот хвост в статистике принятых трасс. Поэтому результаты Kimina необходимо читать с этим ограничением. Следующий отдельный контроль — удалить только наблюдения post_completion из принятых трасс и заново оценить whitening на очищенной калибровке. Простого удаления строк после уже рассчитанного whitening недостаточно. Для этого можно использовать сохраняемые активации; новая генерация не требуется.",
 "**Что поставлено в очередь**",
 table(["Работа","Задание","Условие старта"],[
  ["Основное извлечение, первая волна","8467086","Исходная очередь сохранена"],
  ["Основное извлечение, оставшиеся шарды","8467087","После своей модели первой волны"],
  ["Основная статистика","8467088","После извлечения"],
  ["Отдельный GPU-профиль",queue["jobs"]["profile"]["job_id"],"Пониженный приоритет, отдельная GPU"],
  ["Дополнительные проверки смещений",queue["jobs"]["controls"]["job_id"],"После успешного основного анализа"]]),
 "Профиль использует исходные ответы, выбранные по длине токенов отдельно среди принятых и локализованных ошибочных трасс. Измеряет загрузку модели, проход трансформера, вычисление вероятностей, сжатие и GPU-память; результаты не подмешиваются в научные измерения. Лимит профиля — "+str(plan["profile"]["time_limit_minutes"])+" минут, без генерации.",
 "Зафиксированы смещения "+str(plan["fixed_offsets"])+", окно ±"+str(plan["window_radius"])+", сравнения с surprisal на тех же трассах, равномерным случайным выбором и первым допустимым наблюдением. Отдельно считаются ошибки после первого наблюдения с исходными оценками, тот же срез после исключения первого приращения и трассы с обоими соседями.",
 "Позиционный тест: "+str(plan["positional_null"]["permutations"])+" перестановок; поправка Bonferroni на модели и четыре заранее выбранных исхода в полном срезе. Парные интервалы: "+str(plan["bootstrap"]["replicates"])+" пересэмплирований задач; не строятся при числе независимых задач ниже "+str(plan["bootstrap"]["min_tasks"])+". Интервалы условны на оценённом преобразовании. Остальные срезы — чувствительность, а не дополнительные подтверждающие проверки.",
 "План сохранён до появления новых журналов активаций: "+plan["frozen_utc"]+". Это перспективно зафиксированная чувствительность после уже просмотренного исходного эксперимента; она не превращает исследование в новую подтверждающую preregistration.",
 "**Валидация и ограничения**",
 "Регрессионные тесты проверяют недоступные смещения, пересчёт максимума без сдвига исходного индекса, одинаковые максимумы, парный bootstrap задач, минимальное число задач и позиционную иллюзию: постоянное совпадение типичных позиций само по себе не даёт значимости. Полный журнал и манифест тестов включены в пакет. Live GPU-проверка выполнится при старте профиля; текущие CPU-тесты её не заменяют.",
 "Общие вердикты унаследованы из сохранённой проверки Lean; локальные проверки префикса и отказа не являются новым единым хронологическим сертификатом всего доказательства. Дерево Git содержит изменения, что явно зафиксировано; исходные снимки, конфиги и файлы дополнительно привязаны хешами. Параметры whitening и основной ячейки сохранены. Повторное использование калибровки для преобразования и порога остаётся ограничением P3.",
 "**Что можно заключить сейчас и что дальше**",
 "Подготовка новой разметки завершена, техническая согласованность входов подтверждена. Нового результата о связи скачка с ошибкой пока нет: для него нужны активации и последующая статистика. Более подробная сегментация сама по себе не подтверждает гипотезу.",
 "Дальше: дождаться выделения GPU и проверить независимое совпадение извлечённых состояний с эталонным forward; по профилю оценить время оставшейся работы; получить основную статистику и автоматические позиционные контроли; затем отдельно оценить влияние удаления хвостов post_completion с повторной калибровкой. Сравнивать нужно размеры эффекта, интервалы и охват, сохраняя отрицательные и неопределённые выводы.",
 "Точный срок получения GPU из состояния Pending/Priority не следует. Лимит задания — ограничение Slurm, а не обещание фактического времени выполнения.",
 "**Артефакты**",
 "В пакете сохранены исходные метрики, таблицы трасс, выбранные фрагменты, результаты дополнительного просмотра, письменный план, исходники проверок, журналы тестов и манифесты с контрольными суммами. review.json содержит отдельную запись для каждого просмотренного примера. Текущий снимок очереди — queue-snapshot.json."
]
# Append qualitative review only; numerical examples above derive from measured artifacts.
parts += ["**Ключевые примеры для последующей проверки**"]
for model,bucket in [("deepseek","error_interior"),("goedel","error_first_long"),("kimina","error_last"),("kimina","verified_long")]:
 c=next(c for c in cases if c["model"]==model and c["bucket"]==bucket)
 parts.append(model+" · "+c["trace_id"]+". "+c["note"])
md=OUT/"REPORT_RU.md";md.write_text("\n\n".join(parts)+"\n",encoding="utf-8")
# Reuse the already installed PDF library; no network installation.
deps=REPO/"audit/offset_review_20260914_v1/pdf_export_v1/deps";sys.path.insert(0,str(deps))
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from matplotlib import font_manager
fontpath=font_manager.findfont("DejaVu Sans");boldpath=font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans",weight="bold"))
pdfmetrics.registerFont(TTFont("DV",fontpath));pdfmetrics.registerFont(TTFont("DVB",boldpath))
styles={"body":ParagraphStyle("b",fontName="DV",fontSize=9,leading=13,spaceAfter=8),
        "title":ParagraphStyle("t",fontName="DVB",fontSize=17,leading=22,spaceAfter=14),
        "head":ParagraphStyle("h",fontName="DVB",fontSize=11,leading=15,spaceBefore=12,spaceAfter=7,keepWithNext=True),
        "cell":ParagraphStyle("c",fontName="DV",fontSize=7.3,leading=10)}
story=[]
for s in parts:
 if s.startswith("|"):
  rows=[[x.strip() for x in line.strip("|").split("|")] for line in s.splitlines() if not line.startswith("|---")]
  t=Table([[Paragraph(html.escape(x),styles["cell"]) for x in row] for row in rows],colWidths=[491/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign="LEFT")
  t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eaf0f4")),("VALIGN",(0,0),(-1,-1),"TOP"),
     ("LINEBELOW",(0,0),(-1,-1),.3,colors.HexColor("#d6e0e7")),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
  story.extend([t,Spacer(1,10)])
 else:
  style="title" if s.startswith("# ") else "head" if s.startswith("**") and s.endswith("**") else "body"
  body=s[2:] if style=="title" else s[2:-2] if style=="head" else s
  story.append(Paragraph(html.escape(body),styles[style]))
pages=[]
def footer(canvas,doc):
 pages.append(doc.page);canvas.setFont("DV",7);canvas.drawString(52,24,"ONE BIG JUMP · аудит сегментации");canvas.drawRightString(543,24,str(doc.page))
pdf=OUT/"REPORT_RU.pdf"
SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=52,rightMargin=52,topMargin=42,bottomMargin=50,
 title="ONE BIG JUMP — аудит новой сегментации").build(story,onFirstPage=footer,onLaterPages=footer)
# Copy small source/metric artifacts as a self-contained review packet.
sources=[ROOT/"metrics.json",ROOT/"manifest.json",ROOT/"review-enrichment.json",ROOT/"enrichment-manifest.json",
 HERE/"plan.json",HERE/"audit.py",HERE/"enrich.py",HERE/"render.py",HERE/"report-queue-input.json",HERE/"review-notes.json",HERE/"audit.sbatch",HERE/"enrich.sbatch",HERE/"render.sbatch",
 FOLLOW/"queue.json",FOLLOW/"tests-8467132/metrics.json",FOLLOW/"tests-8467132/manifest.json",FOLLOW/"tests-8467132/tests.log"]
for model in MODELS:
 sources += [ROOT/model/n for n in ["metrics.json","manifest.json","traces.csv","review-cases.json","profile-selection.json","errors.json"]]
sources += list((REPO/"audit/segmentation_controls_20260914_v1").glob("*"))
for p in sources:
 if p.is_file():
  relative=p.relative_to(REPO);dest=OUT/"provenance"/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
receipt={"created_moscow":now,"config":{"source":"CPU audit, deterministic source review, frozen plan","pages":len(pages)},
 "source_control":read(STATES/"source-manifest.json")["source_control"],"environment":environment(),
 "inputs":{str(p):digest(p) for p in sources if p.is_file()},"outputs":{str(p.relative_to(OUT)):digest(p) for p in OUT.rglob("*") if p.is_file()}}
atomic(OUT/"manifest.json",receipt)
print("REPORT READY",str(OUT),len(pages),"pages",flush=True)
