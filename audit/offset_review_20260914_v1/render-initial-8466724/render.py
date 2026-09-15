from __future__ import annotations
import base64,datetime,hashlib,html,importlib.metadata,json,os,pathlib,re,shutil,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path('/beegfs/home/denis.rakhmankin/onebigjump')
HERE=ROOT/'audit/offset_review_20260914_v1'
D=HERE/'result-8466720'
data=json.loads((D/'metrics.json').read_text());manifest=json.loads((D/'manifest.json').read_text())
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
for p,h in manifest['outputs'].items():assert sha(p)==h,p
M=data['models'];names={'deepseek':'DeepSeek','goedel':'Goedel','kimina':'Kimina'}
def pct(x,d=1):return f'{100*x:.{d}f}%'
def num(x,d=3):return '—' if x is None else f'{x:.{d}f}'
def ci(x):return 'не определён' if x is None else '['+num(x[0])+'; '+num(x[1])+']'
chunks=[]
def para(text):chunks.append(text)
def table(headers,rows):
 chunks.append('| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+
               '\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows))

para('**ONE BIG JUMP — отчёт для научного руководителя**')
para('Срез основных результатов и дополнительная диагностика положения скачка относительно первой ошибки. '
     'Основной набор и настройки сохранены. Новая диагностика выполнена после просмотра основных результатов '
     'и имеет исследовательский, а не подтверждающий статус.')
para('Дата расчёта: '+data['created_utc']+'. Задание аудита Slurm: '+data['job']+'.')
para('**Основной вывод.** На сохранённых доказательствах обнаружена выраженная структура положения максимального скачка, '
     'в том числе частое попадание на следующий после ошибки шаг. Однако положение ошибок само по себе сильно неравномерно. '
     'Высокие проценты соседства нельзя интерпретировать как установленную индивидуальную связь скачка с ошибкой без '
     'контроля этих позиционных частот. Основное предсказание точной локализации P2 не подтверждено; '
     'сдвинутая локализация остаётся отдельной проверяемой гипотезой. P1, P3–P5 также пока не дают убедительного подтверждения '
     'заявленного общего механизма.')

para('**Объём данных и что именно завершено.**')
total=sum(v['verification']['attempts'] for v in M.values())
verified=sum(v['verification']['categories']['verified'] for v in M.values())
localized=sum(v['verification']['categories']['localized_tactic_failure'] for v in M.values())
para(f'Учтены {total:,} попыток; Lean подтвердил {verified:,} ({pct(verified/total)}). '
     f'Категория локализованной ошибки тактики присвоена {localized:,} попыткам. '
     'Остальные включают обрывы генерации, ошибки формата, незакрытые цели и ограничения ресурсов. '
     'Неуспешная генерация не всегда даёт достоверную метку первого ошибочного шага. '
     'Эти числа относятся к попыткам, а не к различным решённым задачам.')
table(['Модель','Попыток','Подтверждено Lean','Локализована ошибка'],
      [[names[m],v['verification']['attempts'],v['verification']['categories']['verified'],
        v['verification']['categories']['localized_tactic_failure']] for m,v in M.items()])
para('P2 рассчитан на допустимых ошибочных трассах оценочной части, при температуре 0.6, '
     'среднем заранее выбранном слое и норме после whitening. Калибровочные задачи и другие температуры в эти строки не входят. '
     'Поэтому знаменатель P2 существенно меньше полной популяции. Порог и слой не выбирались по успеху новой диагностики.')

para('**Что означает исключение первого шага.**')
para('Обозначим состояние после формального шага t через X_t; X_0 снимается в конце исходного запроса. '
     'Исходный скачок Z_t соответствует приращению X_t − X_(t−1). Первый скачок связывает конец запроса '
     'с концом первой формальной тактики. Между ними могут находиться неформальные рассуждения и заголовок Lean, '
     'поэтому он не равнозначен переходу между соседними формальными тактиками.')
para('Первый контроль оставляет только доказательства, в которых первая формальная тактика прошла Lean, '
     'а ошибка появилась позже. Это условная подвыборка, а не улучшение результата на всех ошибочных доказательствах. '
     'Второй контроль дополнительно исключает Z_1 из кандидатов на максимум. Приращения остальных шагов не пересчитываются, '
     'никакие соседние состояния не склеиваются, истинная ошибка остаётся той же.')
table(['Модель','Все: n / top-1','Ошибка позже первого: n / top-1','То же, без Z₁: top-1 / случайно'],
 [[names[m],f"{v['subsets']['all']['n']} / {pct(v['subsets']['all']['rates']['lag_+0'])}",
   f"{v['subsets']['failure_after_first']['n']} / {pct(v['subsets']['failure_after_first']['rates']['lag_+0'])}",
   f"{pct(v['subsets']['failure_after_first_drop_first']['rates']['lag_+0'])} / {pct(v['subsets']['failure_after_first_drop_first']['uniform_chance']['lag_+0'])}"]
  for m,v in M.items()])

para('**Длины трасс и смысл дополнения к максимальному скачку.**')
para('Случайный top-1 равен среднему значению 1/L по трассам. Его обратная величина — гармоническая средняя L, '
     'которая не равна обычной арифметической средней. Короткие трассы дают большой вклад в такой случайный уровень.')
table(['Модель','Трасс / задач','Средняя L','Медиана L','Гармоническая L','Доля L=2'],
 [[names[m],f"{v['subsets']['all']['n']} / {v['subsets']['all']['n_tasks']}",
   num(v['subsets']['all']['length_mean'],2),num(v['subsets']['all']['length_median'],1),
   num(v['subsets']['all']['length_harmonic'],2),pct(v['by_length']['L=2']['n']/v['subsets']['all']['n'])]
  for m,v in M.items()])
ds=M['deepseek']['subsets']['all'];d2=M['deepseek']['by_length']['L=2']
para(f"У DeepSeek максимум не совпал с ошибкой в {pct(ds['rates']['complement_coverage'])} случаев. "
     'Это покрытие ошибки множеством всех остальных шагов; в нём может быть несколько кандидатов. '
     f"Если после исключения максимума выбирать один оставшийся шаг равномерно, точность составит {pct(ds['rates']['random_from_complement'])}, "
     f"а правило «всегда первый шаг» даст {pct(ds['rates']['always_first'])}. "
     'Оба результата являются описанием этой выборки, не оценкой переносимости нового детектора.')
para(f"Только при L=2 дополнение содержит ровно один шаг. В этой подвыборке DeepSeek {d2['n']} трасс; "
     f"ошибка на первом шаге встречается в {pct(d2['first_error_rate'])}, "
     f"а выбор противоположного максимуму шага успешен в {pct(d2['rates']['random_from_complement'])}. "
     'Поэтому высокая точность инверсии здесь может возникать за счёт положения ошибки, без анализа внутренних состояний.')

para('**Проверка соседнего скачка.**')
para('Введено D = позиция максимума − позиция первой ошибки. D=+1 означает максимум на следующем шаге; '
     'D=−1 — на предыдущем. Проверены фиксированные смещения от −2 до +2 и окно |D|≤1. '
     'Сдвиг за границу доказательства считается промахом: циклического переноса, обрезания к границе '
     'или исключения неудобных трасс нет. Это ретроспективная локализация; будущий скачок ещё не доступен '
     'в момент выдачи ошибочного шага.')
table(['Модель','D=−1','D=0','D=+1','|D|≤1','Случайное окно |D|≤1','Всегда первый'],
 [[names[m],*[pct(v['subsets']['all']['rates'][k]) for k in ('lag_-1','lag_+0','lag_+1','near_1')],
   pct(v['subsets']['all']['uniform_chance']['near_1']),pct(v['subsets']['all']['rates']['always_first'])]
  for m,v in M.items()])
para('При коротких доказательствах соседнее окно может охватывать почти все позиции. '
     'Для него нужен собственный случайный уровень: число допустимых позиций в окне, делённое на L, '
     'с последующим усреднением по тем же трассам. Сравнивать такое окно с уровнем случайного top-1 некорректно.')
para('![Смещения максимума и контроль позиционных частот](offsets.png)')

para('**Отличает ли сдвиг индивидуальную ошибку от привычной позиции?**')
para('В дополнительном контроле взята одна заранее определённая по идентификатору трасса на задачу. '
     'Положение ошибки переставлялось между разными задачами одинакового семейства и одинаковой длины; '
     'сами скачки и их позиции оставались на месте. Группы с одной задачей исключены. '
     'Такой контроль сохраняет типичные положения ошибок и максимумов и разрушает их связь внутри конкретного доказательства. '
     'Его ограничение — меньшая и изменившаяся подвыборка и предположение обменности задач внутри группы.')
table(['Модель','Задач в контроле','D=+1: наблюдение','D=+1: позиционный контроль','p, одно направление','p, поиск по показателям'],
 [[names[m],v['subsets']['all']['position_null']['n_tasks'],
   pct(v['subsets']['all']['position_null']['observed']['lag_+1']),
   pct(v['subsets']['all']['position_null']['null_mean']['lag_+1']),
   num(v['subsets']['all']['position_null']['p_upper_unadjusted']['lag_+1'],3),
   num(v['subsets']['all']['position_null']['p_abs_max_stat_adjusted']['lag_+1'],3)]
  for m,v in M.items()])
para('В этой таблице наблюдение и контроль рассчитаны на одной ограниченной подвыборке; их нельзя напрямую '
     'сравнивать с процентами по всем трассам из предыдущей таблицы. Поправка учитывает поиск по заранее '
     'перечисленным показателям внутри данной модели и подвыборки; дополнительная поправка на три модели сохранена '
     'в metrics.json. Это не устраняет исследовательский характер анализа, отбор подвыборок и все последствия '
     'предшествующего просмотра данных. Отдельные положительные отклонения требуют независимого подтверждения.')
para('Интервалы в приложенных метриках получены перестановкой/ресэмплингом задач, а не отдельных шагов. '
     f"Число bootstrap-повторов: {data['plan']['bootstrap']}; перестановок: {data['plan']['permutations']}. "
     'При недостаточном числе независимых задач интервал не выдаётся. Описательный интервал не служит '
     'автоматическим доказательством асимптотического утверждения статьи.')

para('**Проверка индексации и границ измерения.**')
ev=[e for v in M.values() for e in v['indexing_evidence']]
para(f"На {len(ev)} детерминированно выбранных трассах независимо восстановлены сырые и whitened-нормы из сохранённых "
     'состояний, сверены хеши состояний, число шагов, позиции последних токенов, метки Lean и сохранённый surprisal. '
     f"Максимальная абсолютная разность raw-норм: {max(e['raw_max_abs_error'] for e in ev):.3g}; "
     f"whitened-норм: {max(e['whitened_max_abs_error'] for e in ev):.3g}. "
     'Обнаруженного глобального сдвига при сопоставлении массивов нет. В таблице индекс 0 означает первый шаг; '
     'ему соответствует states[1]−states[0], а первая ошибка хранится в той же нулевой индексации.')
para('Для обычной нормы смена знака разности не меняет размер скачка. Для whitening это также верно, '
     'если согласованно сменить знак калибровочного среднего. Сдвиг пары состояний на следующий шаг — другой вопрос: '
     'он меняет время наблюдения и проверен через D. Численная сверка не доказывает корректность семантического '
     'разбиения вложенного Lean-кода на атомарные действия. Эта часть требует отдельной проверки сегментации.')
table(['Модель','Пример','Токенов между концом запроса и началом первой тактики'],
 [[names[m],v['indexing_evidence'][0]['problem_id'],
   v['indexing_evidence'][0]['gap_before_first_formal_span_tokens']] for m,v in M.items()])
para('Последняя таблица показывает примеры, а не среднее по популяции. Промежуток может включать неформальное '
     'рассуждение и Lean-заголовок. Он подтверждает, что первый скачок измеряет иной переход, чем последующие. '
     'Новые прямые проходы модели и изменения основных меток в этом аудите не выполнялись.')

para('**P1: хвостовые оценки.**')
table(['Модель','Подмножество','Hill','Moment','GPD','Задач в хвосте','Достаточность по протоколу'],
 [[names[m],sub,*[num(v['primary_summary']['P1'][sub][e]) for e in ('hill','moment','gpd')],
   v['primary_summary']['P1'][sub]['tail_tasks'],
   'да' if v['primary_summary']['P1'][sub]['sufficient_sample'] else 'нет']
  for m,v in M.items() for sub in ('verified','refuted_all')])
table(['Модель','Интервал разности моментных оценок'],
 [[names[m],ci(v['primary_summary']['P1_difference']['ci95'])] for m,v in M.items()])
para('Точечные моментные оценки находятся в ожидаемом порядке, но интервалы разности включают ноль. '
     'Некоторые хвостовые подвыборки малы; у Kimina одна из GPD-оценок недоступна. Hill всегда положителен '
     'и сам по себе не позволяет выбрать лёгкий хвост. Неположительная знаковая оценка не должна '
     'заранее обрезаться до нуля; параметр порядка ξ=max(γ,0) и оценка γ сообщаются раздельно. '
     'Новая диагностика сдвигов не пересчитывает P1 и не меняет его неопределённый статус.')

para('**P3 и калибровка whitening.**')
table(['Модель','Допустимые шаги: исходная калибровка','Допустимые: разделённая','Ошибки: исходная','Ошибки: разделённая'],
 [[names[m],pct(v['controls']['whitening-01']['variant']['threshold']['evaluation']['accepted_evaluation']['exceedance_rate']),
   pct(v['controls']['whitening-04']['variant']['threshold']['evaluation']['accepted_evaluation']['exceedance_rate'],2),
   pct(v['controls']['whitening-01']['variant']['threshold']['evaluation']['first_failure']['exceedance_rate']),
   pct(v['controls']['whitening-04']['variant']['threshold']['evaluation']['first_failure']['exceedance_rate'],2)] for m,v in M.items()])
para('В исходном варианте одни калибровочные задачи использованы для подгонки whitening и выбора порога; '
     'оценочные задачи при этом отдельные. В контрольном варианте задачи для преобразования и порога также разделены, '
     'что одновременно уменьшает объём каждой подгонки. Исчезновение массовых превышений не следует приписывать '
     'единственной причине без дальнейших контролей. Оно показывает сильную зависимость результата от калибровки. '
     'Высокая исходная доля обнаруженных ошибок сопровождалась высокой долей срабатываний на допустимых шагах. '
     'Поэтому она не подтверждает сама по себе связь порога с корректностью или закон overshoot.')

para('**P4: обучение и хвостовой переход.**')
p4=data['P4'];npairs=len(p4['paired_delta']['moment']['values'])
para(f"В отдельном эксперименте модульного сложения проверены {npairs} пар обучений с настоящими и перемешанными метками. "
     f"Средняя итоговая тестовая точность: {pct(p4['aggregate']['real']['test_acc_mean'],3)} "
     f"против {pct(p4['aggregate']['null']['test_acc_mean'],3)} у контроля. "
     'Обобщение основной модели воспроизведено. Однако ранее выполненный аудит показывает, что '
     'медианные знаковые хвостовые оценки уже неположительны перед переходом; снижение зависит от доли хвоста. '
     'Это не установленный переход ξ из положительного значения в ноль.')
table(['Оцениватель','Среднее парное изменение real−null','Пар со снижением'],
 [[k,num(v['mean'],4),f"{v['n_negative']} / {len(v['values'])}"] for k,v in p4['paired_delta'].items()])
para('Число независимых единиц здесь — парные обучения, а не количество сохранённых checkpoint. '
     'Увеличение числа checkpoint не заменяет независимые seed.')

para('**P5: технический ремонт и научная проверка.**')
table(['Режим','Попыток','Подходящий формат','Верных выводов'],
 [[a,v['attempts'],f"{v['format_eligible']} ({pct(v['format_fraction'])})",
   f"{v['verified']} ({pct(v['verified_fraction'])})"] for a,v in data['P5']['arms'].items()])
support=data['P5']['arms']['guided']['calibration_support']
support={(x['temperature'],x['calibration_tasks'],x['increments']) for x in support}
para('Ограничение формата устранило потери на разборе ответа; семантический проверяющий сохранён. '
     'Прироста правильности на этом малом пилоте не установлено. '
     'Поддержка калибровки guided: '+ '; '.join(f"T={t}: {n} задач, {k} приращений на слой" for t,n,k in sorted(support))+
     '. Этого недостаточно для проверки хвостового закона по длине. '
     'Техническую доступность данных следует отличать от статистической достаточности.')

para('**Связь с исходной статьёй.**')
para('В PDF, раздел 5, P2 на странице 9, таблица 2 на странице 10 и описание на странице 22 прямо '
     'предусматривают сравнение с token-surprisal. Теорема 4 на странице 6 не формулирует превосходство над ним: '
     'это дополнительное эмпирическое требование. Более того, при соответствующих предпосылках теоремы '
     'локализация относится к обеим гипотезам механизма, а не только к тяжёлым хвостам. '
     'Даже успешная локализация в отдельности не различает алгоритмический и эвристический механизмы. '
     'Важны предпосылки coupling, стационарности, зависимости экстремумов и режима редких отказов. '
     'Нынешние конечные данные не устанавливают выполнение всех этих предпосылок.')
para('[Исходный черновик статьи](onebigjumpdraft.pdf).')

para('**Дальнейший план.**')
para('1. Завершить независимую проверку более точной сегментации Lean: границы тактик, вложенные блоки, '
     'первый реально исполненный ошибочный шаг и согласованность с проверкой всего доказательства. '
     'Сохранить отдельную версию меток и сопоставление со старой; исходные результаты не перезаписывать.')
para('2. Проверить новую разметку на имеющихся генерациях. Для новых границ использовать сохранённые токены; '
     'если нужных внутренних состояний нет среди старых снимков, потребуется дополнительный teacher-forcing, '
     'но не обязательная повторная генерация. Отдельно оценить первый переход и переходы между формальными тактиками.')
para('3. Для гипотезы о запаздывании заранее зафиксировать знак и величину сдвига на разработочной части '
     'и оценить её на независимых задачах. Сохранить точную локализацию, сдвинутую локализацию и покрытие окном '
     'как разные показатели. Сравнивать с позицией первого шага, surprisal и контролем позиций/длин. '
     'Будущий скачок трактовать как ретроспективный сигнал.')
para('4. Закрепить независимые задачи для подгонки whitening и выбора порога; исследовать достаточность '
     'размера калибровки относительно размерности. Повторно оценить P1/P3 с учётом устойчивости оценивателей '
     'и ограниченного числа задач в хвосте. Не ослаблять критерии только ради положительного исхода.')
para('5. Для P5 сначала увеличить число независимых правильных калибровочных задач, затем проверять зависимость '
     'от длины. Для P4 сначала проверить устойчивость определения хвостового параметра и привязку к механистическим '
     'признакам обучения; после этого планировать дополнительные независимые обучения.')

para('**Происхождение и ограничения отчёта.**')
para('Все численные таблицы и рисунки этого отчёта сформированы программой из metrics.json. '
     'Основные метрики воспроизведены из сохранённого deviations.parquet; хеши прямых входов сопоставлены '
     'с исходными манифестами. Подвыборка численной сверки активаций ограничена и не является полным повторным аудитом '
     'генерации, токенизатора или Lean. Первоначальная попытка аудита завершила расчёты, но остановилась при записи '
     'происхождения из-за отсутствующего по ожидаемому пути PDF; её исходник и журнал сохранены. '
     'Успешный повтор использует тот же диагностический план и формулы.')
para('Снимок исходного основного конвейера: lean-local-toolchain-v7; git commit: '+str(manifest['git_commit'])+
     '; дерево при запуске было '+('изменено' if manifest['git_dirty'] else 'чистым')+
     '. Точные хеши, конфигурация, версии пакетов, сведения об узле, воспроизводимые таблицы по трассам '
     'и границы применимости доступны в manifest.json, render-manifest.json, checks.json и metrics.json. '
     'Отчёт предназначен для научного обсуждения; он не утверждает подтверждение исходных P1–P5.')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,3,figsize=(13,7.2))
