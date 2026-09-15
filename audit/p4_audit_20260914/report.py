from pathlib import Path
import json, time, hashlib, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path('/beegfs/home/denis.rakhmankin/onebigjump/audit/p4_audit_20260914')
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
runs=read('runs.json'); ser=read('series.json'); win=read('windows.json'); sen=read('sensitivity.json'); summary=read('summary-audit.json'); paired=read('original-paired-summary.json'); checks=read('checks.json'); forward=read('forward-reconstruction.json')
def fmt(x,n=4):return '—' if x is None else f'{x:.{n}f}'
def table(headers,rows):
 return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(str(x) for x in row)+' |' for row in rows)+'\n'
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
colors=plt.get_cmap('tab10').colors
fig,axes=plt.subplots(3,2,figsize=(12,10),sharex=True)
for j,arm in enumerate(['real','null']):
 for seed in range(5):
  rr=ser[f'{arm}-{seed}']; x=[c['step'] for c in rr]
  for i,key in enumerate(['test_acc','moment','gpd']):
   vals=[np.nan if c[key] is None else c[key] for c in rr]
   axes[i,j].plot(x,vals,color=colors[seed],lw=1,alpha=.85,label=f'seed {seed}')
  ref=paired['pairs'][seed]['real_reference_step']
  for i in range(3):axes[i,j].axvline(ref,color=colors[seed],alpha=.2,lw=.7,ls=':')
 axes[0,j].set_title('Modular addition' if arm=='real' else 'Shuffled-label control')
 axes[0,j].set_ylim(-.025,1.025)
 for i,key in enumerate(['Held-out accuracy','Moment shape, k=638','GPD shape, k=638']):
  axes[i,j].set_ylabel(key);axes[i,j].grid(alpha=.18)
  if i:axes[i,j].axhline(0,color='black',lw=.7);axes[i,j].set_ylim(-.65,.2)
 axes[-1,j].set_xlabel('Optimizer updates')
axes[0,1].legend(loc='upper left',fontsize=8)
fig.suptitle('P4 audit: learning replicates; a heavy-to-light tail transition does not',fontsize=14)
fig.text(.5,.012,'Each colour is one training seed. Dotted lines: real-run accuracy anchor. Signed estimates; no confidence bands.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.03,1,.96])
for ext in ['png','pdf']:fig.savefig(OUT/f'p4_training_curves.{ext}',dpi=160)
plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,4.6))
for i,name in enumerate(['moment','gpd']):
 for seed in range(5):
  r=sorted([x for x in sen if x['seed']==seed and x['arm']=='real' and x['split']=='all'],key=lambda x:x['fraction'])
  axes[i].plot([100*x['fraction'] for x in r],[x[name+'_delta'] for x in r],marker='o',color=colors[seed],label=f'seed {seed}')
 axes[i].axhline(0,color='black',lw=.8);axes[i].axvline(5,color='grey',ls=':',lw=1)
 axes[i].set_xlabel('Upper tail fraction (%)');axes[i].set_ylabel('Median after minus median before');axes[i].set_title(name.upper());axes[i].grid(alpha=.2)
axes[1].legend(fontsize=8);fig.suptitle('Same checkpoints, different thresholds: direction is not stable')
fig.tight_layout()
for ext in ['png','pdf']:fig.savefig(OUT/f'p4_threshold_sensitivity.{ext}',dpi=180)
plt.close(fig)
tail=summary['tail'];rmain=[r for r in runs if r['arm']=='real'];rnull=[r for r in runs if r['arm']=='null']
headline_rows=[]
for seed in range(5):
 r=rmain[seed];n=rnull[seed];p=paired['pairs'][seed]
 headline_rows.append([seed,r['ref90'],f"{100*r['test_acc_last']:.3f}%",f"{100*n['test_acc_last']:.3f}%",fmt(p['real']['hill']),fmt(p['real']['moment']),fmt(p['real']['gpd'])])
