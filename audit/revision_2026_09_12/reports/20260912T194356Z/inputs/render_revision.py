"""Render a reviewable revision report from immutable status inputs and run manifests."""
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.generation import planned_requests

folder=Path(sys.argv[1]); inputs=folder/'inputs'; config=read_json(inputs/'config.json')
source=Path(config['source'])/'source-manifest.json'
queue=read_json(inputs/'queue.json'); root=Path(config['campaign'])
accounting={}
for line in (inputs/'accounting.txt').read_text().splitlines():
    values=line.split('|')
    if len(values)>=5:
        accounting[values[0]]={'state':values[1],'exit_code':values[2],'elapsed':values[3],'node':values[4]}
for task in queue['tasks'].values():
    if task.get('job_id') in accounting:
        task['state']=accounting[task['job_id']]['state']
required=[source,Path(config['p3_summary']),Path(config['historical_p3']),Path(config['runtime_manifest'])]
for path in required:verify_manifest(path)
p3=read_json(Path(config['p3_summary']).parent/'metrics.json')
historical=read_json(Path(config['historical_p3']).parent/'metrics.json')
runtime=read_json(config['runtime_manifest'])
reg_folder=root.parents[1]/'audit/revision_2026_09_12'/('regression-'+config['regression'])
reg=None
if (reg_folder/'manifest.json').exists():
    verify_manifest(reg_folder/'manifest.json');required.append(reg_folder/'manifest.json')
    reg=read_json(reg_folder/'metrics.json')
