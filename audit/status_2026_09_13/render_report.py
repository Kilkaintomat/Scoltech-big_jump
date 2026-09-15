"""Render a bounded, reproducible status audit from frozen aggregate inputs on Slurm."""
from pathlib import Path
from collections import Counter
import json, sys, datetime, xml.etree.ElementTree as ET
from onebigjump.e1.artifacts import read_json, write_once, finish, digest, verify_manifest
root=Path('/beegfs/home/denis.rakhmankin/onebigjump')
out=Path(sys.argv[1]); inp=out/'inputs'
r=lambda n:read_json(inp/n)
initial=r('initial.metrics.json')
models=['deepseek','goedel','kimina']
controls={model:{name:r(model+'.'+name+'.metrics.json') for name in ['positional']+['whitening-%02d'%i for i in range(12)]} for model in models}
# The expensive initial audit already checked complete training and generation chains.
# Bind its exact aggregate output to that audit, then independently verify new pilot controls.
bindings={}
for stem in ['initial','deduction','replay']+[m+'.'+n for m in models for n in controls[m]]:
    p=inp/(stem+'.metrics.json'); provenance=r(stem+'.provenance.json')
    assert digest(p) in [v for k,v in provenance['outputs'].items() if k.endswith('/metrics.json')]
    bindings[stem]={'metrics_sha256':digest(p),'provenance_sha256':digest(inp/(stem+'.provenance.json'))}
seen=set()
for model in models:
    for name in controls[model]:
        p=root/'runs/controls_20260913/pilot'/model/name/'manifest.json'
        verify_manifest(p,seen)
        assert controls[model][name]['decision']=='inconclusive'
        if name!='positional':assert controls[model][name]['variant']['status']=='complete'
    for stage in ['verification','extraction','measurement','analysis']:
        verify_manifest(root/'runs/lean_reverification_20260912'/model/'pilot'/stage/'manifest.json',seen)
source=root/'audit/revision_2026_09_12/snapshots/controls-v1-20260913/source-manifest.json'
tests=[dict(x.attrib) for x in ET.parse(inp/'tests.xml').getroot().iter('testsuite')]
for t in tests:assert all(int(t[k])==0 for k in ['errors','failures','skipped'])
queues={k:r(k+'.queue.json') for k in ['lean','controls','expansion']}
stats={k:dict(Counter(t['state'] for t in q['tasks'].values())) for k,q in queues.items()}
cutoff=r('cutoff.json')
metrics={'cutoff':cutoff,'initial_audit':initial,'deduction_diagnosis':r('deduction.metrics.json'),
 'fresh_replay':r('replay.metrics.json'),'controls':controls,'protocols':{m:r(m+'.protocol.json') for m in models},
 'queue_counts':stats,'tests':tests,'aggregate_bindings':bindings,'new_manifests_recursively_checked':len(seen),
 'source':read_json(source)['metrics'],'controls_source_sha256':digest(source),
 'pilot_recovery':r('pilot-recovery-receipt.json'),'controls_transition':r('controls-transition.json'),
 'conclusion':'inconclusive: main verifier blocked; whitening miscalibration; P4 learning but no observed positive-to-nonpositive moment transition; deduction protocol failure; P3 undercoverage'}
write_once(out/'metrics.json',metrics)
lines=[]
def p(s=''):lines.append(s+'\n')
def h(s):p('\n## '+s+'\n')
def table(headers,rows):
    p('| '+' | '.join(headers)+' |');p('| '+' | '.join('---' for _ in headers)+' |')
    for row in rows:p('| '+' | '.join(str(x).replace('|',' / ').replace('\n',' ') for x in row)+' |')
    p()