levelrows=[]
for seed in range(5):
 m=next(x for x in win if x['seed']==seed and x['arm']=='real' and x['metric']=='moment')
 g=next(x for x in win if x['seed']==seed and x['arm']=='real' and x['metric']=='gpd')
 levelrows.append([seed,fmt(m['before']),fmt(m['after']),fmt(g['before']),fmt(g['after'])])
sensrows=[]
for f in [.01,.025,.05,.10]:
 x=next(x for x in summary['sensitivity_summary'] if x['split']=='all' and x['fraction']==f)
 sensrows.append([f'{100*f:g}%',round(12769*f),f"{x['moment_n_drop']}/5",f"{x['gpd_n_drop']}/5",fmt(x['moment_mean_delta']),fmt(x['gpd_mean_delta'])])
problem=next(x for x in read('full-tail.json') if x['arm']=='real' and x['seed']==2 and x['step']==20000)
text=f"""# Аудит P4 — 14 сентября 2026

Проверены реализация, исходный снимок, сохранённые измерения и контрольные запуски. **Обучение модульному сложению воспроизведено, заявленный устойчивый переход хвостового параметра не установлен.** В старой версии были реальные ошибки. Новая серия исправляет их, но сохраняет проблемы с надёжностью интервалов и интерпретацией отрицательного результата.

Это аудит существующих данных. Нового обучения нет. Проверки выполнялись через Slurm на CPU, основная сверка заняла {read('provenance.json')['elapsed_s']:.1f} с вычисления. Скрипты и исходные результаты сохранены рядом с отчётом. Две первые служебные попытки остановились до вычислений: отсутствующая документация в снимке и повторная запись файла с режимом read-only. Их журналы сохранены.

## Что именно проверялось

P4 относится к обучению небольшой модели, а не к корпусу 20 016 доказательств Lean. Проверенная реализация охватывает модульное сложение. Для двухшаговой композиции и рекуррентной глубины, также перечисленных в проектном протоколе, здесь результатов нет.

Задача: для a,b из {{0,…,112}} предсказать (a+b) mod 113. Всего 113² = 12 769 входов; обучение на 3830, отложенная проверка на 8939. Вход имеет три токена: a, b, знак «=». Один transformer-блок, d=128, четыре головы внимания, MLP=512, ReLU, без LayerNorm. AdamW: lr=0.001, weight_decay=1, betas=(0.9,0.98), полный обучающий батч, 40 000 обновлений, сохранение каждые 100 обновлений.

Пять seed, для каждого пара real/null. У null перемешаны правильные ответы по входам с сохранением общего распределения меток. В каждой паре **совпали начальные веса, состояние оптимизатора, обучающие и тестовые индексы**; единственная разница настройки задачи — shuffle_labels. Train и test не пересекаются. Все десять моделей достигают 100% точности на обучающей выборке.

На каждом из 401 checkpoint одной модели измеряется

    Z_s(a,b) = ||h_s^(1)(a,b,=) − h_s^(0)(a,b,=)||₂
               / median_{{u,v}} ||h_s^(1)(u,v,=) − h_s^(0)(u,v,=)||₂.

Индекс s здесь — обновление весов. Для каждого входа берётся один вектор приращения блока на последней позиции. Распределение строится по разным входам, не по изменениям весов между checkpoint и не по шагам доказательства. Всего сохранено 4010 checkpoint-измерений, но независимых пар обучений лишь пять.

В основной кривой используются верхние 638 значений (около 5%), считаются Hill, moment и GPD. Масштабирование общей медианой не изменяет эти оценки формы хвоста. Оно само по себе не создаёт эффект P4.

Момент перехода T — первое из пяти последовательных сохранений с test accuracy ≥90%. До и после сравниваются медианы пяти точек в окнах [T−500,T) и (T,T+500]. Точка T исключена. Контроль сравнивается в те же моменты, которые определены по real.

    Δγ = median(γ после T) − median(γ до T).
    D_seed = Δγ_real − Δγ_null.

Отрицательная Δγ означает снижение оценки. Это заранее заданное правило в использованном снимке; оно не выбирает самый удачный спад хвоста. Случайные seed не отбрасываются по результату.

## Полученные числа

{table(['Seed','T: обновления','Test real, финал','Test null, финал','Δ Hill','Δ moment','Δ GPD'],headline_rows)}
Средняя итоговая test accuracy: real **{100*summary['aggregate']['real']['test_acc_mean']:.3f}%**, null **{100*summary['aggregate']['null']['test_acc_mean']:.3f}%**. Случайное угадывание: 1/113 ≈ {100/113:.3f}%. Следовательно, провал подтверждения P4 нельзя объяснить тем, что основная модель вообще не научилась задаче.

При основной доле 5% moment и GPD снижаются в четырёх seed из пяти. У seed 2 обе оценки растут. В парном сравнении средняя D равна {summary['paired_delta']['moment']['mean']:.5f} для moment, {summary['paired_delta']['gpd']['mean']:.5f} для GPD и {summary['paired_delta']['hill']['mean']:.5f} для Hill. Это описательные величины; доверительных интервалов по независимым обучениям эти числа не имеют.

**Оценки уже отрицательны до перехода:**

{table(['Seed','moment до','moment после','GPD до','GPD после'],levelrows)}
Поэтому даже наблюдаемый спад нельзя описывать как установленное исчезновение тяжёлого хвоста. На уровне медианных оценок параметр ξ̂=max(γ̂,0) равен нулю и до, и после.

На всех checkpoint real положительных moment-оценок {summary['aggregate']['real']['moment_positive_checkpoints']} из {summary['aggregate']['real']['n_checkpoints']} ({100*summary['aggregate']['real']['moment_positive_checkpoints']/summary['aggregate']['real']['n_checkpoints']:.2f}%); у null {summary['aggregate']['null']['moment_positive_checkpoints']} из {summary['aggregate']['null']['n_checkpoints']} ({100*summary['aggregate']['null']['moment_positive_checkpoints']/summary['aggregate']['null']['n_checkpoints']:.2f}%). Эти доли описывают временные кривые; checkpoint нельзя считать независимыми повторениями эксперимента.

![Кривые обучения и оценки хвоста](p4_training_curves.png)

## Что подтвердилось при независимой проверке

- Хеши исходных файлов использованного снимка совпали с source manifest.
- Проверены все 4010 скалярных файлов измерений и 50 файлов полного хвостового анализа по их manifest: расхождений нет.
- Проверены хеши 100 наборов норм около переходов и 16 выбранных сохранений весов.
- В 16 прямых проходах заново получены нормы, точность и Fourier-loss: совпадение с сохранёнными значениями точное в использованной среде.
- Формулы Hill и moment на 100 сохранённых выборках проверены отдельно от вызова основного оценивателя. Максимальная ошибка округления: {next(x for x in checks if x['check']=='independent_moment_hill_arithmetic')['max_abs_error']}.
- Синтетические Fourier-компоненты проверяют сохранение постоянной компоненты, исключение смешанных частот и сохранение выбранной частотной пары. Результаты: fourier-mask-controls.json.

Это подтверждает корректность проверенной арифметики и соответствие артефактов весам. Это не проверка всей истории каждого из 40 000 обновлений и не доказательство научной гипотезы.

## Реальные ошибки старой версии

История Git подтверждает, что прежние выводы нельзя смешивать с новой серией.

1. **Hill назывался γ и параметром порядка.** В analyse_p4 использовался c.hill вместо знаковой moment-оценки. Hill неотрицателен по определению и не позволяет утверждать, что хвост тяжёлый только потому, что оценка положительна. Исправление: a3988f7.
2. **Неверная Fourier-проекция.** Сохранялись целые строки и столбцы спектра, включавшие посторонние и смешанные частоты; исключённая часть теряла постоянную компоненту. Теперь сохраняются пары одинаковой частоты и DC.
3. **Excluded loss считался по всем входам.** Для измерения остаточного запоминания он должен оцениваться на train; текущий код это делает.
4. **Частоты менялись от checkpoint к checkpoint.** В текущем durable-пути частоты выбираются один раз по финальной модели и затем фиксируются при повторном измерении.
5. **Коллизии имён публикуемых файлов и manifest.** Ранее null мог перезаписать real при одинаковом seed. В проверенной серии разные каталоги real-N/null-N, хеши и отдельные manifest.

Изменения Fourier-проекции и split подтверждаются коммитом 5302b9f. Старые скалярные loss-логи невозможно исправить простым переименованием; для новой серии доступны веса и повторные измерения.

## Проблемы, которые остались

### 1. Направление эффекта зависит от выбранной части хвоста

Диагностическая сетка 1%, 2.5%, 5%, 10% применена к тем же десяти точкам вокруг T, без обучения и без изменения T.

{table(['Верхняя доля','k, все входы','Снижение moment','Снижение GPD','Средняя Δ moment','Средняя Δ GPD'],sensrows)}
![Чувствительность к порогу](p4_threshold_sensitivity.png)

В частности, seed 4 даёт Δmoment={next(x['moment_delta'] for x in sen if x['seed']==4 and x['arm']=='real' and x['split']=='all' and x['fraction']==.05):+.4f} на 5%, но {next(x['moment_delta'] for x in sen if x['seed']==4 and x['arm']=='real' and x['split']=='all' and x['fraction']==.01):+.4f} на 1%. Для GPD соответствующие значения {next(x['gpd_delta'] for x in sen if x['seed']==4 and x['arm']=='real' and x['split']=='all' and x['fraction']==.05):+.4f} и {next(x['gpd_delta'] for x in sen if x['seed']==4 and x['arm']=='real' and x['split']=='all' and x['fraction']==.01):+.4f}.

На 10% обе оценки снижаются во всех пяти real, на 1% — только в двух. Показывать только удачную долю было бы выбором результата после просмотра. Основная доля 5% зафиксирована в запуске, поэтому сама её реализация не доказывает подгонку. Но устойчивость содержательного вывода к порогу отсутствует.

Анализ выполнен также отдельно на train и test; все значения сохранены в sensitivity.csv. При 5% только на test moment снижается в 5/5, GPD — в 4/5. Следовательно, проблема не сводится к одному явному перемешиванию train/test: оценки, пороги и смысл сравнения требуют отдельного контроля.

### 2. GPD-интервал может появиться даже при отсутствии пригодной точечной оценки

Полный хвостовой анализ завершён на сетке 0, 10 000, 20 000, 30 000, 40 000 для десяти моделей: {tail['n']} срезов. Автовыбор k дал k=20 в {tail['k20']} срезах и k≤30 в {tail['k_le30']}.

В {tail['gpd_missing']} срезах пригодная точечная GPD-оценка отсутствует, **но интервал всё равно записан**. В {tail['gpd_valid_lt_half']} из {tail['n']} срезов успешны менее половины из 500 bootstrap-повторов.

Конкретный пример: real-2, шаг 20 000, k={problem['k']}. Пригодная точечная оценка — null; успешны **{problem['gpd_n_valid']}/{problem['gpd_n_resamples']}** повторов; тем не менее записан «95% CI» **[{problem['gpd_ci_low']:.4f}, {problem['gpd_ci_high']:.4f}]**. Это процентили небольшого, зависимого от сходимости подмножества, и номинальное покрытие 95% ими не обосновано.

Дополнительная диагностика на этом срезе дала 96 непригодных endpoint-решений из 100 попыток и 4 пригодных. Это диагностические повторы с отдельным seed, не замена исходным 500. Код правильно отвергает нерегулярное решение GPD с γ≤−1, однако group_bootstrap затем молча пропускает неудачи и выдаёт интервал, если осталось хотя бы два числа. Ошибка находится в допуске интервала к отчёту и отсутствии явного статуса его пригодности. Она не меняет основную сводку Δ при фиксированных 5%.

Нужно возвращать no_reliable_interval при непригодной точечной оценке или существенном отборе bootstrap-повторов; сохранять причины неудач, заранее проверять покрытие выбранной процедуры на контролях. Произвольная граница доли успешных повторов сама по себе покрытие не гарантирует.

### 3. Полные интервалы не стоят непосредственно на переходе

Плотная кривая использует фиксированные 5% и точечные оценки. Полный расчёт использует иной k и редкую сетку через 10 000 обновлений. Ни один T не совпадает с этой сеткой. Поэтому интервалы из full-tail нельзя приписывать таблице Δ выше.

Кроме того, k фиксируется внутри повторов, неопределённость его выбора не включена; bootstrap условный по одной обученной модели. Все 12 769 входов — полная конечная совокупность задачи: их ресемплирование не заменяет вариацию между независимо обученными моделями.

Флаг identified прошёл {tail['identified']}/{tail['n']} срезов, и все они относятся к начальным весам. После начала обучения — {tail['identified_after_initialization']}/{tail['n_after_initialization']}. Сам этот флаг проверяет плато по k и согласие оценок, а не положительность γ и не алгоритмичность.

### 4. В legacy-анализе остался некалиброванный способ объявлять P4 «непроверенным»

xi_moves=True выставляется, если ξ̂ превышает 1/√k минимум в 10% checkpoint. Это эвристика без калиброванного уровня ошибки; она зависит даже от того, как долго сохранять уже сошедшуюся модель. При k=638 порог около {1/np.sqrt(638):.4f}. Такой критерий нельзя использовать для защиты гипотезы от отрицательных результатов.

Предсказание «γ падает около перехода» действительно проверялось и получило неоднородный результат. Более сильное утверждение «произошёл переход от тяжёлого хвоста к лёгкому» не подтверждено. Это разные формулировки; отсутствие первой картины нельзя автоматически переименовывать в отсутствие эксперимента.

Строка legacy-verdict о том, что всякий наблюдаемый тренд относится к Hill, также слишком сильна: текущие кривые moment/GPD могут меняться, оставаясь отрицательными. Их изменение реально как описательная статистика, но не равно изменению ξ.

### 5. Поздняя точность и появление вычислительного механизма — разные ориентиры

Использование первого устойчивого достижения 90% определяет момент высокой точности. Fourier-компоненты могут давать хорошее решение раньше, пока другие компоненты мешают полному выходу. Это соответствует различению circuit formation и cleanup у Nanda et al.

Фиксация частот по финальным весам допустима для ретроспективного анализа и не обучает модель на test labels. Но такой способ использует будущую модель; он не является онлайн-предсказателем перехода.

В нашей реализации выбраны шесть самых сильных частот embedding. В исходной работе важные частоты подтверждаются также через neuron-logit map и абляции. Эти процедуры не тождественны. Диагностика spectra.json показывает, что выбранные частоты объясняют примерно 88.6–94.2% Fourier-мощности neuron-logit map у real; результаты следует называть приближёнными progress measures, а не полной репликацией механистического анализа.

### 6. Низкий индекс хвоста не доказывает алгоритмическое обобщение

Контроль прекрасно запоминает train, почти не обобщает на test, но также имеет преимущественно отрицательные оценки. Значит, неположительный хвостовой индекс в данной реализации **недостаточен как признак освоенного обобщающего алгоритма**.

При фиксированных конечных весах и конечном множестве из 12 769 входов Z ограничено и все его моменты конечны. Буквальный асимптотический тяжёлый хвост здесь невозможен; исследуется только форма на промежуточных масштабах. Нельзя превращать отрицательную оценку из ограниченной выборки в доказательство природы вычисления. Это ограничение измеряемого объекта, а не неисправность обучения.

## Что делать с текущими результатами

1. Сохранить текущую серию как независимые пять пар и опубликовать отрицательные/неоднозначные наблюдения вместе со всеми порогами.
2. Исправить допуск GPD-интервалов к отчётам, legacy-интерпретацию и устаревшую строку full_k_bootstrap_status=\"queued\" — полный этап уже завершён. Исходные файлы в этом аудите не переписаны.
3. Задать отдельно проверяемые утверждения о форме хвоста, изменении формы и связи с механизмом. Сначала проверить, различает ли метрика контрольные случаи вообще.
4. Для основной оценки использовать явно выбранную популяцию входов; показывать train, held-out и pooled раздельно. Сетку k, критерий устойчивости и окна зафиксировать до новых результатов.
5. Отдельно привязать кривые к появлению Fourier-компетенции и к росту полной test accuracy. Для утверждения о предсказании использовать только доступную к тому моменту информацию.
6. После проверки измерителя планировать независимые seed и оценку вариации между обучениями. Увеличение числа seed при неисправных интервалах и неустойчивой метрике не решает основную проблему.

**Формулировка для коллег:** «В пяти парных обучениях на модульном сложении получено устойчивое обобщение основных моделей при отсутствии обобщения у контроля. Снижение знаковых хвостовых оценок около перехода наблюдается в четырёх из пяти запусков при основном пороге, однако зависит от выбора хвостовой области. Перед переходом медианные оценки уже неположительны; контроль также преимущественно даёт неположительные оценки. Поэтому P4 не подтверждает тяжёлый хвост как параметр порядка алгоритмического обобщения. Проверка обнаружила проблемы надёжности части GPD-интервалов; основные сохранённые точечные измерения воспроизводятся».

## Источники и воспроизведение

- Использованный снимок: audit/readiness_2026_09_11/snapshots/expansion-v1-20260911T024740Z.
- Исходные результаты: runs/expansion_20260911/p4.
- Документация проекта: sources/experimental_specification.md, разделы P4 и 5.3.
- Код: sources/p4.py, sources/p4_grokking.py, sources/grokking.py, sources/bootstrap.py, sources/gpd.py.
- История исправлений: history-fourier.patch, history-order-parameter.patch.
- Nanda et al., 2023: https://arxiv.org/pdf/2301.05217, §5.1–5.2 и Appendix C.2.
- audit.py / audit.sbatch: основная сверка, job 8466319.
- additional.py / additional.sbatch: агрегаты и диагностика endpoint-решений, job 8466328.
- Все подробные числа: runs.csv, windows.csv, sensitivity.csv, full-tail.csv, summary-audit.json.
- Метаданные и контрольные суммы: provenance.json, checks.json, artifact-manifest.json.

Новые p-value и подтверждающие статистические тесты по пилотным пяти парам не запускались. Диагностическая сетка и 300 повторов для проверки сходимости предназначены для аудита численного метода.
"""
(OUT/'REPORT_RU.md').write_text(text,encoding='utf-8')
# Self-contained lightweight HTML for sharing: embeds local generated figures and no remote JS.
import html,base64
try:
 import markdown
 body=markdown.markdown(text,extensions=['tables','fenced_code'])
