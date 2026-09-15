import collections,csv,datetime,shutil,zipfile
from stage_support import *
from followthrough_render import render
def main():
 start("followthrough_report");folder=OUT/"followthrough_report";folder.mkdir(exist_ok=True);assert not (folder/"manifest.json").exists()
 inputs=[];metrics={};blocks=[];outputs=[];tables=folder/"tables";tables.mkdir(exist_ok=True)
 def H(s):blocks.append(("h",s))
 def P(s):blocks.append(("p",s))
 def T(heads,rows,widths=None):
  p=tables/(str(len(outputs)+1)+".csv")
  with p.open("w",encoding="utf-8",newline="") as f:w=csv.writer(f);w.writerow(heads);w.writerows(rows)
  outputs.append(p);blocks.append(("table",{"heads":heads,"rows":rows,"widths":widths}))
 def pc(x):return "—" if x is None else f"{100*x:.2f}%"
 def pp(x):return "—" if x is None else f"{100*x:+.2f}"
 def iv(x):return "—" if x is None else f"[{100*x[0]:+.2f}; {100*x[1]:+.2f}]"
 def load_metric(group):
  p=OUT/group/"manifest.json";check_manifest(p);inputs.append(p);return read(p.parent/"metrics.json")
 cal=load_metric("calibration");audits={m:load_metric("lean_audit/"+m) for m in MODELS};cli={m:load_metric("audit_cli/"+m) for m in MODELS}
 population=load_metric("p2_pipeline");p5=load_metric("p5");snapshot=read(OUT/"flow/latest.json");inputs.append(OUT/"flow/latest.json")
 protocol=read(HERE/"p2-confirmatory-protocol.json");p5plan=read(HERE/"p5-plan.json")
 metrics.update(calibration=cal,audit=audits,independent_cli=cli,new_population=population,p5_setup=p5,queue=snapshot)
 H("One Big Jump: выполненные проверки и новый запуск")
 now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
 P("Срез: "+now.strftime("%d.%m.%Y %H:%M")+" по Москве. Все численные таблицы построены программой из метрик и журналов. Основные завершённые эксперименты сохранены; новые проверки находятся в отдельной ветке артефактов.")
 P("Выполнена совместная проверка очищенной Kimina, раздельной калибровки и начала формального доказательства. Проведён случайный аудит разметки и дополнительная проверка прямым компилятором Lean. Протокол нового P2 зафиксирован до новых ответов. Для DeepSeek и Goedel собран отдельный набор с проверенными эталонами; генерация поставлена в очередь. Расширение P5 начинается с отдельной калибровочной части.")
 P("Универсальная связь «максимальный скачок всегда означает ошибку» по-прежнему не установлена. Исправления измерений не превращают повторный анализ старых задач в независимое подтверждение. Новое воспроизведение предназначено именно для такой проверки.")
 H("Раздельная калибровка и формальное начало")
 P("В очищенной Kimina удалены сохранённые наблюдения после завершения уже верного доказательства. Для нового X0 берётся последний исходный токен на границе начала формального тела доказательства. Токен, захватывающий содержательный текст первой тактики, не используется как начало. Это явно отличается от исходного определения статьи, где X0 находится в конце промпта.")
 T(["Модель","Трасс в парном сравнении","Нет формальной границы","Удалено конечных шагов"],[[m,cal["models"][m]["paired_population"],cal["models"][m]["missing_formal_traces"],cal["models"][m]["removed_terminal_steps"]] for m in MODELS])
 P("Внутри прежней калибровочной части задачи разделены на две непересекающиеся группы: одна обучает среднее и ковариацию, другая задаёт порог верхнего процентиля. Направления разбиения поменяны местами; проверены все заранее указанные значения shrinkage. Оценочные задачи не используются ни для преобразования, ни для порога.")
 rows=[]
 for m in MODELS:
  for f in cal["models"][m]["variants"]["formal_entry"]:
   s=f["settings"]["0.1"];q=s["P2"]
   rows.append([m,str(f["fit_fold"]),pc(s["verified"]["step_rate"]),pc(s["at"]["step_rate"]),pc(q["jump"]),pc(q["surprisal"])])
 T(["Модель","Fit fold","Ложные срабатывания на верных шагах","Обнаружение ошибочного шага","Top1 скачок","Top1 surprisal"],rows,[65,40,106,105,85,90])
 P("В таблице доли top1 имеют вес попыток. Ложные срабатывания измеряются на шагах целиком верных оценочных доказательств; обнаружение — на локализованном первом неверном шаге. Порог и argmax отвечают на разные вопросы. Низкая частота ложных срабатываний не означает высокой чувствительности.")
 rows=[]
 for m in MODELS:
  for f in cal["models"][m]["variants"]["formal_entry"]:
   q=f["settings"]["0.1"]["P2"];rows.append([m,f["fit_fold"],q["tasks"],pp(q["equal_task_difference"]),iv(q["ci95_fixed_transform"])])
 T(["Модель","Fit fold","Задач","Top1: скачок − surprisal, п.п.","95% интервал, п.п."],rows,[72,48,50,153,168])
 P("Здесь каждой прежней задаче дан одинаковый вес, а преобразование зафиксировано. Интервалы номинальные и описательные: эти данные уже многократно анализировались, поэтому положительная граница не является новым подтверждением. У DeepSeek результат при таком взвешивании близок к нулю. Все варианты, включая противоположное разбиение и другие значения shrinkage, сохранены в полном metrics.json.")
 import matplotlib
 matplotlib.use("Agg")
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,2,figsize=(9,3.6))
 for a,key,title in zip(axes,["verified","at"],["Верные шаги: ложное срабатывание","Ошибочный шаг: обнаружение"]):
  for k,m in enumerate(MODELS):
   rates=[100*f["settings"]["0.1"][key]["step_rate"] for f in cal["models"][m]["variants"]["formal_entry"]]
   a.plot([k-.08,k+.08],rates,"o-",label=m)
  a.set_xticks(range(len(MODELS)),MODELS);a.set_ylabel("% шагов");a.set_title(title,fontsize=10);a.grid(alpha=.2)
 fig.tight_layout();figpath=folder/"calibration.png";fig.savefig(figpath,dpi=170);plt.close(fig);outputs.append(figpath)
 blocks.append(("figure",{"file":"calibration.png","caption":"Обе перестановки калибровочных групп; очищенные данные, формальное начало, shrinkage из основной настройки. Разброс между точками показывает чувствительность к разбиению."}))
 H("Случайный аудит Lean")
 selection=load_metric("lean_audit");total=sum(v["completed"] for v in audits.values());agreement=sum(v["category_agreement"] for v in audits.values())
 fine=sum(s["fine_reproduced"] for v in audits.values() for s in v["strata"].values())
 P(f"Всего случайно отобрано и повторно проверено {total} ответов. Совпало {agreement} исходных категорий; точная локализация воспроизвелась в {fine} выбранных случаях, для которых она ранее была установлена. Отбор выполнен без использования величины скачка или surprisal.")
 T(["Модель","Проверено","Категории совпали","Верные: подтверждены Lean CLI","Разногласия CLI, кроме обрывов"],[[m,audits[m]["completed"],audits[m]["category_agreement"],str(cli[m]["verified_independently_certified"])+"/"+str(cli[m]["original_verified"]),cli[m]["nontruncated_category_disagreements"]] for m in MODELS],[69,66,92,132,132])
 P("Отбор стратифицирован: отдельно проверены верные доказательства, ранняя и более поздняя локализованная ошибка, отсутствие надёжной локализации, незакрытые цели, обрыв генерации, ресурсные/контекстные исключения и ошибки формата. Малые категории включались полностью. Это не простая случайная выборка всех ответов, поэтому объединённую долю нельзя выдавать за несмещённую оценку частоты ошибок разметки.")
 T(["Страта","DeepSeek","Goedel","Kimina"],[[st,*[selection["selection"][m]["strata"][st]["selected"] for m in MODELS]] for st in selection["selection"]["deepseek"]["strata"]])
 P("Повтор через REPL проверяет воспроизводимость существующего конвейера. Прямой запуск Lean CLI дополнительно проверяет целое доказательство другим путём подачи исходника и аудит зависимостей теоремы. Эти проверки используют одну версию Lean и одно доверенное формальное утверждение; они не доказывают соответствие формализации неформальному тексту задачи.")
 for m in MODELS:
  P(m+": отдельный компилятор — "+str(cli[m]["statuses"])+". Обрыв с целым допустимым сертификатом: "+str(cli[m]["truncated_but_certificate_valid"])+".")
 P("Ошибка тактики означает, что конкретное применение тактики не прошло проверку. Незакрытая цель означает, что после доступного тела остаётся недоказанное обязательство; это не обязательно неверность последней выполненной тактики. В таких случаях условная привязка отказа к последней позиции не должна подменять надёжно воспроизведённую локализацию.")
 P("Обрыв по лимиту генерации сохраняется отдельным исходом. Ресурсный предел, несовместимость окружения, изменение утверждения моделью и ошибка формата тоже остаются отдельными категориями. Их нельзя автоматически объявлять математической ошибкой конкретного шага.")
 H("Новый набор для воспроизведения")
 P("Источник — исправленный ProofNet-Verified, зафиксированный git commit "+protocol["new_source"]["commit"]+". Источник указывает Lean 4.28; эталон проверяется в фактическом закреплённом окружении проекта. Основное окружение не обновлялось.")
 P("В исходных эталонных файлах встречаются одновременно исходные и исправленные утверждения; встречается и повторяющееся имя задачи. Итоговый идентификатор включает номер записи. Проверяется не совпадение имени, а новое объявление с точным утверждением из JSON и с допустимыми зависимостями доказательства. Эталонные доказательства и неформальные решения не входят в промпты моделей.")
 T(["Показатель","Значение"],[["Кандидатов после проверки прежней генерации",population["candidate_problems"]],["Задач с прошедшим эталоном",population["compatible_problems"]],["Групп упражнений",population["compatible_exercise_groups"]],["Групп технического пилота",population["technical_pilot_groups"]],["Групп независимой оценки",population["evaluation_groups"]]])
 T(["Исход проверки эталона","Задач"],list(population["reference_categories"].items()))
 T(["Модель","Всего новых попыток","Технический пилот","Независимая оценка"],[[m,*[population["models"][m][k] for k in ["planned_attempts","pilot_attempts","evaluation_attempts"]]] for m in protocol["models"]])
 P("Этот набор новый для истории генерации данного проекта. Отсутствие задач в предобучении моделей не установлено. Переход от miniF2F к учебниковым задачам меняет предметную область; новое исследование проверяет перенос результата, а не точное повторение исходного распределения задач.")
 H("Зафиксированный протокол подтверждения P2")
 P("Единица веса — группа независимого упражнения. Сначала усредняются пригодные попытки одной задачи, затем задачи внутри упражнения, затем сами группы. Подпункты одного упражнения не считаются отдельными независимыми наблюдениями.")
 P("Goedel: основной результат — средняя разность top1 между скачком и surprisal. DeepSeek: основной результат — точное совпадение максимума с ошибкой после первого наблюдения, когда первое приращение исключено, сверх позиционного контроля по учебнику и точной длине.")
 P("Для DeepSeek один представитель упражнения выбирается детерминированно по хешу до фильтрации позиции ошибки. Если у выбранного представителя отсутствует формальная граница, другой ответ вместо него не подбирается. Затем ошибки переставляются только внутри групп одинакового учебника и длины. Одиночные страты отдельно учитываются как несопоставимые.")
 P("В семействе два основных утверждения. Для Goedel требуется положительная нижняя граница двустороннего интервала уровня "+pc(1-.05/protocol["primary_family"]["size"])+". Для DeepSeek используется односторонний точный порог "+str(.05/protocol["primary_family"]["size"])+". При недостатке "+str(protocol["minimum_independent_groups"])+" независимых групп результат считается недостаточно определённым.")
 P("Границы не зацикливаются и не обрезаются искусственно: если соседнего шага нет, соответствующий сдвиг недоступен. Основное сравнение — D=0. Сдвиги и окно около ошибки остаются дополнительными проверками, для них указываются знаменатели и доступность границ.")
 P("Слой, температура, shrinkage, формальное начало, число попыток и правило остановки заданы до новых ответов. Преобразование берётся из фиксированного направления раздельной калибровки на старых задачах; лучший вариант по новой оценке не выбирается. Предусмотрено полное завершение запланированного набора, без остановки или расширения из-за промежуточного p-value.")
 H("Расширение контролируемого P5")
 T(["Часть","Задач","Попыток"],[[x["stage"],x["problems"],x["attempts"]] for x in p5["checks"]])
 P("Сначала генерируется только калибровочная часть. Для каждой температуры независимо требуются не менее "+str(p5plan["minimum_verified_tasks_per_transform_fold"])+" верных задач для обучения преобразования и столько же для отдельного выбора порога, а также достаточное качество формата и подтверждение извлечения состояний. Оценочная часть автоматически допускается только после этого условия.")
 P("P5 остаётся контролируемым семейством цепочек modus ponens со случайными именами и порядком правил. Увеличение числа экземпляров не добавляет новых логических семейств. Синтаксическое ограничение формата не выбирает математически верный следующий шаг.")
 P("Предусмотрен прогноз успеха по длине: коэффициент оценивается на калибровочных задачах, качество прогноза проверяется на оценочных и сравнивается с постоянной вероятностью, также обученной на калибровке. Все назначенные попытки, включая неверный формат и обрывы, остаются в знаменателе. Подгонка зависимости от длины сама по себе не определяет экстремальный индекс, порог или тяжёлохвостый механизм.")
 H("Очередь, контроль и оставшиеся действия")
 P("Состояния планировщика ниже относятся к моменту "+snapshot["checked_utc"]+". Численное время ожидания GPU не гарантируется: срок выдачи ресурса определяется планировщиком.")
 T(["Этап","Статус","Заявки"],[[name,s["state"],", ".join(str(x.get("job","")) for x in s["members"])] for name,s in snapshot["stages"].items()],[122,90,279])
 P("Новый контроллер проверяет задания раз в 30 минут, запускает подготовленные зависимые этапы и может дважды продолжить сохранённый журнал после тайм-аута, отказа узла или вытеснения. Ошибка программы, схемы или целостности данных не обходится автоматически. Старые задания не отменяются. Сообщения из cron в этот чат не подключены.")
 P("Следующие действия уже описаны в коде: завершить генерацию нового P2, выполнить Lean и точную сегментацию, извлечь состояния, применить зафиксированное преобразование и посчитать основные сравнения; для P5 — завершить калибровку, проверить допуск, затем получить независимую оценку. Результаты этих ещё не завершённых этапов в этом отчёте не заявляются.")
 H("Артефакты и воспроизведение")
 P("Корневая папка нового запуска на сервере: "+str(OUT)+". Протокол подтверждения: "+str(HERE/"p2-confirmatory-protocol.json")+". Состояние контроля: "+str(OUT/"flow/latest.json")+".")
 P("В технических манифестах исправлены ссылки на временные пути REPL внутри контейнера: они заменены постоянными файлами с теми же наблюдёнными SHA256. Исходные версии манифестов и журнал исправления сохранены; численные выходные файлы не менялись.")
 P("Код сохранён отдельно с хешами и отметкой dirty. Базовый commit не включает все сохранённые изменения, поэтому одного git checkout недостаточно. В компактном архиве есть отчёт, метрики, журналы выбранного аудита и исходники новых этапов; большие веса моделей и матрицы состояний в архив не включены.")
 P("Источник набора: https://github.com/marcusm117/ProofNet-Verified . Формальные определения проекта: docs/experimental_specification.md. Все экспериментальные числа происходят из перечисленных в манифесте файлов проекта.")
 pages=render(folder,blocks,"One Big Jump: проверки и независимое воспроизведение")
 metrics["report_pages"]=pages;metrics["generation_calls_by_report"]=0
 outputs += [folder/f for f in ["REPORT_RU.pdf","REPORT_RU.md","REPORT_RU.html"]]
 finish("followthrough_report",metrics,inputs,outputs)
 package=OUT/"followthrough_package";package.mkdir(exist_ok=True);shutil.copytree(folder,package/"report",dirs_exist_ok=True)
 for group in ["calibration","lean_audit","p2_pipeline","p5","flow","audit_cli","provenance_repair"]:
  src=OUT/group;dest=package/"data"/group;dest.mkdir(parents=True,exist_ok=True)
  for path in src.rglob("*"):
   if path.is_file() and path.suffix in [".json",".jsonl"] and path.name!="candidates.json":
    rel=path.relative_to(src)
    if len(rel.parts)>2:continue
    target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
 (package/"source").mkdir(exist_ok=True)
 for path in HERE.iterdir():
  if path.is_file() and path.suffix in [".py",".json",".sbatch",".txt"]:shutil.copy2(path,package/"source"/path.name)
 (package/"README.md").write_text("Откройте report/REPORT_RU.pdf. Это локальный снимок, не обновляемая в реальном времени панель. Метрики — data/, исходники — source/. Исходные абсолютные пути в манифестах относятся к серверу. Локальные файлы проверяются по package-manifest.json. Большие матрицы состояний и веса моделей не включены.\n",encoding="utf-8")
 files={str(p.relative_to(package)):digest(p) for p in package.rglob("*") if p.is_file() and p.name!="package-manifest.json"}
 atomic(package/"package-manifest.json",{"files":files,"report_pages":pages,"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()})
 archive=OUT/"FOLLOWTHROUGH_20260915_v1.zip"
 with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
  for path in package.rglob("*"):
   if path.is_file():z.write(path,str(path.relative_to(package)))
 atomic(OUT/"followthrough-download.json",{"archive":archive.name,"sha256":digest(archive),"files":len(files)+1,"pages":pages})
 print("FOLLOWTHROUGH REPORT READY",json.dumps(read(OUT/"followthrough-download.json")),flush=True)
if __name__=="__main__":main()
