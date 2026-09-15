from pathlib import Path
import json,csv,collections,datetime,hashlib,html,re,platform,os,base64
P=Path(__file__).parent
S=json.loads((P/'summary.json').read_text())
N={'deepseek':'DeepSeek','goedel':'Goedel','kimina':'Kimina'}; M=list(N)
def rows(name): return list(csv.DictReader((P/name).open(encoding='utf-8-sig')))
E=rows('p1_all_estimates.csv'); D=rows('p1_descriptive.csv'); A=rows('main_attempts_snapshot.csv'); PA=rows('pilot_attempts.csv')
def num(v,d=2):
 if v is None or v=='': return '—'
 try:return f'{float(v):.{d}f}'
 except (TypeError,ValueError):return str(v)
def pc(n,d):return num(100*n/d)+'%'
def pair(n,d):return f'{n}/{d} ({pc(n,d)})'
def table(h,rs):
 return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']+['| '+' | '.join(str(x).replace('|','/').replace('\n',' ') for x in r)+' |' for r in rs])
out=[]
def p(x=''):out.append(x.strip()+'\n')
def title(x):p('**'+x+'**')
def tab(h,r):p(table(h,r))
def pic(path,alt):p('!['+alt+']('+path+')')
stamp=datetime.datetime.fromisoformat(S['captured_utc'])
msk=stamp.astimezone(datetime.timezone(datetime.timedelta(hours=3))).strftime('%d.%m.%Y %H:%M:%S МСК')
total=len(A); cats=collections.Counter(r['category'] for r in A)
assert total==sum(S['models'][m]['main']['n'] for m in M)
assert all(int(float(r['n_pre']))==int(float(r['t_star'])) for r in A if r['category']=='localized_tactic_failure')
protos={m:json.loads((P/'evidence'/m/'protocol.json').read_text()) for m in M}
title('P1: результаты, пригодность задач и примеры ошибок')
p('Срез: **'+msk+'**. Основная проверка продолжается; это зафиксированный срез, а не окончание всей серии.')
p('**Главный результат:** завершённый пилот пока не позволяет подтвердить или опровергнуть P1 — различие хвостов изменений внутренних состояний у принятых и отвергнутых доказательств. Основная проверка показывает, что модели решают существенную долю задач. Объяснение «весь набор слишком сложен» данными не поддерживается.')
p(f'Записано {total} из 20 016 исходов основной проверки ({pc(total,20016)}); принято {cats["verified"]}, локализовано отказов {cats["localized_tactic_failure"]}. На момент снимка итогового main/analysis/metrics.json нет ни у одной модели. Проценты основной серии и оценки P1 из пилота имеют разные знаменатели.')
p('Полные данные: [summary.json](summary.json), [все оценки P1](p1_all_estimates.csv), [описательная статистика](p1_descriptive.csv), [устойчивость по k](p1_stability.csv), [исходы основной проверки](main_attempts_snapshot.csv), [происхождение файлов](sources.json). Пустое числовое поле CSV означает отсутствие оценки, а не ноль.')
title('1. Проценты принятых доказательств и локализованных отказов')
p('Попытка — один ответ на одну задачу при заданной температуре. Несколько попыток одной задачи зависимы. Процент принятых попыток отличается от процента задач с хотя бы одним успешным ответом.')
p('verified — доказательство, принятое конвейером Lean для доверенного исходного утверждения при действовавшей политике допустимых доказательств/аксиом. localized_tactic_failure — доказательство отвергнуто, а последовательная проверка позволила указать первый отказавший блок. Категории не пересекаются. Локализованный отказ не является дополнительным верным доказательством.')
p('Их объединение — доля ответов с нужным типом исхода. Для P1 дополнительно требуются корректное сопоставление блоков с токенами, извлечение состояний, разделение calibration/evaluation и достаточное число независимых задач.')
tab(['Модель','Исходов / 6672','verified','Локализованный отказ','Объединение'],
 [[N[m],str(S['models'][m]['main']['n'])+' / 6672',pair(S['models'][m]['main']['categories']['verified'],S['models'][m]['main']['n']),pair(S['models'][m]['main']['categories']['localized_tactic_failure'],S['models'][m]['main']['n']),pair(S['models'][m]['main']['categories']['verified']+S['models'][m]['main']['categories']['localized_tactic_failure'],S['models'][m]['main']['n'])] for m in M]+[['Все',str(total)+' / 20016',pair(cats['verified'],total),pair(cats['localized_tactic_failure'],total),pair(cats['verified']+cats['localized_tactic_failure'],total)]])