def f(x):return 'недоступно' if x is None else ('%+.4f'%x)
def pct(x):return 'недоступно' if x is None else ('%.2f%%'%(x*100))
def num(x):return 'недоступно' if x is None else ('%.5g'%x)
def rate(z):return str(z['exceedances'])+'/'+str(z['steps'])+' = '+pct(z['exceedance_rate'])
p('# One Big Jump — проверка состояния и результатов на Жоресе')
p('Срез состояния: **'+cutoff['utc']+' (UTC)**. Отчёт создан на вычислительном узле Slurm из зафиксированных метрик. Источник: '+str(root)+'.')
p('**Основной вывод:** генерация завершена, но основная проверенная выборка ещё не готова. Ночная Lean-серия остановилась из-за исчерпания системной таблицы файлов и отдельной воспроизводимой ошибки пошагового воспроизведения. Парный P4 завершён и показывает обучение, однако ожидаемый переход от положительного к неположительному хвостовому индексу не продемонстрирован. Дедукционный пилот выявил нарушение протокола ответов. Полная пилотная сетка whitening завершена и подтверждает проблему калибровки порога. Эти результаты требуют исправления измерительного контура перед дальнейшим масштабированием.')
p('Этот документ предназначен для независимого аудита другим GPT или исследователем. Числа в таблицах автоматически прочитаны из metrics.json; исходные ответы моделей, активации и контрольные точки остаются на сервере. Начальный аудит и результаты сегодняшнего восстановления различаются ниже. Это аудит текущих веток проекта, а не новая проверка всех исторических симуляций и каждого прежнего результата статьи.')

h('Что измеряет проект и какие ограничения действуют')
p('Проект проверяет связь между крупными изменениями residual stream и ошибками рассуждения. Приращение — разность состояний на последних токенах соседних шагов; начальная точка берётся на последнем токене промпта. Измеряются raw-норма, whitened-норма после преобразования и innovation после линейного прогноза. Генерация выполняется без обратной связи от проверяющего алгоритма. После первой ошибки метки поглощающие: последующие шаги помечаются unreached, а не реально проверенными.')
p('P1 сравнивает хвосты распределений; P2 — локализацию первой ошибки и сравнение с token surprisal; P3 — overshoot/форму хвоста и её статистическую калибровку; P4 — изменение показателей во время grokking; P5 — закон ошибки в зависимости от длины. Завершение вычислительного этапа само по себе не означает подтверждения предсказания.')
p('Знаковый индекс gamma и параметр порядка xi различаются: xi=max(gamma,0). Отрицательные оценки moment/GPD сохраняются. Положительный Hill сам по себе не доказывает тяжёлый хвост: Hill не может дать неположительную оценку. Отдельные трассы одного задания зависимы, поэтому для интервалов единицей ресемплинга служит задание; при недостаточном числе независимых заданий интервал здесь не сообщается. Для P4 независимая единица — парный training seed.')
table(['Модель','Основной слой','Основная температура','Основная статистика','Ревизия модели'],
 [[m,metrics['protocols'][m]['primary_layer'],metrics['protocols'][m]['primary_temperature'],metrics['protocols'][m]['primary_statistic'],metrics['protocols'][m]['revision']] for m in models])
p('Основная ячейка сохранена заранее выбранной. Сетка чувствительности и анализ исключения первого приращения — вторичные диагностики. Протоколы сохранены в inputs/*.protocol.json. Даже успешный collection-only gate разрешает сбор данных, а не подтверждает научные гипотезы.')

h('Генерация и реальная готовность основной выборки')
table(['Модель','Запланировано','Сохранено','Уникальных ID','Пропущено / лишних ID','Частичных строк меток'],
 [[m,d['planned_attempts'],d['generated_attempts'],d['unique_generated_ids'],str(len(d['missing_ids']))+' / '+str(len(d['unexpected_ids'])),d['partial_label_rows']] for m,d in initial['lean'].items()])
p('Всего сохранено '+str(sum(x['generated_attempts'] for x in initial['lean'].values()))+' основных попыток. Плановые ID сопоставлены с журналами; проверены дубликаты, хеши строк и контекстов. Генерация завершена во всех запланированных шардах. Перегенерация из-за ошибки проверяющего алгоритма не требуется.')
p('Основных строк меток на начальном срезе: '+str(sum(x['partial_label_rows'] for x in initial['lean'].values()))+'. Они включают частичные и неуспешные задания, поэтому не являются готовым согласованным набором. В основной новой серии ещё нет завершённых extraction/measurement/analysis. Нельзя рассчитывать окончательные P1/P2/P3/P5 или сравнивать модели по долям успеха из этих частичных строк.')
table(['Причина ночного падения','Число заданий'],Counter(x['cause'] for x in initial['lean_failures']).items())
table(['Модель','Категория частичной метки','Число'],[[m,k,v] for m,d in initial['lean'].items() for k,v in sorted(d['partial_label_categories'].items())])
p('Эта последняя таблица описывает содержимое сохранённых журналов; семантическая правильность каждой метки пока не установлена. В строках не найдено буквального сообщения об исчерпании файлов, однако отсутствие такой строки не доказывает правильность t*.')