ds_offsets=data['plan']['fixed_offsets'];xx=np.arange(len(ds_offsets))
for col,(m,v) in enumerate(M.items()):
 a=v['subsets']['all'];n=a['position_null'];kk=['lag_%+d'%d for d in ds_offsets]
 for row,obs,expected,label in [(0,a['rates'],a['uniform_chance'],'Равномерный выбор'),
                               (1,n['observed'],n['null_mean'],'Позиционный контроль')]:
  ax=axes[row,col]
  ax.bar(xx-.17,[obs[k]*100 for k in kk],width=.34,label='Наблюдение',color='#206592')
  ax.bar(xx+.17,[expected[k]*100 for k in kk],width=.34,label=label,color='#c78443')
  ax.set_xticks(xx,[f'{d:+d}' for d in ds_offsets]);ax.set_ylim(0,100)
  ax.set_xlabel('D = максимум − ошибка')
  ax.set_title(names[m]+('\nВсе допустимые трассы' if row==0 else '\nОдна трасса на задачу, ограниченные группы'))
  ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
  if col==0:ax.set_ylabel('Доля совпадений, %')
  ax.legend(fontsize=8)
fig.suptitle('Сдвиг максимального скачка: сравнивать нужно на одинаковых подвыборках',fontsize=13)
fig.tight_layout(rect=(0,0,1,.95))
fig.savefig(D/'offsets.png',dpi=180);fig.savefig(D/'offsets.pdf');plt.close(fig)