p('Знаменатель — уже записанные исходы модели. Непроверенные ответы не считаются ни успехами, ни ошибками. Подмножества задач пока различаются; ранжировать модели только по этой таблице нельзя.')
pic('figures/main_outcomes.png','Исходы основной проверки на момент снимка')
order=['verified','localized_tactic_failure','generation_truncation','parse_error','context_statement_mismatch','timeout_resource','sorry_invalid_proof','terminal_unsolved_goals','unsupported_segmentation','infrastructure_error']
title('2. Все категории исходов основной проверки')
tab(['Категория']+[N[m] for m in M]+['Всего'],[[c]+[S['models'][m]['main']['categories'].get(c,0) for m in M]+[cats[c]] for c in order])
p('generation_truncation — обрезанная генерация; parse_error — невозможность разобрать ответ; context_statement_mismatch — несовпадение с доверенным контекстом/утверждением; timeout_resource — ограничение времени или ресурсов; terminal_unsolved_goals — оставшиеся цели; unsupported_segmentation — неподдержанная структура разбиения; infrastructure_error — инфраструктурное исключение.')
p('sorry_invalid_proof — составная категория, которая может включать недопустимую для конкретной версии проверки зависимость от аксиомы, а не только буквальный sorry или математически неверное утверждение. Нельзя объявить все такие ответы математическими ошибками. В архивном пилоте Kimina есть 8 исключений по политике native-доказательств; переименовывать их по более поздней политике без согласованной повторной проверки нельзя.')
title('3. Подходит ли сложность задач')
nt=S['matched_tasks']; den=nt*16
p(f'Для сопоставимого описания выделена **{nt} одинаковая задача**, у каждой модели есть все 16 исходов: по 8 при T=0.6 и T=1.0. Это {den} попыток на модель. Выборка зависит от завершения проверки и не является случайной выборкой всех задач; выводы ниже описательные.')
tab(['Модель','Принятые попытки','Локализованные отказы','Объединение','Задач с ≥1 успехом из 16'],
 [[N[m],pair(S['matched_cohort'][m]['categories']['verified'],den),pair(S['matched_cohort'][m]['categories']['localized_tactic_failure'],den),pair(S['matched_cohort'][m]['categories']['verified']+S['matched_cohort'][m]['categories']['localized_tactic_failure'],den),pair(S['matched_cohort'][m]['tasks_solved_at_least_once'],nt)] for m in M])
p('Последний столбец — наблюдаемое покрытие задач смешанным набором температур. Это не опубликованный benchmark pass@16 другой работы. Несколько ответов на одно утверждение зависимы; обычный интервал, считающий все попытки независимыми, был бы неоправданно узким.')
fs=S['family_statistics']; families=list(dict.fromkeys(r['family'] for r in fs))
tab(['Семейство','Задач','Попыток на модель']+[N[m]+': verified' for m in M],
 [[f,next(r['tasks'] for r in fs if r['family']==f),next(r['attempts'] for r in fs if r['family']==f)]+[pair(next(r['verified'] for r in fs if r['family']==f and r['model']==m),next(r['attempts'] for r in fs if r['family']==f and r['model']==m)) for m in M] for f in families])
p('Семейства взяты из метаданных проекта, это не независимая шкала математической трудности. Но различия велики: mathd_algebra существенно легче IMO по наблюдаемой успешности. В IMO у Goedel обрезано '+str(next(r['truncated'] for r in fs if r['family']=='imo' and r['model']=='goedel'))+' из '+str(next(r['attempts'] for r in fs if r['family']=='imo' and r['model']=='goedel'))+' ответов. Обрезание не доказывает невозможность решения с другим бюджетом.')
p('**Оценка:** набор подходит для изучения смеси успехов и отказов. Для P1 важнее получить достаточно различных задач в каждой группе. Я бы сохранил смешанную сложность, анализировал семейства и типы отказов отдельно, а бюджет токенов проверял на заранее выбранной подвыборке с одинаковыми условиями для моделей. Подбирать только лёгкие задачи до получения желаемого хвоста нельзя.')
p('[Полная таблица семейств, включая обрезания и отказы](matched_task_families.csv).')
title('4. Как часто у отказа есть успешный pre')
p('pre — блоки, успешно выполненные Lean до первого отказа. Отказ в первом блоке может быть точно локализован, но pre тогда пуст. Ниже обе температуры и обе роли основной проверки вместе; это не выборка P1.')
tab(['Модель','Локализованных отказов','С непустым pre','Доля среди всех исходов'],
 [[N[m],S['models'][m]['main']['categories']['localized_tactic_failure'],pair(S['models'][m]['main']['local_with_pre'],S['models'][m]['main']['categories']['localized_tactic_failure']),pair(S['models'][m]['main']['local_with_pre'],S['models'][m]['main']['n'])] for m in M])