h('Lean: два разных препятствия')
replay=metrics['fresh_replay']
p('Сохранённый случай **'+replay['trace_id']+'**: целое доказательство принимается Lean, а пошаговое воспроизведение отвергает блок have с сообщением Unknown identifier 𝓝. Он воспроизведён повторно без изменения доказательства и протокола в свежих независимых REPL-сессиях.')
table(['Свежая сессия','Whole proof','Replay','Категория','Необъяснённое расхождение'],
 [[i,x['whole'],x['replay'],x['category'],x['unexplained_disagreement']] for i,x in enumerate(replay['fresh_session_results'])])
p('Вероятное направление ремонта — сохранение scoped notation и контекста парсера/команд между whole-proof и tactic replay. Это диагноз по воспроизводимому симптому, ещё не доказательство конкретной строки с дефектом. Новый случай показывает ограниченность прежнего регрессионного набора: прежние исправления heartbeat и сегментации не покрыли все контексты Lean.')
table(['Фаза','Системная таблица: allocated / unused / max','Процессный soft / hard NOFILE'],
 [[x['phase'],x['values']['file_nr'].replace('\t',' / '),' / '.join(map(str,x['values']['process_nofile']))] for x in replay['node_file_counters']])
p('При запуске REPL на cn70 существенно вырос глобальный счётчик открытых файлов. Ранее несколько Lean-заданий размещались на одном узле, а исключения имели errno ENFILE — системный лимит файлов, не только лимит одного процесса. Это согласуется с ресурсной причиной ночных падений. Контролируемый эксперимент с различной конкурентностью пока не выполнен; остаточный глобальный счётчик после закрытия сессии требует отдельной проверки очистки ресурсов.')
p('Практическое следующее действие: сначала исправить контекст нотаций и расширить регрессии, затем запускать Lean с консервативным ограничением сессий на узел и мониторингом /proc/sys/fs/file-nr. Начальное инженерное ограничение — не более двух одновременных сессий на узел с дальнейшей проверкой. Простого повышения ulimit -n недостаточно для системного ENFILE. Протокольный бюджет heartbeat сохраняется.')
p('Проверять нужно и t*, включая случаи, где whole-proof и replay оба возвращают false: совпадение итогового отказа может скрывать ошибочную локализацию. После ремонта следует создать новый неизменяемый слой верификации над сохранёнными генерациями и перепроверить потенциально затронутые шарды. Старые метки и манифесты должны остаться доступными для сравнения. Текущий основной диспетчер не перезапущен.')

h('Whitening и позиционные эффекты: завершённые пилотные контроли')
p('Завершено '+str(sum(1 for q in queues['controls']['tasks'] if q.startswith('pilot/')))+' заданий пилотных контролей. Для каждой модели есть baseline positional и полная сетка shrinkage × разделение transform/threshold × исключение первого приращения. Все варианты имеют status=complete, научное решение остаётся inconclusive.')
plan=controls['deepseek']['whitening-00']['plan']
p('План: '+json.dumps(plan,ensure_ascii=False)+'. Разделение задаётся по ID задания, поэтому попытки одного задания не попадают в разные стороны. Fit и threshold при disjoint=true не пересекаются; evaluation отделена от обеих сторон. При drop_first=true первое приращение исключено при fit, пороге и оценке. Исходные индексы t сохранены для сопоставления с t*. Пустые трассы и исключённые случаи учитываются явно.')
table(['Модель','Raw: превышения на допустимых шагах','Whitened','Innovation'],
 [[m]+[rate(controls[m]['positional']['cells'][s]['threshold']['evaluation']['accepted_evaluation']) for s in ['raw','whitened','innovation']] for m in models])