report='\n\n'.join(chunks)+'\n'
(D/'REPORT_RU.md').write_text(report)
shutil.copyfile(HERE/'onebigjumpdraft.pdf',D/'onebigjumpdraft.pdf')
# Minimal Markdown-to-HTML renderer, supporting only syntax actually emitted above.
def inline(s):
 s=html.escape(s)
 s=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',s)
 s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',s)
 return s
body=[]
for c in chunks:
 if c.startswith('|'):
  lines=c.splitlines();heads=[x.strip() for x in lines[0].strip('|').split('|')]
  rows=[[x.strip() for x in l.strip('|').split('|')] for l in lines[2:]]
  body.append('<div class="table"><table><thead><tr>'+''.join('<th>'+inline(x)+'</th>' for x in heads)+
              '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table></div>')
 elif c.startswith('!['):
  b64=base64.b64encode((D/'offsets.png').read_bytes()).decode()
  body.append('<figure><img alt="Смещения максимального скачка" src="data:image/png;base64,'+b64+'"></figure>')
 else:body.append('<p>'+inline(c)+'</p>')
css='''body{font:16px/1.55 Georgia,serif;color:#182431;background:#fff;max-width:1120px;margin:40px auto;padding:0 32px}
p{margin:1em 0}p:first-child{font-size:27px}.table{overflow-x:auto;margin:22px 0}table{border-collapse:collapse;width:100%;font:13px/1.5 Arial,sans-serif}
th{text-align:left;background:#eaf0f4}th,td{border-bottom:1px solid #d8e0e5;padding:9px 10px}img{max-width:100%;height:auto}
figure{margin:26px 0}a{color:#145e87}strong{color:#142d43}@media print{body{margin:0;padding:0;font-size:11pt;max-width:none}
table{font-size:8pt}tr,figure{break-inside:avoid}p{orphans:3;widows:3}@page{size:A4;margin:18mm}}'''
(D/'REPORT_RU.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ONE BIG JUMP — отчёт</title><style>'+
 css+'</style><body>'+''.join(body)+'</body></html>')