p('Различие долей зависит от стиля вывода, длины и вложенности первого блока и сегментации. Оно не является прямой мерой глубины рассуждения. Проверено: для локализованных отказов число успешных предшествующих блоков равно нулевому индексу первого отказа.')
title('5. Что проверяет P1 и какие величины измеряются')
p('Для задачи i, попытки a и блока t берём вектор Xᵢₐₜ ∈ ℝᵈ на последнем токене блока после выбранного слоя модели. Xᵢₐ₀ — состояние последнего токена prompt. Здесь математические блоки нумеруются с 1; в исходных файлах t и t_star нумеруются с 0.')
p('Приращение ΔXₜ = Xₜ−Xₜ₋₁. Из него и состояний строятся три скалярных измерения:')
p('1. raw: Zₜ = ‖ΔXₜ‖₂.\n2. whitened: Zʷₜ = √((ΔXₜ−μ)ᵀΣ⁻¹(ΔXₜ−μ)). μ и регуляризованная ковариация Σ оцениваются по принятым трассам отдельных калибровочных задач.\n3. innovation: Zⁱⁿⁿₜ = ‖Xₜ−ÂXₜ₋₁−ĉ‖₂. Â и ĉ — линейный прогноз, обученный с ridge-регуляризацией на калибровке. Это остаток прогноза следующего состояния.')
p('Whitening учитывает неодинаковые масштабы и корреляции направлений. Сама нормировка не гарантирует качество ковариации на малой калибровке и не превращает конечные данные в доказательство тяжёлого хвоста.')
p('t* — первый отказавший блок. verified содержит все шаги принятых доказательств; refuted_all — все шаги пригодных отвергнутых трасс; pre: t<t*; at: t=t*; post: t>t*; at_post: t≥t*. Группы перекрываются: refuted_all = pre ∪ at ∪ post, at_post = at ∪ post. Все шесть строк нельзя складывать как независимые наблюдения.')
p('После t* текст уже существует: генерация шла без обратной связи от Lean. Внутренние состояния можно измерить повторным проходом по сохранённым токенам — teacher forcing. Но последовательная проверка не выполняла post: его статус unreached. Это не утверждение, что каждая такая строка сама по себе неверна.')
p('P1 ожидает более тяжёлый хвост у отвергнутых трасс, особенно at_post, чем у verified. Ожидаемый рисунок: verified ≈ pre < at_post. Совпадение максимума скачка с первым отказом — отдельный вопрос P2.')
p('Параметр γ описывает форму экстремального хвоста. Для регулярно меняющегося степенного хвоста P(Z>z) ≈ L(z)z^(−1/γ), γ>0, где L медленно меняется. γ=0 и γ<0 соответствуют другим областям притяжения экстремумов; γ<0 предполагает конечную правую границу в этой модели. Параметр порядка проекта ξ=max(γ,0) не следует путать с приращением ΔXₜ.')
p('Hill, moment и GPD оценивают один хвостовой параметр разными методами. Hill усредняет логарифмы отношений k крупнейших наблюдений к порогу и не выдаёт отрицательное значение. Moment допускает отрицательные оценки. GPD подгоняет обобщённое распределение Парето к превышениям порога. k — число хвостовых наблюдений, не число задач. Положительный Hill сам по себе не доказывает степенной хвост; отрицательный нестабильный moment на нескольких задачах не доказывает алгоритмический режим.')
p('Для конечной нейросети это проверка промежуточного диапазона масштабов, а не буквальное установление неограниченного распределения при z→∞. Даже устойчивое различие оценок не является само по себе причинным доказательством внутреннего алгоритма.')
title('6. Дизайн и поток данных завершённого пилота')
tab(['Метка','Точная модель','Блоки, с 1','Основной блок'],
 [[N[m],protos[m]['model_id'],', '.join(str(x+1) for x in protos[m]['layers']),protos[m]['primary_layer']+1] for m in M])