p('Допустимые шаги в этой таблице — реально принятые шаги до первой ошибки, включая шаги полностью успешных трасс. Это не все сгенерированные шаги и не только полностью успешные трассы. Разделы verified_evaluation и first_failure в metrics.json позволяют проверить знаменатели отдельно. Частота превышений дана описательно, шаги не считаются независимыми.')
table(['Модель','Вариант','Fit: шаги / задания','Threshold: шаги / задания','n_fit / d','Порог tau','Превышения на допустимых шагах'],
 [[m,name,str(v['fit_increments'])+' / '+str(v['effective_fit_tasks']),str(v['threshold']['calibration']['steps'])+' / '+str(v['threshold']['calibration']['tasks']),num(v['n_over_d']),num(v['threshold']['tau']),rate(v['threshold']['evaluation']['accepted_evaluation'])]
 for m in models for name in ['whitening-01','whitening-04','whitening-07','whitening-10'] for v in [controls[m][name]['variant']]])
p('В таблице выше shrinkage фиксирован на исходном значении протокола. whitening-01 использует одни данные для fit/threshold, whitening-04 разделяет их; whitening-07 и whitening-10 дополнительно исключают первое приращение.')
p('Повторное использование fit-данных для порога даёт выраженно оптимистичную оценку на обучающих приращениях при очень малом отношении n/d. Разделение резко поднимает tau и снижает частоту превышений вне fit. Это сильная диагностическая поддержка такой причины провала, но маленькая калибровочная выборка и зависимость шагов не позволяют объявить разделённый вариант корректно откалиброванным. Номинальная хвостовая доля равна '+pct(plan['q'])+'. Даже разрешение эмпирической квантили ограничено числом калибровочных шагов.')
table(['Модель','Вариант','Shrinkage','Disjoint','Drop first','Tau','Допустимые: превышения / шаги','Первый отказ: превышения / шаги'],
 [[m,name,v['specification']['shrinkage'],v['specification']['disjoint'],v['specification']['drop_first'],num(v['threshold']['tau']),rate(v['threshold']['evaluation']['accepted_evaluation']),rate(v['threshold']['evaluation']['first_failure'])]
 for m in models for name,d in controls[m].items() if name!='positional' for v in [d['variant']]])
p('Во всей проверенной сетке изменение shrinkage не исправляет повторное использование данных. Исключение первого приращения само по себе тоже не устраняет патологию порога. Разделённые варианты остаются вторичной чувствительностью; на основании этой таблицы основной метод не заменялся.')

h('P2: сравнение с surprisal на одинаковых трассах')
p('Для каждого сравнения jump и surprisal используют точное пересечение доступных трасс; ID и SHA256 списка находятся в paired_trace_ids и paired_trace_ids_sha256. Сравнивать top-1 из разных наборов запрещено. Значение paired_gain — jump_top1 минус surprisal_top1. Ниже приведены все baseline-статистики, чтобы не выбирать только удачную.')
table(['Модель','Статистика','Трассы / задания','Jump top-1','Surprisal top-1','Парная разность','95% CI'],
 [[m,s,str(v['n_traces'])+' / '+str(v['n_tasks']),pct(v['jump_top1']),pct(v['surprisal_top1']),f(v['paired_gain']),'нет: мало независимых заданий' if v['paired_ci95'] is None else v['paired_ci95']]
 for m in models for s in ['raw','whitened','innovation'] for v in [controls[m]['positional']['cells'][s]['P2']['all']]])
table(['Модель','Статистика','Отбор','Трассы / задания','Jump top-1','Surprisal top-1','Парная разность'],
 [[m,s,view,str(v['n_traces'])+' / '+str(v['n_tasks']),pct(v['jump_top1']),pct(v['surprisal_top1']),f(v['paired_gain'])]
 for m in models for s in ['raw','whitened','innovation'] for view in ['failure_after_first','failure_after_first_drop_first'] for v in [controls[m]['positional']['cells'][s]['P2'][view]]])
