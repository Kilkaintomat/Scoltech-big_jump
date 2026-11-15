from mp_common import *
import csv,gzip,io,shutil,re,subprocess
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
PUB=ROOT/"runs/models_projections_latest_20261115_v1"
DEST=PUB/"publication"
def tab(head,rows):
 return "\n".join(["| "+" | ".join(head)+" |","| "+" | ".join(["---"]*len(head))+" |"]+["| "+" | ".join(str(v).replace("|","/").replace("\n"," ") for v in r)+" |" for r in rows])+"\n"
def fmt(r,pct=False,ci=False):
 if not r or r.get("value") is None:return "—"
 f=100 if pct else 1;n=2 if pct else 4;s=f'{r["value"]*f:.{n}f}'
 if ci and r.get("ci95") is not None:s+=f' [{r["ci95"][0]*f:.{n}f}; {r["ci95"][1]*f:.{n}f}]'
 return s
def hp(r):
 return "—" if not r or "holm_p" not in r else f'{r["holm_p"]:.3g}'
def csvout(name,rows,compressed=False):
 if not rows:return
 fields=list(dict.fromkeys(k for r in rows for k in r))
 stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=fields);w.writeheader()
 for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
 b=stream.getvalue().encode("utf8")
 (DEST/name).write_bytes(gzip.compress(b,mtime=0) if compressed else b)