p('Данные: cat-searcher/minif2f-lean4, revision 70a1249ce240667f6bcdd1ccd62f847f0e065d57. Основная серия: 417 задач × 2 температуры × 8 попыток = 6672 ответа на модель, всего 20 016. Пилот: 20 задач × 2 температуры × 2 попытки = 80 ответов на модель, всего 240. T∈{0.6,1.0}, top_p=1, максимум 8192 новых токенов.')
tab(['Модель','Генераций','Токенов','Размечено','Извлечено','Измерено','verified','Локализованных','Необъяснённых расхождений'],
 [[N[m]]+[S['models'][m]['pilot_flow'][k] for k in ['generation_attempts','generation_tokens','labelled_attempts','extracted_attempts','measured_traces']]+[S['models'][m]['pilot']['categories']['verified'],S['models'][m]['pilot']['categories']['localized_tactic_failure'],S['models'][m]['pilot_flow']['unexplained_disagreements']] for m in M])
p('Извлечено и измерено — счётчики этапов, не размер основной P1-выборки. P1 фильтрует evaluation и primary_eligible, затем фиксирует температуру, слой и измерение. Поэтому 80 ответов не превращаются в 80 трасс в каждой строке P1.')
tab(['Категория пилота']+[N[m] for m in M],[[c]+[S['models'][m]['pilot']['categories'].get(c,0) for m in M] for c in order if any(S['models'][m]['pilot']['categories'].get(c,0) for m in M)])
tab(['Роль: число различных задач']+[N[m] for m in M],[[r]+[len({a['problem_id'] for a in PA if a['model']==m and a['role']==r}) for m in M] for r in sorted({a['role'] for a in PA})])
p('Калибровочные задачи не входят в evaluation. Основная настройка: T=0.6, whitened, средний из трёх сохранённых слоёв. Вариации слоя, температуры и измерения — проверки чувствительности на связанных данных.')
title('7. Основные числа P1')
groups=['verified','refuted_all','pre','at','post','at_post']
tab(['Группа']+[N[m]+': шаги / трассы / задачи' for m in M],[[g]+[' / '.join(str(S['primary'][m]['P1'][g][k]) for k in ['n_steps','n_traces','n_tasks']) for m in M] for g in groups])
pic('figures/primary_counts.png','Число шагов в основной настройке P1')
p('У каждой модели pre опирается только на **2 независимые задачи**. Пилотная точечная подгонка начинается с 50 положительных шагов; ниже этого порога оценки отсутствуют. Это технический минимум пилота, не гарантия научной достаточности.')
tab(['Модель','Группа','Hill γ','Moment γ','GPD γ','Статус'],[[N[m],g]+[num(S['primary'][m]['P1'][g].get(k),6) for k in ['hill','moment','gpd']]+[S['primary'][m]['P1'][g]['fit_status']] for m in M for g in ['verified','pre','at_post','refuted_all']])
km=S['primary']['kimina']['P1']['refuted_all']
p(f'Единственная основная группа с точечной подгонкой — Kimina/refuted_all: {km["n_positive"]} шагов, {km["n_traces"]} трасс, {km["n_tasks"]} задачи; k={km["k"]}; задач в хвосте {km["tail_tasks"]}. Hill={num(km["hill"],9)}, moment={num(km["moment"],9)}. Интервал отсутствует. Разность γ_ref−γ_ver получить нельзя: γ_ver не оценён.')
p('GPD не дал пригодной оценки. Сырой результат оптимизатора γ='+num(km['gpd_fit']['gamma'],9)+' отклонён: '+km['gpd_fit']['message']+'. Его нельзя выдавать за успешно оценённый параметр.')
p('Выбор k: '+km['k_selection']['method']+'. Двойной bootstrap перешёл к запасному правилу: выборка слишком мала для двух стадий; диагностический KS-выбор дал k='+str(km['secondary_ks']['k'])+'. Увеличение числа bootstrap-повторов не создаёт новых независимых задач.')
p('Ниже описательные величины Zʷ. Их абсолютные масштабы не предназначены для прямого ранжирования моделей.')
pri=[r for r in D if r['temperature']=='0.6' and r['statistic']=='whitened' and r['variant']=='P1' and int(r['block_1based'])==protos[r['model']]['primary_layer']+1]
tab(['Модель','Группа','n','Среднее','SD','Медиана','q90','q95','Максимум'],[[N[r['model']],r['group'],r['n_steps']]+[num(r[k],3) for k in ['mean','std_sample','median','q90','q95','maximum']] for r in pri])
p('Среднее, квантили и максимум описывают наблюдавшиеся числа. Без неопределённости и анализа хвостового диапазона из них нельзя вывести наличие или отсутствие тяжёлого хвоста.')
title('8. Первый шаг, слой и измерение: чувствительность результатов')
tab(['Группа']+[N[m]+': шагов после удаления первого' for m in M],[[g]+[S['primary'][m]['P1_exclude_first'][g]['n_steps'] for m in M] for g in groups])
p('После удаления первого шага Kimina/refuted_all в основной настройке уменьшается с 54 до 48 наблюдений. Единственная подгонка исчезает из-за порога 50. Это показывает недостаточный запас данных, но не доказывает, что весь эффект вызван первым шагом.')
st=km['stability']
tab(['k','Hill','Moment'],[[k,num(st['hill'][j],6),num(st['moment'][j],6)] for j,k in enumerate(st['k'])])
pic('figures/primary_stability.png','Оценки Kimina/refuted_all в зависимости от k')
p('Moment меняется примерно от −1.81 до −0.61; доверительных полос нет. Одинаковый знак нескольких точек на тех же 3 задачах не заменяет независимую проверку.')
fitted=[r for r in E if r['hill']!='']
tab(['Модель','T','Блок','Измерение','Вариант','Группа','n','k','Hill','Moment','GPD'],
 [[N[r['model']],r['temperature'],r['block_1based'],r['statistic'],'без первого' if r['variant']=='P1_exclude_first' else 'все шаги',r['group'],r['n_steps'],r['k'],num(r['hill'],6),num(r['moment'],6),num(r['gpd'],6)] for r in fitted])