p('failure_after_first исключает трассы, где первая ошибка сразу на первом шаге; второй вариант также убирает первый шаг из кандидатов argmax. Отбор меняет задачу оценивания и знаменатель, поэтому его нельзя выдавать за улучшение на исходной совокупности. В частности, заметный raw-сигнал DeepSeek на полном пилоте связан с первым шагом; после отбора остаётся слишком мало независимых заданий для вывода о преимуществе.')
p('Позиционный null стратифицирован по семейству задания и точной длине, с одним заранее определённым представителем на задание. На малом пилоте страты часто не содержат достаточно независимых заданий; недоступный p-value не равен отрицательному результату. В metrics.json сохранены доступность, причины исключений, шанс E[1/L], выборка null и все варианты whitening. Интервалы не строятся ниже протокольного минимума независимых заданий.')
p('P1 на этой сетке в основном недоступен из-за недостаточного числа шагов/хвостовых наблюдений. Редкие конечные оценки не являются полноценной идентификацией хвоста. Ниже все доступные тройки, включая недоступный GPD; порядок — Hill, moment, GPD.')
table(['Модель','Вариант','Группа','Hill','Moment','GPD'],
 [[m,name,group]+[num(x) for x in values] for m in models for name,d in controls[m].items() if name!='positional' for group,values in d['variant']['P1'].items() if any(x is not None for x in values)])
p('Для основных данных подготовлены '+str(sum(k.startswith('main/') for k in queues['controls']['tasks']))+' задания контроля, сейчас WAITING. Они включают позиционный анализ, полную сетку whitening и повторные подгонки калибровки. Их зависимости переведены с прежней серии на runs/lean_reverification_20260912. После нового исправления Lean необходимо явно перепривязать их к окончательной валидированной серии, если путь изменится. Пока main-измерений нет, эти задания не вычисляют научные результаты.')

h('Парный P4: обучение есть, заявленного перехода хвоста пока нет')
runs=initial['p4']['runs']; pairs=initial['p4']['summary']['pairs']
by={(x['arm'],x['seed']):x for x in runs}
p('Завершены все запланированные real/null пары, включая обучение, измерения, tail-grid и парную сводку. Контроль null перемешивает метки. В каждом запуске '+str(runs[0]['training']['steps'])+' шагов обучения и '+str(runs[0]['training']['checkpoints'])+' контрольных точек. Свойства конфигурации и хеши контрольных точек сохранены в метриках и исходных манифестах.')
table(['Seed','Опорный шаг real','Финальная точность real','Финальная точность null','Moment real до','Moment real после'],
 [[z['seed'],z['real_reference_step'],pct(by['real',z['seed']]['final']['test_acc']),pct(by['null',z['seed']]['final']['test_acc']),f(by['real',z['seed']]['primary_transition']['moment']['before']),f(by['real',z['seed']]['primary_transition']['moment']['after'])] for z in pairs])
p('Опорный шаг определяется заранее заданным правилом: '+runs[0]['primary_transition']['rule']+'. Средние до и после берутся в окнах радиуса '+str(runs[0]['primary_transition']['window_radius_steps'])+' шагов. Null сравнивается в тех же временных окнах, привязанных к real, а не к выбранному задним числом переходу null.')
table(['Seed','Hill до → после','Moment до → после','GPD до → после','ΔHill real−null','ΔMoment real−null','ΔGPD real−null'],
 [[z['seed']]+[f(by['real',z['seed']]['primary_transition'][s]['before'])+' → '+f(by['real',z['seed']]['primary_transition'][s]['after']) for s in ['hill','moment','gpd']]+[f(z['paired_difference'][s]) for s in ['hill','moment','gpd']] for z in pairs])
p('Парная разность — (после−до)_real − (после−до)_null. Поля restricted_loss/excluded_loss в парной сводке тоже являются изменениями, а не абсолютными значениями loss; отрицательный delta restricted_loss не означает отрицательную cross-entropy.')
p('Moment отрицателен до и после во всех real-запусках. Следовательно, положительная оценка xi, исчезающая при grokking, здесь не показана. Направление изменений неоднородно между seeds. Результат обучения устойчив; конкретное хвостовое предсказание остаётся inconclusive. Это не подтверждение алгоритмичности модели и не универсальное опровержение теории: конечная ограниченная область входов и выбранная наблюдаемая величина ограничивают интерпретацию.')
p('Полная grid-диагностика с Hill/moment/GPD, выбранным k и условными bootstrap-интервалами находится в metrics.json → initial_audit → p4 → runs → tail_grid. Bootstrap по входам внутри фиксированной обученной модели не заменяет вариативность между training seeds. До дополнительных однотипных тренировок следует проверить соответствие наблюдаемой величины предполагаемому промежуточному хвостовому диапазону и сформулировать отдельный заранее заданный тест.')