def textout(name,s):(DEST/name).write_text(s,encoding="utf8")
def short(k):return model(k)["model_id"].split("/")[-1]
def filecopy(p,name):track(p);shutil.copyfile(p,DEST/name)
def main():
 start();DEST.mkdir(exist_ok=True);assert not (DEST/"manifest.json").exists()
 stamp=datetime.datetime.now(datetime.timezone.utc);z=read(OUT/"report_part1/metrics.json")
 verify_manifest(OUT/"report_part1")
 reg=read(OUT/"part2/science_registry.json");mgr=read(OUT/"part2/management.json")
 packs=[]
 for p in sorted((OUT/"part2/contexts").glob("**/statistics/metrics.json")):
  if not (p.parent/"manifest.json").exists():continue
  verify_manifest(p.parent);a=read(p)
  if not a.get("unavailable"):packs.append(dict(context=a["context"],layer=int(p.parent.parent.name),data=a))
 ms=[];cs=[]
 for pack in packs:
  for kind,target in [("metrics",ms),("contrasts",cs)]:
   target.extend(dict(r,context=pack["context"]["id"],dataset=pack["context"]["dataset"],coefficient_mode=pack["context"]["coefficient_mode"]) for r in pack["data"][kind])
 primary_packs=[p for p in packs if p["layer"]==primary(model(p["context"]["model"]))]
 regids={c["id"] for c in reg["contexts"]};ready={p["context"]["id"] for p in primary_packs}
 planned_models=sorted({c["model"] for c in reg["contexts"]})
 queue=(PUB/"inputs/queue.txt").read_text(encoding="utf8") if (PUB/"inputs/queue.txt").exists() else ""
 own=[]
 for k in ["kimina15","deepseek15","goedelsft","goedel32"]:
  r=OUT/"part2/2B"/k
  n=read(OUT/"part2/registry/metrics.json")["own_generation_attempts_per_model"]
  own.append(dict(model=k,assigned=n,generated=sum(len(p.stem)==64 for p in (r/"generation").glob("*/*.json")),verified=sum(1 for p in (r/"verification").glob("*/*-result.json"))))
 model_status=[]
 for k in planned_models:
  plan=OUT/"part2/plans/2A"/k/"statistics.json"
  units=read(plan) if plan.exists() else []
  done=sum((OUT/"part2/contexts"/u["context"]["id"]/str(u["layer"])/"statistics/manifest.json").exists() for u in units)
  model_status.append(dict(model=k,completed_statistics=done,planned_statistics=len(units) if units else None,completed_primary=sum(c["id"] in ready for c in reg["contexts"] if c["model"]==k),planned_primary=sum(c["model"]==k for c in reg["contexts"])))
 status=dict(snapshot_utc=stamp.isoformat(),snapshot_msk=stamp.astimezone(datetime.timezone(datetime.timedelta(hours=3))).isoformat(),completed_primary_contexts=len(ready&regids),planned_primary_contexts=len(regids),completed_statistics=len(packs),part2_family_size=reg["primary_family_size"],manager_alerts=mgr.get("alerts"),manager_last_checked=mgr.get("last_checked_utc"),model_status=model_status,own_generation=own,queue=queue)
 save(DEST/"status.json",status)
 def met(k,l,src,arm,metric="hit",sec="standalone",sl="pooled"):
  return next((r for r in z["metrics"] if (r["model"],r["layer"],r["source"],r["slice"],r["section"],r["method"],r["metric"])==(k,l,src,sl,sec,arm,metric)),None)
 def con(k,l,src,arm,metric="hit",sec="localization",sl="pooled"):
  return next((r for r in z["contrasts"] if (r["model"],r["layer"],r["source"],r["slice"],r["section"],r["contrast"],r["metric"])==(k,l,src,sl,sec,arm,metric)),None)
 def pm(p,arm,metric="hit",sec="standalone",sl="pooled"):
  return next((r for r in p["data"]["metrics"] if (r["slice"],r["section"],r["method"],r["metric"])==(sl,sec,arm,metric)),None)
 def pc(p,arm,metric="hit",sec="localization",sl="pooled"):
  return next((r for r in p["data"]["contrasts"] if (r["slice"],r["section"],r["contrast"],r["metric"])==(sl,sec,arm,metric)),None)
 keys=["qwen05","qwen15","qwen7","qwen14","qwen32","deepseek","goedel"]
 p1ctx=[c for c in z["contexts"] if c["primary_layer"]]
 lines=["# Новые результаты: направления скрытых состояний, ProcessBench и Lean\n",
 f'Снимок на **{status["snapshot_msk"]} (МСК)**. Данные и таблицы сформированы на Жоресе из сохранённых метрик; переобучения ради отчёта нет.\n',
 f'**ProcessBench завершён:** {len(keys)} читающих моделей, {len(z["contexts"])} сочетаний слоя и источника направления. **Lean продолжается:** готовы {status["completed_primary_contexts"]} из {status["planned_primary_contexts"]} основных ячеек. Одна ячейка — модель × набор × источник направления; дополнительные слои и полностью замороженные переносы учитываются отдельно.\n',
 "В этом отчёте объединены новая серия models_projections, контроль позиционных бейзлайнов ProcessBench и две проверки хвостовых методов. Более ранние результаты и их другие популяции перечислены в конце.\n",
 "## Что именно сравнивается\n",
 r"На последнем токене шага читающая модель даёт состояние $X_t$. Приращение $d_t=X_t-X_{t-1}$. Отбелённая норма — $w_t=\|\widehat\Sigma^{-1/2}(d_t-\widehat\mu)\|_2$. По обучающим задачам строятся направления $n_D$ и $n_H$:"+ "\n",
 r"$$s^D_t=\frac{n_D^\top d_t}{\|n_D\|_2},\qquad h_t=\frac{n_H^\top X_t+b}{\|n_H\|_2},\qquad s^H_t=h_t-h_{t-1}.$$"+"\n",
 "nD обучается по приращениям, nH — по состояниям. Положительные примеры — первые отвергнутые шаги; отрицательные — принятые шаги до отказа и шаги верных решений. Шаги после первого отказа не считаются отрицательными примерами. Случайные направления, модули проекций, сырая норма и перпендикулярная компонента входят в полные таблицы.\n",
 "Отдельное правило выбирает argmax оценки среди всех шагов. Обученный локализатор — условный логит: вероятность каждого шага нормируется по всему доказательству. Бейзлайн B содержит позицию, относительную позицию, первый/последний шаг, число токенов, сплайн среднего surprisal и его знаковое и абсолютное изменение. Тип тактики постоянен (OTHER), поэтому это не полностью совпадает с более широким историческим бейзлайном геометрической серии.\n",
 "В таблицах локализатора «+sD» означает B+sD, а «+w» — B+w. Нормаль и локализатор обучаются без оценочных задач во вложенной групповой кросс-валидации 5×3. Нейросетевые веса заморожены. Читающая модель может отличаться от автора текста: результаты не измеряют её собственную способность решать задачи.\n",
 f'Hit — точное попадание в первую ошибку, в процентах; ΔHit — процентные пункты. NLL — отрицательный логарифм вероятности истинного шага; меньше лучше. Веса задач равны. Индивидуальные 95%-интервалы получены {z["bootstrap"]} бутстрап-повторами целых групп при фиксированных прогнозах. При менее чем 20 группах интервал не приводится.\n',
 f'В ProcessBench опубликована уже готовая поправка Холма: основное семейство — {z["primary_hypotheses"]} гипотез; остальные проверки имеют отдельное поисковое семейство. p вычислены заранее выбранным приближением через bootstrap-SE и Student t. Индивидуальный интервал не является одновременно скорректированным интервалом. В Lean полное семейство ({reg["primary_family_size"]} гипотез) пока не готово: частичная семья не пересчитывается, окончательных решений по ней нет.\n',
 "Локализация здесь **ретроспективная**, с доступом ко всему доказательству. AUROC наличия ошибки и префиксная диагностика — отдельные задачи; их нельзя читать как гарантии своевременной тревоги.\n",
 "## ProcessBench: отдельные правила\n"]
 rows=[]
 for k in keys:
  l=primary(model(k))
  rows.append([short(k),l,*[fmt(met(k,l,"pb",a),True,True) for a in ["w","sD","absD","h","weak"]]])
 lines.append(tab(["Читающая модель","Слой","Норма w, Hit [CI]","Проекция sD, Hit [CI]","Модуль sD, Hit [CI]","Состояние h, Hit [CI]","Слабые метки, Hit [CI]"],rows))
 c=p1ctx[0];l=c["layer"];k=c["model"]
 lines.append(f'Оценочная популяция: {c["attempts"]} решений, из них {c["failed"]} ошибочных; {c["groups"]} групп всего и {met(k,l,"pb","w")["groups"]} групп в локализации. Отдельный PRM даёт {fmt(met(k,l,"pb","prm"),True,True)}% Hit, позиционное правило — {fmt(met(k,l,"pb","position"),True,True)}%, равномерный уровень — {fmt(met(k,l,"pb","uniform"),True,True)}%. Эти общие контролы не меняются при смене читающей модели.\n')
 lines+=["![ProcessBench: нормы, проекции и обученный локализатор](processbench.png)\n",
 "Слабая метка — наличие процессной ошибки во всём решении, а не только правильность финального ответа. Её место не передаётся обучению направления. Лучший основной слой после просмотра результатов не выбирался.\n",
 "## ProcessBench: обученный локализатор\n"]
 rows=[]
 for k in keys:
  l=primary(model(k))
  def hn(a):return fmt(met(k,l,"pb",a,sec="localization"),True)+" / "+fmt(met(k,l,"pb",a,"nll","localization"))
  rows.append([short(k),hn("baseline"),hn("w"),hn("sD"),hn("h"),hn("hd")])
 lines.append(tab(["Модель","B: Hit / NLL","+w: Hit / NLL","+sD: Hit / NLL","+h: Hit / NLL","+h и sH: Hit / NLL"],rows))
 rows=[]
 for k in keys:
  l=primary(model(k))
  for contrast in ["sD-baseline","sD-w"]:
   h=con(k,l,"pb",contrast);n=con(k,l,"pb",contrast,"nll")
   rows.append([short(k),contrast,fmt(h,True,True),fmt(n,False,True),hp(h),hp(n),h.get("holm_family_size","—") if h else "—"])
 lines.append(tab(["Модель","Контраст","ΔHit, п.п. [CI]","Выигрыш NLL [CI]","Holm-p Hit","Holm-p NLL","Размер семьи"],rows))
 lines.append("sD−baseline: добавка проекции к B; sD−w: замена добавленной нормы на проекцию при том же B. Положительный выигрыш NLL равен NLL базы сравнения минус NLL нового варианта.\n")
 ds=[r for r in z["decisions"] if r.get("primary_layer") and r["slice"]=="pooled" and r["source"]=="pb"]
 lines.append(tab(["Модель","Заранее заданное правило направленного сигнала","Правило полезности знака","Правило слабых меток"],[[short(r["model"]),str(r["directed_signal"]),str(r["sign_matters"]),str(r["weak_labels_work"])] for r in ds]))
 lines.append("False означает, что составное правило не выполнено; это не доказательство отсутствия информации. Проекция может быть полезна при обычном распределении: положительный результат локализации сам по себе не устанавливает тяжёлый хвост, Кестеновский механизм или причинное влияние направления.\n")
 lines.append("## Перенос направления Lean → ProcessBench\n")
 rows=[]
 for k in ["deepseek","goedel"]:
  l=primary(model(k))
  for src in ["pb","lean"]:
   rows.append([short(k),src,fmt(met(k,l,src,"sD"),True,True),fmt(met(k,l,src,"sD",sec="localization"),True),fmt(met(k,l,src,"sD","nll","localization")),fmt(con(k,l,src,"sD-w"),True,True)])
 lines.append(tab(["Модель","Источник направления","Argmax sD [CI]","B+sD Hit","B+sD NLL","B+sD минус B+w, п.п. [CI]"],rows))
 lines.append("В строках lean заморожены нормали, обученные на ProofNet; коэффициенты последующего локализатора оцениваются на ProcessBench вне фолда. Это не полностью замороженный перенос предиктора. Направления, обученные на ProcessBench, существенно точнее перенесённых нормалей в отдельных правилах. Слабый классификатор этих строк всё ещё обучен на ProcessBench.\n")
 lines.append("## ProcessBench: наличие ошибки и префиксы\n")
 rows=[]
 for k in keys:
  l=primary(model(k));pr=next(r for r in z["prefix"] if (r["model"],r["layer"],r["source"],r["slice"],r["statistic"])==(k,l,"pb","pooled","sD"));c=pr["c2"]["metrics"]
  rows.append([short(k),fmt(met(k,l,"pb","sD","auc","max_detection"),False,True),fmt(met(k,l,"pb","baseline","auc","detection")),fmt(met(k,l,"pb","sD","auc","detection"),False,True),fmt(c.get("prefix_hit"),True),fmt(c.get("control"),True),fmt(c.get("delta"),True,True)])
 lines.append(tab(["Модель","AUROC max sD [CI]","AUROC B","AUROC B+sD [CI]","Рекорд на отказе C2, %","Контроль C2, %","Контраст C2, п.п. [CI]"],rows))
 lines.append("C2 использует известное место отказа, исключает первый шаг и сравнивает его с той же позицией в подходящих доказательствах, падающих позже. Это диагностический анализ, а не потоковый прогноз. AUROC выше относится к наличию ошибки во всём решении.\n")
 lines.append("## Lean: завершённые основные ячейки\n")
 selected=[p for p in primary_packs if p["context"]["section"] in ["2A","2B"]]
 selected.sort(key=lambda p:(p["context"]["model"],p["context"]["dataset"],p["context"]["direction_source"]))
 rows=[]
 for p in selected:
  c=p["context"];ct=p["data"]["counts"]
  rows.append([short(c["model"]),c["dataset"],c["direction_source"],ct["attempts"],ct["failed"],pm(p,"w")["groups"],fmt(pm(p,"w"),True,True),fmt(pm(p,"sD"),True,True),fmt(pm(p,"baseline",sec="localization"),True),fmt(pm(p,"sD",sec="localization"),True)])
 lines.append(tab(["Модель","Набор","Источник направления","Всего","С отказом","Групп для Hit","Argmax w [CI]","Argmax sD [CI]","B Hit","B+sD Hit"],rows))
 lines.append("Все показанные 2A-доказательства сгенерированы исходными DeepSeek/Goedel. native — направление обучено на том же наборе с OOF-защитой. ProofNet — замороженное направление с ProofNet, но коэффициенты локализатора оцениваются на целевом наборе вне фолда. Полностью замороженные предикторы вынесены отдельно ниже.\n")
 rows=[]
 for p in selected:
  c=p["context"]
  for co in ["sD-baseline","sD-w"]:
   rows.append([short(c["model"]),c["dataset"],c["direction_source"],co,fmt(pc(p,co),True,True),fmt(pc(p,co,"nll"),False,True)])
 lines.append(tab(["Модель","Набор","Источник","Контраст","ΔHit [индивидуальный CI]","Выигрыш NLL [индивидуальный CI]"],rows))
 lines.append("Эти индивидуальные интервалы уже рассчитаны; общая поправка Холма второй части ещё ожидает оставшиеся ячейки. На Putnam в этой серии сохранены только ошибочные попытки, поэтому AUROC наличия ошибки там не определён.\n")
 rows=[]
 for p in selected:
  if p["context"]["direction_source"]!="native":continue
  for sl in ["author_deepseek","author_goedel"]:
   c=p["context"];r=pm(p,"w",sl=sl)
   rows.append([short(c["model"]),c["dataset"],sl,r.get("groups") if r else "—",fmt(r,True),fmt(pm(p,"sD",sl=sl),True),fmt(pm(p,"baseline",sec="localization",sl=sl),True),fmt(pm(p,"sD",sec="localization",sl=sl),True)])
 lines.append("### Раздельно по автору доказательства\n")
 lines.append(tab(["Читающая модель","Набор","Автор","Групп Hit","w Hit","sD Hit","B Hit","B+sD Hit"],rows))
 lines.append("### Междоменный и полностью замороженный перенос\n")
 rows=[]
 for p in primary_packs:
  c=p["context"]
  if c["section"] not in ["cross","frozen"]:continue
  rows.append([short(c["model"]),c["dataset"],c["direction_source"],c["coefficient_mode"],fmt(pm(p,"sD"),True,True),fmt(pm(p,"baseline",sec="localization"),True),fmt(pm(p,"sD",sec="localization"),True),fmt(pc(p,"sD-baseline"),True,True)])
 lines.append(tab(["Модель","Цель","Источник","Коэффициенты","Argmax sD [CI]","B Hit","B+sD Hit","ΔHit [CI]"],rows))
 lines.append("target_OOF использует целевые обучающие фолды для коэффициентов. В frozen-постановке направление, стандартизация, регуляризация, коэффициенты и позиционный предиктор заморожены по ProofNet. Эти режимы отвечают на разные вопросы.\n")
 lines.append("## Контроль ProcessBench: равномерное и позиционное правила\n")
 u=read(ROOT/"runs/rebuttal_22Kj_processbench_uniform_20261115_v1/metrics.json")
 ur=[];uc=[]
 for modelkey,slices in u["models"].items():
  for sl,block in slices.items():
   ur.extend(dict(model=modelkey,slice=sl,method=m,**r) for m,r in block["rates"].items())
   uc.extend(dict(model=modelkey,slice=sl,contrast=m,**r) for m,r in block["contrasts"].items())
 rows=[]
 for mk,slices in u["models"].items():
  for sl,b in slices.items():
   rows.append([mk,sl,b["support"]["attempts"],b["support"]["groups"],*[f'{100*b["rates"][a]["equal_group"]:.2f}' for a in ["jump","surprisal","prm","uniform","first","last","position_oof"]]])
 lines.append(tab(["Серия","Срез","Попыток","Групп","Jump","Surprisal","PRM","Uniform","Первый","Последний","Позиционный OOF"],rows))
 lines.append("E15 — Qwen2.5-7B-Instruct; E16 — Qwen2.5-1.5B-Instruct. Все точности — проценты с равными весами групп. Позиционный предиктор выбирает моду первой ошибки по корзинам длины; обучение раздельно внутри каждого среза на других задачах.\n")
 lines.append(tab(["Серия","Контраст pooled","ΔHit, п.п. [CI]"],[[r["model"],r["contrast"],fmt(r,True,True)] for r in uc if r["slice"]=="pooled"]))
 lines.append(f'Архивный контроль: **{u["reproduction"]["status"]}**. Повторно воспроизведены оценки и интервалы архивных правил. В обеих читающих моделях скачок выше равномерного уровня, но ниже позиционного предиктора. Относительно surprisal индивидуальные интервалы pooled включают ноль. Значит, превышение равномерного уровня нельзя само по себе считать добавочной ценностью относительно позиционного контроля.\n')
 lines.append("## Хвостовые проверки: где расчёт остановлен и почему\n")
 t=read(ROOT/"runs/rebuttal_local_tails_20261115_v1/metrics.json")
 pt=read(ROOT/"runs/rebuttal_projection_tails_20261115_v1/metrics.json")
 lines.append(tab(["Серия","Синтетических наборов","Обязательная проверка","Новые реальные исходы"],[
 ["Локальные хвосты",t["total_simulated_datasets"],t["gate"]["status"],t["gate"]["real_data_verdict"]],
 ["Хвосты проекций",pt["completed_synthetic_datasets"],"A: "+pt["gateA"]["status"]+"; B: "+pt["gateB"]["status"],pt["real_projection_outcomes_computed"]]]))
 lines.append(f'Локальные хвосты: калибровка не пройдена в {t["gate"]["failed_main_combinations"]} из {t["gate"]["total_main_combinations"]} основных сочетаний; проблемные генераторы — '+", ".join(sorted({r["generator"] for r in t["gate"]["reasons"]}))+". Не удалось надёжно трактовать локальный параметр как универсальный асимптотический индекс на коротких наблюдаемых окнах.\n")
 fails=[r for r in pt["gateB"]["failures"] if r.get("check")=="type_I_inflation"]
 lines.append(tab(["Синтетическая популяция","Истинный механизм","Сравнение","Ложных отклонений / повторов","Частота, %","99% Monte Carlo CI"],[[r["cell"],r["case"],r["test"],str(r["rejections"])+" / "+str(r["reps"]),f'{100*r["rate"]:.2f}',f'[{100*r["mc99"][0]:.2f}; {100*r["mc99"][1]:.2f}]'] for r in fails]))
 lines.append("Для хвостов проекций демонстрация маскировки нормой прошла, но на истинном скалярном Кестене локальные сравнения завышают частоту отклонений; проверка мощности против диагональной альтернативы также не прошла. Числа выше относятся к отдельным сравнениям, а не к ошибке первого рода полного объединённого правила. По заранее установленному правилу новые реальные хвостовые исходы не вычислялись. Это результат проверки применимости метода, а не отрицательный результат о распределении реальных состояний.\n")
 lines.append("## Что ещё считается\n")
 lines.append(tab(["Модель","Готово статистических блоков / запланировано в созданном плане","Основных ячеек готово / всего"],[[short(r["model"]),str(r["completed_statistics"])+" / "+str(r["planned_statistics"] if r["planned_statistics"] is not None else "план ещё не создан"),str(r["completed_primary"])+" / "+str(r["planned_primary"])] for r in model_status]))
 lines.append(tab(["Новый автор","Назначено генераций","Сохранено генераций","Проверено Lean"],[[short(r["model"]),r["assigned"],r["generated"],r["verified"]] for r in own]))
 lines.append("Статус диспетчера на момент снимка: "+json.dumps(mgr.get("alerts"),ensure_ascii=False)+" (список сигналов о проблемах). Физическая очередь и ожидающие стадии: [status.json](status.json). Диспетчер продолжает зарегистрированную серию; собственные генерации 2B и чтение чужих доказательств 2A не смешиваются. Подготовка отчёта не меняет и не останавливает задания.\n")
 lines.append("## Ограничения воспроизводимости и сопоставления\n")
 lines.append("- Основные ProcessBench-состояния Qwen1.5B/7B взяты из сохранённых E16/NNG_B2: новый BF16 forward численно не воспроизвёл архив даже при тех же токенах и ревизии. Причина не установлена; допуск не ослаблялся. Новые дополнительные слои используют собственные новые скоры.\n- Основные слои DeepSeek/Goedel сохраняют архивные индексы 14/17; буквальные средние слои 15/18 считаются дополнительно. Индексы zero-based.\n- Группы Lean канонизированы по задачам и одинаковым формальным утверждениям. Калибровка 2A использует отдельные проверенные miniF2F; это отличается от старых популяций. Нельзя парно вычитать новые цифры из исторической таблицы геометрии.\n- Разложение на направленную и перпендикулярную части относится к сырому d; отбелённая норма w имеет другое преобразование. Незначимость длины перпендикулярной части не означает отсутствия информации в полном векторе.\n- При argmax и условном логите смещение b сокращается. Успех h не доказывает существование универсального порога расстояния до плоскости.\n- Новые генераторы DeepSeek-V1.5/Goedel-SFT используют явно расширенное окно 12 288 при исходном 4096. Это отмеченная в протоколе экстраполяция, не штатная поддержка длины.\n")
 paper=read(PUB/"paper_inspection/metrics.json");probe=read(PUB/"probe.json")
 paperpub=dict(pdf_sha256=paper["pdf_sha256"],pdfs=probe["pdf"],archives=[dict(file=a["file"],sha256=a["sha256"],files=a["files"],references=a["tex"],compile=a.get("compile")) for a in paper["archives"]],exact_current_pdf_source_identified=False)
 save(DEST/"paper_inventory.json",paperpub)
 lines.append("## PDF статьи и TeX-проект\n")
 lines.append("Найден полный по структуре проект extreme_value_reasoning_failure_revised_v4_latex: main.tex, sections.tex, app_proofs.tex, app_rest.tex, refs.tex, рисунок и стили ICLR. Все явно подключаемые файлы на месте. Также найден iclr-latex-source-v8.zip с main.tex, appendix.tex, refs.bib и рисунком.\n")
 prows=[]
 for name,v in probe["pdf"].items():
  inf=v["pdfinfo"]
  def field(key):
   m=re.search(r"^"+re.escape(key)+r":\s*(.+)$",inf,re.M);return m.group(1) if m else "—"
  prows.append([name,field("Pages"),field("CreationDate"),v["extract_exit"]])
 lines.append(tab(["PDF","Страниц","Дата создания из PDF metadata","Извлечение текста: код выхода"],prows))
 lines.append("Последний скачанный 49433_An_Extreme_Value_Perspec (2).pdf отличается от v4: уже абстракты содержат разные формулировки и наборы результатов. Архив v8 тоже отличается текстом абстракта и введения. Точный TeX-исходник именно скачанного PDF пока не установлен. Сборка TeX не проверена: на выделенном CPU-узле отсутствует pdflatex; наличие зависимостей проекта проверено отдельно. Полные тексты рукописи не включены в эту публикацию отчёта.\n")
 lines.append("## Проверки и файлы\n")
 v=read(PUB/"validation/metrics.json")
 lines.append(tab(["Команда","Код выхода","Лог"],[[r["command"],r["exit_code"],"[Лог](validation/"+r["log"]+")"] for r in v["checks"]]))
 lines.append("Проверки выполнялись через Slurm в отдельной копии опубликованного исходного кода. Ненулевой код не означает успешную проверку. При наличии пропусков внешних Lean/ML-тестов их причины сохранены в логах. Метрики этого отчёта сверены с хешами исходных manifests; научные исходы не пересчитаны.\n")
 lines.append("- [Метрики, которые использованы в основных таблицах](metrics.json).\n- [Все ProcessBench-метрики, CSV.gz](part1_metrics.csv.gz); [все контрасты, CSV.gz](part1_contrasts.csv.gz).\n- [Все готовые Lean-метрики, CSV.gz](part2_metrics.csv.gz); [контрасты, CSV.gz](part2_contrasts.csv.gz). Здесь также дополнительные слои, срезы авторов и полностью замороженный перенос.\n- [ProcessBench: контролы](processbench_controls.csv), [их контрасты](processbench_contrasts.csv).\n- [Хвостовая калибровка](tail_calibration.json), [исходные протоколы](protocols), [манифест](manifest.json), [генератор отчёта](generate_report.py).\n")
 lines.append("## Где лежат предыдущие отчёты\n")
 lines.append("- [Общий отчёт до новой серии](../complete_20261115/).\n- [Surprisal и его изменение: ответ wDaH](../rebuttal_wDaH_surprisal_change_20261115_v1/).\n- [Проверка модели шума считывания](../rebuttal_noise_20261115_v1/).\n- [Устройство локализатора](../localizer_explained_20261113/), [сводка локализации и потоковых постановок](../localizer_daily_20261113/).\n- [Позиции максимумов, ошибок и поправка на длину](../peak_error_distributions_20261111/).\n\nСерверные первоисточники нового отчёта: runs/models_projections_20261115_v1; runs/rebuttal_22Kj_processbench_uniform_20261115_v1; runs/rebuttal_local_tails_20261115_v1; runs/rebuttal_projection_tails_20261115_v1. Манифест перечисляет точные файлы и SHA-256.\n")
 textout("REPORT_RU.md","\n".join(lines))
 csvout("part1_metrics.csv.gz",z["metrics"],True);csvout("part1_contrasts.csv.gz",z["contrasts"],True)
 csvout("part2_metrics.csv.gz",ms,True);csvout("part2_contrasts.csv.gz",cs,True)
 csvout("processbench_controls.csv",ur);csvout("processbench_contrasts.csv",uc)
 selected_p1=[r for r in z["metrics"] if r["slice"]=="pooled" and r["layer"]==primary(model(r["model"])) and not r["method"].startswith("random")]
 selected_p1c=[r for r in z["contrasts"] if r["slice"]=="pooled" and r["layer"]==primary(model(r["model"])) and r["contrast"] in ["sD-baseline","sD-w","sD-absD","sD-position"]]
 selected_p2=[r for r in ms if r["slice"]=="pooled" and r["layer"]==primary(model(r["model"])) and r["method"] in ["w","sD","h","hd","baseline","uniform","position"]]
 selected_p2c=[r for r in cs if r["slice"]=="pooled" and r["layer"]==primary(model(r["model"])) and r["contrast"] in ["sD-baseline","sD-w"]]
 save(DEST/"metrics.json",dict(snapshot=status,part1=dict(contexts=p1ctx,metrics=selected_p1,contrasts=selected_p1c,decisions=ds,primary_hypotheses=z["primary_hypotheses"]),part2=dict(contexts=[dict(context=p["context"],layer=p["layer"],counts=p["data"]["counts"]) for p in primary_packs],metrics=selected_p2,contrasts=selected_p2c,Holm_status="pending_full_family"),processbench_reproduction=dict(status=u["reproduction"]["status"],checks=len(u["reproduction"]["checks"]))))
 save(DEST/"tail_calibration.json",dict(local=t,projection={k:v for k,v in pt.items() if k!="runs"}))
 (DEST/"protocols").mkdir(exist_ok=True)
 for name in ["protocol.md","protocol_A1.md","protocol_A2.md","protocol_A3.md","protocol_P2.md","protocol_P2_A1.md"]:
  if (OUT/name).exists():filecopy(OUT/name,"protocols/"+name)
 for name,src in [("local_tails","rebuttal_local_tails_20261115_v1"),("projection_tails","rebuttal_projection_tails_20261115_v1"),("processbench_controls","rebuttal_22Kj_processbench_uniform_20261115_v1")]:
  filecopy(ROOT/"runs"/src/"protocol.md","protocols/"+name+".md")
 (DEST/"validation").mkdir(exist_ok=True)
 for f in (PUB/"validation").glob("*"):
  if f.is_file():filecopy(f,"validation/"+f.name)
 filecopy(Path(__file__),"generate_report.py")
 fig,axes=plt.subplots(1,2,figsize=(12,4.5))
 for ax,sec,arms in [(axes[0],"standalone",["w","sD"]),(axes[1],"localization",["baseline","sD"])]:
  for arm in arms:
   vals=[100*met(k,primary(model(k)),"pb",arm,sec=sec)["value"] for k in keys]
   ax.plot(range(len(keys)),vals,"o-",label=arm)
  ax.set_xticks(range(len(keys)),["Q0.5","Q1.5","Q7","Q14","Q32","DS7","G8"]);ax.set_ylabel("Exact localization (%)");ax.legend();ax.grid(alpha=.2)
 axes[0].set_title("Standalone rules");axes[1].set_title("Conditional localizer: baseline vs baseline+sD")
 fig.tight_layout();fig.savefig(DEST/"processbench.png",dpi=150);plt.close(fig)
 # Scientific values are copied without recomputing estimates, CIs or multiplicity.
 assert all(r.get("holm_p") is None for r in cs),"Unexpected partial-family Holm"
 assert all((r.get("ci95") is None) or r.get("groups",0)>=20 for r in z["metrics"]+ms)
 assert len({p["context"]["id"]+":"+str(p["layer"]) for p in packs})==len(packs)
 finish(DEST,dict(kind="read_only_snapshot_and_report",part1_final=True,part2_final=False,source_report_root=str(OUT),metrics_not_refitted=True))
 print("PUBLICATION_READY",str(DEST),len(packs),len(ready&regids),flush=True)
if __name__=="__main__":main()
