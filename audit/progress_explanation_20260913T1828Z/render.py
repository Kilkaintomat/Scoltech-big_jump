import json, datetime, hashlib, shutil
from pathlib import Path
p=Path(__file__).parent
d=json.loads((p/'metrics.json').read_text(encoding='utf8'))
models=['deepseek','goedel','kimina']
names={'deepseek':'DeepSeek-Prover-V2-7B','goedel':'Goedel-Prover-V2-8B','kimina':'Kimina-Prover-Distill-8B'}
n=sum(d['models'][m]['n'] for m in models)
v=sum(d['models'][m]['categories'].get('verified',0) for m in models)
r=sum(d['models'][m]['categories'].get('localized_tactic_failure',0) for m in models)
tr=sum(d['models'][m]['categories'].get('generation_truncation',0) for m in models)
to=sum(d['models'][m]['categories'].get('timeout_resource',0) for m in models)
elapsed=sum(c['elapsed_s']['sum'] for m in models for c in d['models'][m]['by_category'].values())
timeout_elapsed=sum(d['models'][m]['by_category']['timeout_resource']['elapsed_s']['sum'] for m in models)
previous=Path('/beegfs/home/denis.rakhmankin/onebigjump/audit/colleague_brief_20260913T173153Z/evidence.json')
old=json.loads(previous.read_text(encoding='utf8'))
oldn=sum(x['labelled'] for x in old['main_progress'].values())
parse=lambda s:datetime.datetime.strptime(s.rstrip('Z'),'%Y-%m-%dT%H:%M:%S.%f')
hours=(parse(d['captured_utc'])-parse(old['captured_utc'])).total_seconds()/3600
rate=(n-oldn)/hours
remaining=20016-n
lines=['**Срез проверки One Big Jump: качество, сложность задач и длительность**','',
'Срез журналов: '+d['captured_utc']+' (UTC). Краткий аудит выполнен через Slurm; генерация и Lean-проверка не перезапускались.','',
'156 verified в старом срезе означают 156 принятых доказательств. 99 localized_tactic_failure — отдельная категория. Вычитание 156−99 не даёт числа правильных доказательств.','',
'**Текущие счётчики.** Это незавершённые выборки разного состава; по этой таблице нельзя ранжировать модели.','',
'| Модель | Обработано | verified | Локализованный отказ | Остальные категории |','|---|---:|---:|---:|---:|']
for m in models:
 x=d['models'][m];c=x['categories']
 lines.append('| {} | {} | {} | {} | {} |'.format(names[m],x['n'],c.get('verified',0),c.get('localized_tactic_failure',0),x['n']-c.get('verified',0)-c.get('localized_tactic_failure',0)))
lines+=['','Всего {}/20016 = {:.2f}%; принято {}; локализованных отказов {}; прочих {}.'.format(n,n/20016*100,v,r,n-v-r),'',
'**Одинаковые задачи.** Использованы только полностью прочитанные журналы shard-000 и shard-001: одинаковые 100 задач, по 16 ответов на задачу и модель, 8 при каждой температуре. Это описательный промежуточный срез; он включает калибровочные и оценочные задачи и не является итоговым miniF2F-test результатом.','',
'| Модель | Принятых ответов / 1600 | Доля | Решено задач хотя бы раз / 100 | При T=0.6, хотя бы раз из 8 | При T=1.0, хотя бы раз из 8 |','|---|---:|---:|---:|---:|---:|']
for m in models:
 c=d['matched_cohort']['models'][m]; a=c['categories']['verified']
 lines.append('| {} | {} | {:.2f}% | {} | {} | {} |'.format(names[m],a,a/1600*100,c['tasks_solved_at_least_once'],c['by_temperature']['0.6']['tasks_solved_at_least_once'],c['by_temperature']['1.0']['tasks_solved_at_least_once']))