p(f'Здесь все {len(fitted)} строки с оценкой Hill из {len(E)} строк P1; они принадлежат Kimina/refuted_all. Все {len(E)} решений inconclusive, интервалов нет. В {len(E)-len(fitted)} строках недостаточно положительных шагов. GPD имеет пригодную точечную оценку в {sum(bool(r["gpd"]) for r in E)} строках.')
p('При T=0.6 знак moment зависит от слоя и измерения. Whitened на блоке 9 даёт '+num(next(r['moment'] for r in E if r['model']=='kimina' and r['temperature']=='0.6' and r['block_1based']=='9' and r['statistic']=='whitened' and r['variant']=='P1' and r['group']=='refuted_all'),6)+', на основном блоке 18 — '+num(km['moment'],6)+'. Нельзя выбрать удобную строку после просмотра результатов и выдать её за общее свойство модели.')
p('3 модели × 2 температуры × 3 слоя × 3 измерения = 54 настройки. В каждой 6 групп × 2 варианта = 12 строк; всего 648. Все строки, включая отсутствие оценок: [полное приложение](APPENDIX_FULL.md).')
title('9. Ограничения калибровки whitening')
cal={m:next(x for x in S['models'][m]['calibration'] if x['temperature']==0.6 and x['layer']==protos[m]['primary_layer']) for m in M}
tab(['Модель','Приращений','Задач','Размерность d','n/d','Число обусловленности'],[[N[m],cal[m]['calibration_increments'],cal[m]['calibration_tasks'],4096,num(cal[m]['n_over_d'],6),num(cal[m]['condition_number'],1)] for m in M])
p('Shrinkage=0.1 к изотропной ковариации. При n≪d ранг центрированной выборочной ковариации ≤n−1. Данные определяют лишь небольшое подпространство; обратимая нормировка существенно зависит от регуляризации.')
p('Следующий контроль относится к более ранним меткам lean_reverification_20260912, сохранён в runs/controls_20260913_local/pilot/.../whitening-01 и whitening-04. Он не смешивается с текущими долями verified. «Принятые шаги» здесь включают verified и успешный pre.')
wr=[]
for m in M:
 for v in ['01','04']:
  w=S['secondary_whitening_controls'][m][v]['variant']; a=w['threshold']['evaluation']['accepted_evaluation']
  wr.append([N[m],'те же задачи' if v=='01' else 'раздельные задачи',num(w['threshold']['tau'],3),pair(a['exceedances'],a['steps'])])