h('Контролируемая дедукция: корректно остановленный пилот')
d=metrics['deduction_diagnosis']
table(['Показатель','Результат'],[
 ['Попыток / различных заданий',str(d['attempts'])+' / '+str(d['unique_tasks'])],
 ['Категории',json.dumps(d['categories'],ensure_ascii=False)],
 ['Неверная длина ответа',d['format_wrong_length']],
 ['В том числе посторонние строки',d['format_unknown_lines']],
 ['Допустимые по формату, но повторяющие исходный факт',d['eligible_initial_fact_repetitions']],
 ['Первый отказ сразу в допустимых по формату ответах',d['eligible_first_failure_at_zero']],
 ['Принятые проверяющим алгоритмом эталонные цепочки',str(d['gold_checker_passes'])+'/'+str(d['attempts'])],
 ['Причины завершения генерации',json.dumps(d['finish_reasons'])]])
p('Доля ответов, соответствующих формату: '+pct(initial['deduction']['format_eligible']/d['attempts'])+'. Исходный порог gate не достигнут, основная дедукционная серия не разрешена. Все формально допустимые ответы начинаются с повторения данного начального факта, хотя каждый новый шаг должен быть выводом по одному правилу. Это объясняет концентрацию первой ошибки на начале. Проверяющий алгоритм принимает все эталонные цепочки без ослабления правил. Ошибки формата не объясняются только достижением лимита генерации.')
dedcells=[x for x in initial['deduction']['cells'] if x['available']]
table(['Температура','Статистика','Трассы / задания P2','Jump top-1','Surprisal top-1','Null p_jump','Null заданий'],
 [[x['temperature'],x['statistic'],str(x['P2']['n_traces'])+' / '+str(x['P2']['n_tasks']),pct(x['P2']['jump']['top1']),pct(x['P2']['surprisal']['top1']),num(x['positional_null']['p_jump']),x['positional_null']['n_tasks']] for x in dedcells])
p('Кажущаяся идеальной локализация raw на таком пилоте не является убедительным сигналом coupling: ошибки и крупные изменения сосредоточены на первом шаге, а доступный позиционный null не показывает преимущества. Whitened/innovation недоступны без достаточной verified-калибровки. Полностью успешных цепочек нет; P5 не даёт валидной оценки закона длины. Format failures сохраняются в intention-to-treat знаменателе; исходы с нулём успехов не выбрасываются ради подгонки.')
p('Следующее действие — отдельный development-пилот с ясным примером ровно L новых выведенных фактов, запретом повторения исходного факта и демонстрацией допустимого завершения. Сначала проверить небольшой набор свежих технических ответов тем же алгоритмом, затем заморозить протокол и собрать независимый пилот/main. Исходные ответы не редактировать и gate не понижать. Контрольный ответ модели и эталонную цепочку нельзя смешивать.')

h('P3: статистическая калибровка всё ещё недостаточна')
p3=initial['p3']
table(['Сценарий','Метод','Доступные интервалы / датасеты','Покрытие среди доступных','95% Monte Carlo CI'],
 [[scenario,method,str(z['availability']['successes'])+'/'+str(z['availability']['datasets']),str(z['coverage']['successes'])+'/'+str(z['coverage']['datasets'])+' = '+pct(z['coverage']['fraction']),' — '.join(pct(x) for x in z['coverage']['monte_carlo_ci95'])]
 for scenario,s in p3['scenarios'].items() for method,z in s['methods'].items()])
p('Это прежняя завершённая диагностика на независимых симулированных датасетах, заново проверенная в текущем аудите, а не новая серия после сегодняшних контролей. Номинальное покрытие интервала — 95%. Original-support показывает заметное недопокрытие estimated percentile/basic. Oracle не является доступным методом для реальных данных, а его покрытие условно на наличии оценки. Числители и знаменатели приведены явно, поэтому результат на доступном подмножестве нельзя выдать за результат на всех датасетах.')
p('Изменение статистического метода автоматически не внедрено: main_method_changed='+str(p3['main_method_changed'])+'. Новую коррекцию нужно заранее определить и проверить на независимой калибровочной серии, затем отдельно валидировать. Пока нельзя трактовать текущие интервалы как надёжные подтверждающие интервалы заявленного уровня.')