lines+=['','**Различие семейств на том же срезе.** Формальные семейства не являются независимой измеренной шкалой сложности; более низкая доля может отражать также обрывы, стиль доказательств и ограничения проверяющего.','',
'| Семейство | Задач | Ответов на модель | DeepSeek | Goedel | Kimina |','|---|---:|---:|---:|---:|---:|']
for fam in ['mathd_algebra','imo']:
 fs=[d['matched_cohort']['models'][m]['by_family'][fam] for m in models]
 lines.append('| {} | {} | {} | {} | {} | {} |'.format(fam,fs[0]['tasks'],fs[0]['n'],*['{}/{} = {:.2f}%'.format(f['verified'],f['n'],100*f['verified']/f['n']) for f in fs]))
lines+=['','**Обрывы и время.** generation_truncation: {}/{} = {:.2f}%; timeout_resource: {}/{} = {:.2f}%. Последняя категория занимает {:.2f}% суммы elapsed_s в журналах. Это сумма времени обработки отдельных ответов, а не wall time всей кампании.'.format(tr,n,100*tr/n,to,n,100*to/n,100*timeout_elapsed/elapsed),'',
'Значение whole_proof_ok само по себе не заменяет verified: отдельно проверяются отсутствие дыр/запрещённых аксиом, полный ответ, ресурсы и согласованность пошаговой проверки.','',
'**Оценка оставшегося времени.** Между предыдущим срезом '+old['captured_utc']+' и текущим число записей выросло с {} до {} за {:.1f} минут: {:.0f} записей/час. Осталось {}. Простая линейная экстраполяция: {:.2f} часа на остаток проверки при той же скорости. Это не гарантированный срок и не срок готовности итоговых P1–P3.'.format(oldn,n,hours*60,rate,remaining,remaining/rate),'',
'На контрольных 48 трассах завершённый benchmark двух работников дал {:.3f}x ускорение ({:.2f} → {:.2f} секунд), 48/48 совпадений с последовательным вариантом и архивной разметкой. Один раунд короткого теста не гарантирует такого ускорения на полной серии.'.format(d['guarded_benchmark']['speedup'],d['guarded_benchmark']['serial_seconds'],d['guarded_benchmark']['parallel_seconds']),'',
'**Блокировка.** kimina/main-verify-1 завершился FAILED после записи всех 752 исходов из-за несогласия whole-proof/replay. В прочитанных журналах Kimina два таких примера: mathd_algebra_215:T1.0:a06 и aime_1984_p15:T1.0:a01. Полная проверка проходит, пошаговая — нет. В queue downstream Kimina BLOCKED; ожидание времени не снимает эту причину.','',
'В первом примере преобразование отступов повреждает <;>. Во втором all_goals отрывается от своей вложенной тактики. Эти случаи требуют исправления/проверки разметки, а не объявления математической ошибки модели.','',
'Goedel job 8466170 остановился на импорте Mathlib с Too many open files in system. Позже диспетчер запустил 8466180 с ограничением числа работников. Это инфраструктурный отказ, а не результат решения задач.','',
'**Как отделить причины.** Сравнить исходный проверяющий и независимую полную компиляцию на заранее выбранных примерах всех категорий; прогнать эталонные доказательства тех же задач; отдельно повторить ресурсные случаи с повышенным бюджетом; сравнить генерацию с исходным и увеличенным лимитом токенов на одинаковых заранее выбранных задачах, включая контроль без обрывов. Эти дополнительные эксперименты здесь не выполнялись.','',
'Источники и хеши журналов: [metrics.json](metrics.json), [manifest.json](manifest.json). Код расчёта: [audit.py](audit.py).','']
(p/'REPORT_RU.md').write_text('\n'.join(lines),encoding='utf8')
for source,name in [
('/beegfs/home/denis.rakhmankin/onebigjump/runs/lean_reverification_20260913_local/logs/obj0913local-goedel-main-verify-3-8466170.log','goedel-infrastructure-failure.log'),
('/beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_13/statistical-fitness-v1/benchmark-guarded/metrics.json','guarded-benchmark.json')]:
 shutil.copyfile(source,str(p/name))
print('REPORT_READY',n,rate,remaining/rate)