tab(['Модель','Данные для transform и порога','Порог τ','Превышения на принятых evaluation-шагax'],wr)
p('Порог — 99-й процентиль калибровки. При повторном использовании задач для transform и порога все принятые evaluation-шаги превысили его. Разделение задач уменьшило долю, но не установило 1%-ную частоту. Это свидетельствует о плохом переносе такой калибровки в малом пилоте. Это диагностика порога детекции, не самостоятельный результат P1.')
title('10. Синтетическая проверка процедуры P1')
p('Отдельные искусственные данные с известной истиной, по 200 наборов на сценарий. Они проверяют процедуру, не языковые модели.')
tab(['Сценарий','Интервал доступен','Покрытие истинной разности','Положительное решение P1','95% MC-интервал частоты решения'],
 [[name,pair(d['availability']['successes'],d['availability']['datasets']),pair(d['coverage_among_available']['successes'],d['coverage_among_available']['datasets']),pair(d['family_positive_rejection_all_datasets']['successes'],d['family_positive_rejection_all_datasets']['datasets']),'['+num(100*d['family_positive_rejection_all_datasets']['monte_carlo_ci95'][0])+'%; '+num(100*d['family_positive_rejection_all_datasets']['monte_carlo_ci95'][1])+'%]'] for name,d in S['p1_controls'].items()])
p('В tail_alternative положительное решение получено в 28/200 случаях: наблюдаемая мощность 14% для данной симуляции и настроек. В трёх других сценариях 0/200 не означает нулевую истинную вероятность: верхняя граница интервала около 1.83%. Процедура осторожная, но маломощная в проверенном сценарии. Нельзя переносить 14% на любые данные или считать отсутствие подтверждения опровержением.')
p('[Все первичные значения и интервалы покрытия](evidence/p1-controls.json).')
title('11. Два реальных доказательства с pre и первым отказом')
p('Примеры выбраны по интерпретируемости ошибки и наличию pre, а не случайно и не по попаданию скачка. completion.txt содержит исходный ответ; generated.lean — извлечённый formal-span без исправлений; checked.lean — доверенный заголовок плюс проверявшееся тело. Последний файл является материализацией проверявшегося кандидата.')
for e in S['examples']:
 title(N[e['model']]+' — '+e['trace_id'])
 p(f'T={e["temperature"]}, роль {e["role"]}, блоков {e["L"]}; pre={e["n_pre"]}; отказ в блоке {e["failure_step_1based"]}; post={e["n_post"]}. В исходных данных t_star={e["t_star_0based"]}.')
 if e['model']=='deepseek':
  p('Из f(x)=3√(2x−7)−8 нужно получить f(8)=1. Подстановка даёт 3√9−8=1. Первый блок успешно подставляет определение. Второй обращается к Real.sqrt_eq_iff_sq_eq, отсутствующей в использованной среде Mathlib. Ошибка не свидетельствует о неправильном вычислении √9.')
 else:
  p('Дано a₀=1, aₙ₊₁=∏ₖ₌₀ⁿ aₖ+4. Требуется aₙ−√aₙ₊₁=2 при n≥1. Lean принял a₁=5, a₂=9, a₃=49, a₄=2209. Модель записала a₅=4 874 049; на самом деле 1·5·9·49·2209+4=4 870 849, разница 3200. Это конкретная арифметическая ошибка.')
 p('Полный исходный формальный фрагмент генерации без исправлений:')
 p('~~~lean\n'+e['original_code'].strip()+'\n~~~')
 p('Первое сообщение последовательной проверки:')
 p('~~~text\n'+e['error'].strip()+'\n~~~')
 tab(['Блок','Область','Статус','Начало блока','raw','whitened','innovation'],[[a['step_1based'],a['region'],a['status'],a['tactic'].splitlines()[0],num(a['raw'],3),num(a['whitened'],3),num(a['innovation'],3)] for a in e['steps']])
 p('Шаг максимума: '+', '.join(k+' → '+str(v) for k,v in e['score_argmax_step_1based'].items())+'. Слой основной; у Kimina в этом примере T=1.0, это проверка чувствительности, не основная ячейка T=0.6.')
 slug=e['slug']
 p('[Исходный ответ](examples/'+slug+'/completion.txt) · [Lean-фрагмент](examples/'+slug+'/generated.lean) · [Проверявшийся кандидат](examples/'+slug+'/checked.lean) · [Метки Lean](examples/'+slug+'/label.json) · [Блоки и измерения](examples/'+slug+'/steps.csv).')