except ImportError:
 body='<pre>'+html.escape(text)+'</pre>'
for name in ['p4_training_curves.png','p4_threshold_sensitivity.png']:
 body=body.replace('src="'+name+'"','src="data:image/png;base64,'+base64.b64encode((OUT/name).read_bytes()).decode()+'"')
page='<!doctype html><meta charset="utf-8"><title>Аудит P4</title><style>body{font:17px/1.65 system-ui,sans-serif;max-width:1120px;margin:40px auto;padding:0 25px;color:#17212b}table{border-collapse:collapse;font-size:15px;width:100%;margin:20px 0}th,td{border-bottom:1px solid #ddd;text-align:left;padding:8px}th{background:#eef2f6}h1,h2,h3{line-height:1.25}h2{margin-top:42px}pre{white-space:pre-wrap;background:#f2f4f5;padding:18px;font-size:14px}img{max-width:100%}a{color:#17608a}@media print{body{font-size:12px;margin:0}h2{page-break-after:avoid}table,img{break-inside:avoid}}</style>'+body
(OUT/'REPORT_RU.html').write_text(page,encoding='utf-8')
files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='artifact-manifest.json']
manifest={'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'job':os.environ.get('SLURM_JOB_ID'),'files':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if not p.name.endswith('.log')},'note':'Read-only scientific audit; original production artifacts unchanged; PDF attachment not transferred.'}
(OUT/'artifact-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('REPORTS_WRITTEN',len(text),len(page))