h('Что сделано в этом подключении')
p('- Прочитаны Slurm accounting, очереди, журналы и артефакты; сверены плановые ID основных генераций и хеши сохранённых данных.\n- Завершена реализация whitening/position diagnostics: независимые transform/threshold задания, сетка shrinkage, исключение первого приращения, сохранение исходного t, парное сравнение с surprisal и учёт исключений.\n- Исправлены ошибки типов незавершённой проверки кода; пройдены focused и общий быстрый набор проверок.\n- Восстановлены DeepSeek pilot measure/analyze/gate после ресурсного падения, история заданий сохранена. Это не перезапуск основной Lean-серии.\n- Запущена и завершена полная сетка пилотных контролей. Ожидавшие старых данных основные контроли перенесены в отдельную очередь с актуальными зависимостями; существующие P4/генерации/выходы сохранены.\n- Отдельным Slurm-заданием проверены все gold-цепочки дедукции.\n- Отдельным Slurm-заданием воспроизведено расхождение Lean и измерены системные счётчики файлов.\n- Подготовлен этот отчёт и машинные метрики. Новое дорогое обучение и повторная генерация не запускались.')
table(['Проверка','Число тестов','Ошибки','Падения','Пропуски'],[[t['name'],t['tests'],t['errors'],t['failures'],t['skipped']] for t in tests])
p('Текущий общий набор включает ruff, форматирование, mypy и fast tests. Прежняя live-проверка Lean/torch относится к предыдущему ремонту и не заменяет регрессии нового случая 𝓝. Успех тестов не отменяет обнаруженного дефекта в научной разметке.')
table(['Очередь','Состояния после сегодняшних действий'],[[k,json.dumps(v,ensure_ascii=False)] for k,v in stats.items()])
p('В controls число COMPLETED включает внешнюю задачу валидации. WAITING у основных контролей означает отсутствие входных main-манифестов, а не вычисление в процессе. У Lean часть BLOCKED остаётся как сохранённое состояние зависимостей: диспетчер остановлен, основной запуск сознательно не возобновлён. Последняя проверка очереди Slurm сохранена в inputs/squeue.txt.')

h('Порядок следующих действий и критерии завершения')
table(['Приоритет','Действие','Критерий готовности'],
 [
 ['A','Исправить Lean scoped notation/контекст и проверить жизненный цикл REPL; ограничить конкурентность на узел.','Свежие регрессии принимают этот whole/replay случай согласованно, проверяют локализацию t*, включая оба false; длительная проверка на узле проходит без ENFILE.'],
 ['B','Создать новую неизменяемую верификацию сохранённых генераций; завершить extraction/measurement/analysis и перепривязать основные контроли.','Полнота ID/шардов и манифестов, отсутствие необъяснённых расхождений, корректная absorption, достаточная независимая калибровка; все заранее заданные контроли выполнены.'],
 ['C','Переработать инструкции дедукционного development-пилота, затем заморозить новый протокол.','Модель соблюдает формат и выводит новые факты; прежний gate пройден на свежих данных без ослабления проверяющего алгоритма.'],
 ['D','Зафиксировать P4 как реплицированное обучение с неподтверждённым переходом индекса; проверить конструкцию хвостового наблюдения.','Новая гипотеза/наблюдаемая величина и диапазон оценивания заданы до дополнительной серии; публикуются все три оценивателя и контрпримеры seeds.'],
 ['E','Довести независимую калибровку P3.','Доступность и покрытие проверены на новой заранее заданной валидационной серии; ошибки и недоступные оценки учитываются явно.']
 ])