pic('figures/example_trajectories.png','Две траектории: pre, первый отказ и продолжение')
p('У DeepSeek whitening дал максимум на ошибочном блоке 2; raw — на 1, innovation — на 3. У Kimina все три максимума на блоке 6 при ошибке на 5. Измерение получается после обработки текста блока и не является прогнозом до его генерации. Два выбранных примера не оценивают качество локализации; для этого нужен P2 на всех пригодных трассах.')
title('12. Выводы и следующие проверки')
p('**Установлено:** модели решают существенную долю задач; сложность и причины отказов неоднородны; есть реальные трассы с правильным префиксом; пилот позволяет измерять внутренние траектории. Результаты зависят от числа независимых задач, слоя, измерения, первого шага и калибровки.')
p('**Не установлено:** подтверждение или опровержение P1; более тяжёлый хвост у неверных доказательств; алгоритмический/эвристический механизм по знаку отдельной оценки; возможность надёжно прогнозировать будущую ошибку. Основной анализ не завершён, а независимых данных пилота недостаточно. Это не равнозначно выводу «гипотеза не работает».')
p('1. Завершить согласованную основную проверку, затем extraction → measurement → analysis. Сохранить версии среды и определения исходов; показать исключения до сравнения хвостов.\n2. Проверить объём verified, pre и at_post отдельно. Протокол основной серии требует минимум 200 шагов, 20 задач, 20 задач в хвосте, k≥20; 500 внешних и 200 внутренних bootstrap-повторов. Эти пороги не гарантируют мощность.\n3. Разбивать на более мелкие семантические блоки по синтаксису и состояниям Lean. Сохранить крупную и новую сетки и сравнить на тех же доказательствах; вложенные блоки не становятся независимыми задачами.\n4. Разделить задачи подгонки whitening и выбора порога, увеличить независимую калибровку, проверить обусловленность и заранее заданные варианты регуляризации.\n5. Учитывать семейство, длину и тип отказа. Новые независимые задачи полезнее дополнительных ответов на тех же двух задачах pre. Проверять влияние сложности и лимита на заранее фиксированных подвыборках.\n6. Оценить мощность на симуляциях с фактическими длинами трасс, количеством задач и зависимостью шагов; представить все три оценки, интервалы, выбор k и проверки чувствительности.')
title('13. Происхождение и состав архива')
p('Slurm job 8466254 читал сохранённые данные, считал описательные сводки и строил рисунки. Генерация, Lean replay и хвостовые подгонки не перезапускались. Все 648 счётчиков шагов и положительных значений сверены с deviations.parquet; проверены уникальность trace_id основного среза и согласованность pre с t_star.')
p('Большие журналы основной проверки продолжали дописываться: фиксированный срез представлен компактной таблицей, а не заявлением об неизменности всех исходных журналов. Пути, размеры, времена и SHA-256 прочитанных файлов сохранены в sources.json. Манифесты исходных пилотов — в evidence/<model>. Рабочее дерево сервера было dirty; отчёт является описательной сборкой из сохранённых артефактов, а не чистым повтором всех вычислений из одного коммита.')
tab(['Файл','Содержание'],[
 ['REPORT_RU.md / REPORT_RU.html','Отчёт с таблицами, доказательствами и рисунками'],
 ['APPENDIX_FULL.md','Все 648 строк оценок P1, включая отсутствие подгонки'],
 ['p1_all_estimates.csv','Настройки, группы, n, задачи, k, три оценки, статусы и диагностика GPD'],
 ['p1_descriptive.csv','648 групп: n, mean, sample SD, min, q25, median, q75, q90, q95, max'],
 ['p1_stability.csv','Все сохранённые сетки k для Hill и moment'],
 ['main_attempts_snapshot.csv / pilot_attempts.csv','Исходы попыток, задача, роль, температура, t_star и pre'],
 ['matched_task_families.csv','Сопоставимые семейства задач'],
 ['examples/','Исходные ответы, проверявшиеся кандидаты, метки и измерения'],
 ['evidence/','Первичные метрики, labels, parquet, калибровка, протоколы и манифесты'],
 ['summary.json / sources.json / report-manifest.json','Сводка, источники и контрольные суммы']])