# Produce a typeset PDF if ReportLab is already available; do not install anything.
pdf_status='reportlab unavailable; standalone HTML is ready for browser printing'
try:
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image
 from reportlab.lib import colors
 from reportlab.lib.styles import getSampleStyleSheet
 from reportlab.pdfbase import pdfmetrics
 from reportlab.pdfbase.ttfonts import TTFont
 from reportlab.lib.enums import TA_LEFT
 from matplotlib import font_manager
 fontpath=font_manager.findfont('DejaVu Sans')
 boldpath=font_manager.findfont(font_manager.FontProperties(family='DejaVu Sans',weight='bold'))
 pdfmetrics.registerFont(TTFont('DejaVu',fontpath));pdfmetrics.registerFont(TTFont('DejaVuBold',boldpath))
 pdfmetrics.registerFontFamily('DejaVu',normal='DejaVu',bold='DejaVuBold',italic='DejaVu',boldItalic='DejaVuBold')
 styles=getSampleStyleSheet()
 styles['BodyText'].fontName='DejaVu';styles['BodyText'].fontSize=9;styles['BodyText'].leading=13
 styles['BodyText'].spaceAfter=7
 from reportlab.lib.styles import ParagraphStyle
 small=ParagraphStyle('small',parent=styles['BodyText'],fontSize=7,leading=10)
 def ptext(s):return re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',html.escape(s))
 story=[]
 for c in chunks:
  if c.startswith('|'):
   ls=c.splitlines();rows=[[x.strip() for x in l.strip('|').split('|')] for l in [ls[0],*ls[2:]]]
   values=[[Paragraph(ptext(x),small) for x in row] for row in rows]
   tab=Table(values,colWidths=[495/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign='LEFT')
   tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf0f4')),
       ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.3,colors.lightgrey),
       ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
   story.extend([tab,Spacer(1,12)])
  elif c.startswith('!['):story.extend([Image(str(D/'offsets.png'),width=495,height=274),Spacer(1,10)])
  else:story.append(Paragraph(ptext(re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1',c)),styles['BodyText']))
 def footer(canvas,doc):
  canvas.setFont('DejaVu',8);canvas.drawRightString(545,25,str(doc.page))
 SimpleDocTemplate(str(D/'REPORT_RU.pdf'),pagesize=(595,842),rightMargin=50,leftMargin=50,topMargin=40,bottomMargin=40).build(story,onFirstPage=footer,onLaterPages=footer)
 pdf_status='created'
except ImportError:pass
inputs={str(D/'metrics.json'):sha(D/'metrics.json'),str(D/'manifest.json'):sha(D/'manifest.json'),
        str(HERE/'render.py'):sha(HERE/'render.py')}
outputs={str(D/n):sha(D/n) for n in ('REPORT_RU.md','REPORT_RU.html','offsets.png','offsets.pdf','onebigjumpdraft.pdf')}
if (D/'REPORT_RU.pdf').exists():outputs[str(D/'REPORT_RU.pdf')]=sha(D/'REPORT_RU.pdf')
receipt={'stage':'supervisor-report-render','job':os.environ['SLURM_JOB_ID'],'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'git_commit':os.environ.get('ONEBIGJUMP_GIT_COMMIT'),'git_dirty':bool(os.environ.get('ONEBIGJUMP_GIT_STATUS')),
         'environment':manifest['environment'],'config':{'data_job':data['job'],'format':'Markdown + standalone HTML + plots','pdf_status':pdf_status},
         'inputs':inputs,'outputs':outputs}
(D/'render-manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print('REPORT_READY',str(D),'PDF:',pdf_status)