p('Наиболее полезный ближайший результат — законченная доверенная разметка уже собранных генераций. Новые большие GPU-серии сейчас дадут меньше информации, чем устранение конкретного дефекта проверки и завершение основных диагностик. Срок основной Lean-серии пока нельзя честно оценить: сначала требуется проверить ресурсную устойчивость и исправление контекста. Для нового development-пилота дедукции допустим небольшой заранее ограниченный GPU-запуск, но массовый сбор преждевременен.')
p('Пункт о запуске дедукционного пилота и парном P4 организационно выполнен: оба состоялись, P4 закончен, дедукционный gate выявил проблему. Пункт о whitening/позиционных эффектах завершён на пилотах; на основных данных остаётся зависимость от ремонта Lean и измерения. Выдавать его за полностью завершённый на main было бы неверно.')

h('Происхождение результатов и проверка другим GPT')
p('Начальный аудит: '+str(len(initial['checks']))+' проверенных манифестов, all_checked_manifests_valid='+str(initial['all_checked_manifests_valid'])+'. В финальном сборщике проверены привязки агрегатов к выходам этих манифестов; новые пилотные цепочки проверены рекурсивно с устранением повторов: '+str(len(seen))+' различных манифестов. Хеши подтверждают целостность и происхождение, но не семантическую правильность алгоритма проверки.')
p('Git/source: '+json.dumps(metrics['source'],ensure_ascii=False)+'. Дерево dirty; единственного git commit недостаточно для воспроизведения. Сохранённый неизменяемый snapshot и его content digest обязательны. Controls source-manifest SHA256: '+metrics['controls_source_sha256']+'. Lean source-manifest SHA256: '+replay['source_sha256']+'.')
p('Основные серверные пути:\n- runs/lean_recovery_20260911_v3 — сохранённые генерации.\n- runs/lean_reverification_20260912 — частичная новая проверка и восстановленные пилоты.\n- runs/expansion_20260911/p4/summary — завершённая парная сводка.\n- runs/expansion_20260911/deduction/pilot — исходный неудачный пилот.\n- runs/controls_20260913 — завершённые pilot-контроли и main-зависимости.\n- runs/p3_diagnosis_20260912/summary — диагностика покрытия.\n- audit/status_2026_09_13 — сегодняшние проверки, истории переходов и этот отчёт.')
p('Пакет содержит REPORT.md, metrics.json, manifest.json, inputs с агрегированными источниками, учётом заданий и протоколами, а также текст запроса независимому рецензенту. Абсолютные пути манифестов относятся к Жоресу. Полная рекурсивная проверка исходных экспериментов возможна на сервере; автономный пакет позволяет перепроверить цифры отчёта, знаменатели, provenance и логику выводов, но не заново запустить Lean или восстановить активации.')
p('Рецензенту следует отдельно проверить: не смешаны ли generation-complete и experiment-complete; не превращена ли отрицательная gamma в доказательство положительного xi; не выбрана ли удачная ячейка задним числом; одинаковы ли трассы у jump/surprisal; не скрыты ли format failures и недоступные интервалы; не подменяет ли обучение P4 подтверждение хвостового механизма; нет ли попытки принять частичные Lean-метки за валидированный main.')
(out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
(out/'PROMPT_FOR_GPT.txt').write_text(
 'Проведи независимый критический аудит проекта One Big Jump по REPORT.md, metrics.json и inputs. Проверь числа и знаменатели, статус main против pilot, сохранение primary cell, единицы ресемплинга, доступность интервалов и отличие обучения P4 от хвостового предсказания. Найди необоснованные выводы, утечки между transform/threshold/evaluation, позиционные артефакты и риски ошибочной Lean-разметки. Не считай completed Slurm подтверждением гипотезы. Предложи приоритетные действия с критериями завершения. Раздели подтверждённые фактами выводы, интерпретации и вопросы, для которых нужны серверные исходники. Исходные ответы и веса в пакет не включены.\n',encoding='utf-8')
finish(out,stage='final-project-status-report',context={'cutoff':cutoff,'scope':'aggregate scientific status audit; no primary method changes'},
 inputs=[Path(__file__),source,*sorted(inp.iterdir())],
 outputs=[out/'metrics.json',out/'REPORT.md',out/'PROMPT_FOR_GPT.txt'],
 metrics={'aggregate_binding_count':len(bindings),'new_manifest_count':len(seen),'pilot_controls_complete':sum(k.startswith('pilot/') for k in queues['controls']['tasks']),'scientific_decision':'inconclusive'})
print('REPORT_READY',out,flush=True)