md='\n'.join(out);(P/'REPORT_RU.md').write_text(md,encoding='utf-8')
ah=['Модель','T','Блок','Измерение','Вариант','Группа','Шаги','Трассы','Задачи','Задачи в хвосте','k','Hill','Moment','GPD','Статус']
ar=[[N[r['model']],r['temperature'],r['block_1based'],r['statistic'],r['variant'],r['group'],r['n_steps'],r['n_traces'],r['n_tasks'],r['tail_tasks'] or '—',r['k'] or '—',num(r['hill'],9),num(r['moment'],9),num(r['gpd'],9),r['fit_status']] for r in E]
(P/'APPENDIX_FULL.md').write_text('**Все оценки P1, '+msk+'**\n\nПилот. CI отсутствуют, решения inconclusive. — означает отсутствие оценки. P1_exclude_first удаляет первый блок каждой трассы.\n\n'+table(ah,ar)+'\n',encoding='utf-8')
def inline(t):
 t=html.escape(t);t=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',t)
 return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',t)
def render(lines):
 chunks=[];i=0
 while i<len(lines):
  line=lines[i]
  if not line.strip():i+=1;continue
  if line.startswith('~~~'):
   code=[];i+=1
   while i<len(lines) and not lines[i].startswith('~~~'):code.append(lines[i]);i+=1
   chunks.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>');i+=1
  elif line.startswith('| '):
   block=[]
   while i<len(lines) and lines[i].startswith('| '):block.append(lines[i]);i+=1
   heads=[x.strip() for x in block[0].strip('|').split('|')];body=[[x.strip() for x in z.strip('|').split('|')] for z in block[2:]]
   chunks.append('<div class="scroll"><table><thead><tr>'+''.join('<th>'+inline(x)+'</th>' for x in heads)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(x)+'</td>' for x in r)+'</tr>' for r in body)+'</tbody></table></div>')
  elif line.startswith('!['):
   match=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line);path=P/match.group(2)
   chunks.append('<figure><img alt="'+html.escape(match.group(1))+'" src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'"><figcaption>'+html.escape(match.group(1))+'</figcaption></figure>');i+=1
  elif line.startswith('**') and line.endswith('**') and line.count('**')==2:
   chunks.append('<p class="section">'+inline(line)+'</p>');i+=1
  else:chunks.append('<p>'+inline(line)+'</p>');i+=1
 return '\n'.join(chunks)
css='body{font:17px/1.6 system-ui,sans-serif;background:#f7f7f4;color:#202624;margin:0}main{max-width:1250px;margin:auto;padding:35px}p{max-width:1100px}.section{font-size:23px;margin-top:45px;border-top:2px solid #ccd8d1;padding-top:16px}a{color:#087168}table{border-collapse:collapse;background:white;font-size:14px;margin:15px 0}td,th{border:1px solid #d2dad5;padding:7px 10px;text-align:left;vertical-align:top}th{background:#e5eee7;position:sticky;top:0}.scroll{overflow:auto;max-width:100%}pre{overflow:auto;background:#e9eee9;padding:18px;border-radius:6px;line-height:1.4}code{font:14px/1.4 monospace}img{max-width:100%;height:auto}figure{margin:20px 0}figcaption{color:#607068}input{padding:10px;width:360px;max-width:90%;margin:15px}summary{cursor:pointer;font-weight:bold}@media print{body{background:white}main{padding:0}pre{white-space:pre-wrap}table{font-size:10px}.scroll{overflow:visible}details{display:none}}'
app='<details><summary>Все 648 оценок P1 (раскрыть)</summary><input placeholder="Фильтр: kimina, whitened, pre…" oninput="document.querySelectorAll(\'#allfits tbody tr\').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(this.value.toLowerCase()))"><div id="allfits">'+render(table(ah,ar).splitlines())+'</div></details>'
(P/'REPORT_RU.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P1 — '+msk+'</title><style>'+css+'</style><main>'+render(md.splitlines())+app+'</main></html>',encoding='utf-8')
manifest={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'capture_utc':S['captured_utc'],'scope':S['scope'],'calculation_job':'8466254','render_job':os.environ.get('SLURM_JOB_ID'),'python':platform.python_version(),'hostname':platform.node(),'checks':S['checks']+[{'localized_pre_matches_t_star':True,'main_records':len(A),'p1_rows':len(E)}],'files':{}}
for f in sorted(P.rglob('*')):
 if f.is_file() and f.name!='report-manifest.json' and f.suffix!='.log':
  manifest['files'][str(f.relative_to(P))]={'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size}
(P/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('REPORT_READY',json.dumps({'main_total':total,'totals':dict(cats),'fits':len(fitted),'fitted_statuses':dict(collections.Counter(r['fit_status'] for r in E)),'report_bytes':len(md.encode()),'files':len(manifest['files'])},ensure_ascii=False),flush=True)