tests={}
for path in inputs.glob('*.xml'):
    suites=list(ET.parse(path).getroot().iter('testsuite'))
    tests[path.name]={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
identity=Path(config['historical_p3']).parent.parent/('runtime-identity-'+config['runtime_identity'])/'manifest.json'
verify_manifest(identity);required.append(identity)
models={}
for name in ('deepseek','goedel','kimina'):
    model=root/name; protocol=read_json(model/'main/protocol.json')
    requests=planned_requests(model,'main',protocol)
    generation=[Path(p) for p in config['generation_manifests'][name]]
    manifests=[read_json(p) for p in generation]
    log=inputs/(name+'-pilot-verify.log')
    progress=re.findall(r'^verified (\d+) / (\d+) ',log.read_text(encoding='utf-8',errors='replace'),re.M) if log.exists() else []
    protocols={}
    for phase in ('pilot','main'):
        current=model/phase/'protocol.json'
        previous=Path(config['previous_campaign'])/name/phase/'protocol.json'
        assert digest(current)==digest(previous),'Protocol changed: '+name+'/'+phase
        protocols[phase]=digest(current)
        required.extend([current,previous])
    smoke=model/'checks'/('lean-smoke-'+source.parent.name)/'manifest.json'
    if smoke.exists():verify_manifest(smoke);required.append(smoke)
    models[name]={'pilot_progress':{'rows_in_log':int(progress[-1][0]) if progress else 0,'final':False},
        'protocol_sha256':protocols,'generation_is_original':(model/'main/generation').resolve()==(Path(config['previous_campaign'])/name/'main/generation').resolve(),
        'model_id':protocol['model_id'],'revision':protocol['revision'],
        'planned_attempts':len(requests),'tasks':len({r['problem_id'] for r in requests}),
        'completed_generation_shards':len(generation),
        'manifested_generation_attempts':sum(m['metrics']['attempts'] for m in manifests),
        'temperatures':protocol['temperatures'],'layers':protocol['layers'],
        'primary_layer':protocol['primary_layer'],'budgets':protocol['lean'],
        'stages':{stage:dict(Counter(t['state'] for t in queue['tasks'].values() if t.get('model')==name and t.get('stage')==stage)) for stage in ('smoke','verify','extract','measure','analyze')}}
    required += [model/'main/protocol.json',*generation]
metrics={'cutoff_utc':config['cutoff_utc'],'source':str(source),'source_sha256':digest(source),
    'git':read_json(source)['metrics'],'campaign':str(root),'accounting':accounting,
    'queue_counts':dict(Counter(t['state'] for t in queue['tasks'].values())),
    'tests':tests,'regression':reg,'models':models,'historical_p3':historical,'independent_p3':p3,
    'runtime_manifest_sha256':digest(config['runtime_manifest']),
    'runtime_binary_sha256':runtime['outputs'][str(Path(config['runtime_manifest']).parent/'repl')],
    'validation_job':config['validation'],'regression_job':config['regression']}
assert all(m['generation_is_original'] for m in models.values())
write_once(folder/'metrics.json',metrics)
def percent(value):return 'нет интервала' if value is None else f'{100*value:.2f}%'
def state(job):return accounting.get(job,{}).get('state','UNKNOWN')
lines=[
'# Выполнение первых трёх пунктов: проверка Lean, повторная серия, калибровка P3',
'',f"Срез очереди: {config['cutoff_utc']}. Отчёт рассчитан на Жоресе из журналов заданий, XML тестов и манифестов; сводные числа находятся в `metrics.json`.",
'', '## Что сделано и что ещё выполняется',
'', 'Исправления кода и отдельная сборка REPL подготовлены. Старые ответы, токены, протоколы и результаты сохранены. Повторная серия автоматически проходит проверку, извлечение активаций, измерения и полный анализ P1–P3 после своих зависимостей. Готовность очереди не означает завершение вычислений.',
'',f"Проверка окончательной версии: Slurm {config['validation']} — **{state(config['validation'])}**. Регрессия на сохранённых ответах: {config['regression']} — **{state(config['regression'])}**. Проверка одинаковой сборки вне Lean-стадий: {config['runtime_identity']} — **{state(config['runtime_identity'])}**.",
'', 'Независимый аудит P3 завершён. Ни действующий percentile-интервал, ни заранее выбранный basic bootstrap не обеспечили заявленное покрытие в исходном сценарии. Поправка не перенесена в основной анализ; количественные интервалы остаются описательными, научное решение — inconclusive.',
'', '## 1. Что было неверно в Lean и что изменено',
'', 'В исходной проверке целое доказательство могло пройти, а пошаговое исполнение останавливалось при 200 000 heartbeats, хотя протокол задаёт 400 000. Проверка исходников показала: `ContextInfo.runCoreM` создаёт `Core.Context` с лимитом по умолчанию и затем меняет Options; `withOptions` не пересчитывает активное поле `maxHeartbeats`. Простое добавление `set_option` к тактике было проверено и оказалось недостаточным. Этот вариант не является итоговым исправлением.',
'', 'Итоговая поправка находится в `ProofSnapshot.create`: активный `Core.Context.maxHeartbeats` берётся через `Core.getMaxHeartbeats ctx.options`. Она собрана на том же закреплённом Lean и той же базовой ревизии REPL. Живой тест читает и видимую опцию, и действующий лимит контекста. Это исправление исполнения заданного протокола; сами лимиты не повышались.',
'', 'Сегментатор теперь удерживает незакрытые скобки вместе с продолжением, включая закрывающую строку с тем же отступом. Символы внутри строк, символьных литералов, комментариев и quoted identifiers не открывают такие группы. Исходные координаты сегментов сохраняются для токенов и активаций.',
'', 'Heartbeat/recursion exhaustion классифицируется как `timeout_resource`. Прежние whole/replay verdicts не скрываются: известная ресурсная причина отмечается отдельно, а необъяснённое расхождение продолжает блокировать дальнейшие стадии. После первой ошибки все последующие метки остаются 0/unreached.',
'', 'Ошибка импорта прежде могла потеряться в frontend, оставляя пустое окружение и ответ с env ID. Сборка теперь возвращает ошибки импорта до обработки команд. Запуск дополнительно проверяет обычную тактику, Mathlib и Aesop. Число попыток запуска ограничено, все неудачи сохраняются; при повторном сбое разметка не начинается. Это защита и улучшенная диагностика; абсолютная надёжность на любых узлах не заявляется.',
'', 'Все стадии используют один закреплённый бинарник. Для Lean он копируется на диск узла; стадии, которые Lean не исполняют, сверяют тот же бинарник и манифест. Проверены отказ при изменении бинарника/манифеста и отсутствие тихого возврата к старому REPL.',
'', '### Проверки',
'', '| XML | Тесты | Failures | Errors | Skipped |','|---|---:|---:|---:|---:|']
for name,row in sorted(tests.items()):lines.append(f"| {name} | {row['tests']} | {row['failures']} | {row['errors']} | {row['skipped']} |")
if not tests:lines.append('| XML ещё не опубликован | — | — | — | — |')
lines += ['', 'XML рассматривается вместе с кодом завершения Slurm. Проход тестов при последующей неудаче проверки исходников не считается подтверждением окончательной версии. Предыдущие неудачные preflight-задания и их журналы сохранены в audit.', '', '| Сохранённый ответ | Итог новой регрессии |','|---|---|']
if reg:
    for rid,category in reg['categories'].items():lines.append(f'| {rid} | {category} |')
    lines += ['',f"Учтено случаев: {reg['cases']}; необъяснённых расхождений: {reg['unexplained_disagreements']}."]
else:lines.append('| Финальная регрессия ещё выполняется | см. Slurm |')
lines += ['', '## 2. Повторная серия и сохранение исходных данных', '',f"Новая серия: `{root}`.",f"Предыдущая серия: `{config['previous_campaign']}`.",f"Исходники новой серии: `{source.parent}`.", '', 'Пилот и main используют исходные generation-каталоги через ссылки. Протоколы скопированы без изменения байтов. Проверка, извлечение активаций, измерение и анализ имеют отдельные каталоги. Незавершённые исходные задания генерации являются внешними зависимостями; новая очередь не может отправить их повторно. Старый диспетчер остановлен, сами задания генерации сохранены.', '', '| Модель | Задачи в плане | Попытки в плане | Готовые generation shards | Попытки в готовых манифестах |','|---|---:|---:|---:|---:|']
for name,m in models.items():lines.append(f"| {name} | {m['tasks']} | {m['planned_attempts']} | {m['completed_generation_shards']} | {m['manifested_generation_attempts']} |")
lines += ['', 'Это учёт генерации; он не означает, что все ответы уже заново проверены или что доступны новые P1–P3.', '', '| Состояние новой очереди | Число заданий |','|---|---:|']
for key,value in sorted(metrics['queue_counts'].items()):lines.append(f'| {key} | {value} |')
lines += ['', 'Стадии по моделям, включая пилот и main вместе:', '', '| Модель | Стадия | Состояния |','|---|---|---|']
for name,m in models.items():
    for stage,counts in m['stages'].items():lines.append(f'| {name} | {stage} | {json.dumps(counts)} |')
lines += ['', 'Повторная разметка пилота на момент среза (последняя законченная запись в журнале; незавершённые метки не используются как итоговая статистика):', '', '| Модель | Slurm job | Состояние | Обработано ответов по журналу |', '|---|---|---|---:|']
for name,m in models.items():
    task=queue['tasks'][name+'/pilot-verify']
    lines.append(f"| {name} | {task.get('job_id','—')} | {task['state']} | {m['pilot_progress']['rows_in_log']} |")
lines += ['', 'Совпадение SHA256 старого и нового протокола проверено для пилота и main каждой модели. Адреса generation-каталогов также совпадают после раскрытия ссылок. Значения хешей, полные model IDs, revisions, бюджеты и слои приведены в metrics.json.']
lines += ['', 'Порядок: validation + сохранённые regression cases + runtime identity → smoke → повторная проверка пилота → pilot extraction/measurement/analysis → gate → проверка main по всем shards → gather verification → extraction shards → gather extraction → measurement → full analysis. Ошибка зависимости блокирует дочерние стадии. Контроллер работает в tmux и продолжает запускать готовые задания после завершения этого отчёта.', '', 'P4 и P5 в эти три пункта не входят. Их ожидающие задания не отменялись и не переставлялись. Времена ожидания GPU зависят от Slurm; точное время готовности всех моделей не обещается.', '', '## 3. P3: диагноз и независимая проверка поправки', '', 'Исходный coupled-overshoot контроль задаёт нижнюю границу failure values через фиксированный популяционный квантиль. Анализ оценивает порог заново на независимой calibration-выборке. Когда оценка ниже этой границы, positive excesses имеют положительную нижнюю границу и не являются zero-location GPD на выбранном пороге. Это объясняет часть смещения; оно не оправдывает недопокрытие полного метода.', '', '| Историческая группа | Наборы | Покрыто | Покрытие | Среднее смещение shape |','|---|---:|---:|---:|---:|']
for name,row in historical['groups'].items():lines.append(f"| {name} | {row['datasets']} | {row['covered']} | {percent(row['coverage'])} | {row['mean_point_bias']:.6f} |")
lines += ['', 'Новая проверка использовала новые, заранее фиксированные seeds: 200 наборов в каждом из трёх сценариев, 48 calibration tasks и 48 evaluation tasks, 500 task-bootstrap повторов. Одна задача переносится вместе со всеми её попытками. Проверяются исходная граница, более низкая граница и exponential null. Это маргинальная P3-симуляция: ненужные для неё P1/P2 переменные опущены. Основной метод, q и результаты моделей не подбирались по этим исходам.', '', '| Сценарий | Метод | Доступно CI | Покрытие среди доступных | MC 95% интервал покрытия | Положительных family-выводов |','|---|---|---:|---:|---|---:|']
for scenario,entry in p3['scenarios'].items():
    for method,row in entry['methods'].items():
        lo,hi=row['coverage']['monte_carlo_ci95']
        lines.append(f"| {scenario} | {method} | {row['availability']['successes']}/{row['availability']['datasets']} | {percent(row['coverage']['fraction'])} | [{percent(lo)}, {percent(hi)}] | {row['positive_family_rejection']['successes']}/{row['positive_family_rejection']['datasets']} |")
lines += ['', '`estimated` означает оцениваемый calibration threshold; `oracle` — известную границу симулятора. Oracle недоступен на реальных моделях и не является предлагаемым методом для них. Basic отражает bootstrap-квантили относительно точечной оценки. Правила достаточности сохранены, поэтому доступность CI различается; сравнивать только доли покрытия, игнорируя знаменатели, нельзя.', '', 'В исходном сценарии basic не устранил сильное недопокрытие. В других сценариях улучшение ограничено; эта проверка не устанавливает надёжность на данных трансформеров. Нулевые положительные family-выводы на exponential null означают лишь результат конечного контроля при данном family size, а не доказательство универсального контроля ошибки.', '', 'Практический вывод: по текущим интервалам нельзя объявлять P3 подтверждённым. Следующий статистический этап должен отдельно учитывать выбор порога, конечное смещение GPD и зависимость внутри задач, затем проверяться на новых заранее заданных seeds и распределениях. В этой итерации новая поправка не объявлена удачной и не внедрена ради желаемого результата.', '', '## Воспроизводимость и проверка другим GPT', '',f"Git: `{metrics['git']['git_commit']}`, ветка `{metrics['git']['git_branch']}`, dirty = `{metrics['git']['dirty']}`. Состояние задано полным snapshot, а не одним commit ID.",f"SHA256 source manifest: `{metrics['source_sha256']}`.",f"SHA256 runtime manifest: `{metrics['runtime_manifest_sha256']}`.",f"SHA256 REPL binary: `{metrics['runtime_binary_sha256']}`.", '', 'Базовая ревизия REPL и локальная поправка указаны раздельно в runtime manifest; версия Lean/Mathlib, исходники до поправки, исходники после неё, команды сборки, пакеты, узел и Slurm ID сохранены рядом. Sealed manifest содержит неизменяемую копию build script и исходного build record. Старый raw build record может ссылаться на рабочий файл; для повторной проверки используется sealed artifact.', '', 'Проверяющему следует: сопоставить whole/replay на всех пяти случаях; проверить действующий heartbeat limit, а не только Options; проверить исходные координаты скобочных сегментов; убедиться в сохранении всех generation IDs и protocol hashes; проверить запрет математической интерпретации resource failures; проверить CI availability и покрытие P3 по всем сценариям; отделить законченные вычисления от очереди зависимостей.', '', 'Не следует переносить результат синтетического контроля на научный вывод о реальных prover-моделях. Полный анализ новой основной выборки станет отдельным результатом после завершения цепочки. Для проверки чисел используйте `metrics.json` и `manifest.json`; технические пути исходных артефактов находятся в манифесте.', '']
report=folder/'REPORT.md'
with report.open('x',encoding='utf-8') as stream:
    stream.write('\n'.join(lines))
finish(folder,stage='revision-review-report',context={'source':digest(source)},
    inputs=[*required,*[p for p in inputs.iterdir() if p.is_file()]],outputs=[folder/'metrics.json',report],
    metrics={'cutoff_utc':config['cutoff_utc'],'queue_counts':metrics['queue_counts'],'validation_job':config['validation'],'regression_job':config['regression']})
print(report,flush=True)
