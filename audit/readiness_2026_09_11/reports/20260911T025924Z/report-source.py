"""Read retained metrics and job ledgers; produce a dated audit, never paper numbers."""
import datetime
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from onebigjump.e1.artifacts import digest, finish, read_json, write_once
from onebigjump.e1.stages import rows

base = Path('/beegfs/home/denis.rakhmankin/onebigjump')
audit = base / 'audit/readiness_2026_09_11'
root = base / 'runs/expansion_20260911'
protected = base / 'runs/lean_recovery_20260911_v3'
source = Path((audit / 'source-path.txt').read_text().strip())
now = datetime.datetime.now(datetime.timezone.utc)
out = audit / 'reports' / now.strftime('%Y%m%dT%H%M%SZ')
out.mkdir(parents=True)
script = out / 'report-source.py'
script.write_bytes(Path(__file__).read_bytes())
queue = read_json(root / 'queue.json')
original = read_json(protected / 'queue.json')
old = read_json(base / 'audit/revision_2026_09_11/reports/20260911T015747Z/metrics.json')
inputs = [source / 'source-manifest.json', script,
          base / 'audit/revision_2026_09_11/reports/20260911T015747Z/metrics.json']
qpath = write_once(out / 'queue.json', queue)
pqpath = write_once(out / 'protected-queue.json', original)
accounting_path = Path(os.environ['READINESS_ACCOUNTING'])
accounting = accounting_path.read_text()
inputs.append(accounting_path)
(out / 'slurm-accounting.tsv').write_text(accounting)
summary = {'as_of_utc': now.isoformat(), 'source': str(source), 'source_sha256': digest(source/'source-manifest.json'),
           'expansion_counts': queue.get('counts'), 'protected_counts': original.get('counts'),
           'expansion_tasks': len(queue['tasks']), 'models': {}, 'sidecars': {}, 'tests': {}}
for p in sorted(audit.glob('*-8464485.xml')):
    tree = ET.parse(p).getroot()
    summary['tests'][p.name] = {name: len(list(tree.iter(tag))) for name,tag in [('tests','testcase'),('failures','failure'),('errors','error'),('skipped','skipped')]}
    (out/p.name).write_bytes(p.read_bytes())
for name in ('deepseek','goedel','kimina'):
    records = list((protected/name/'main/generation').glob('*/samples.jsonl'))
    summary['models'][name] = {'main_attempts_saved': sum(sum(line.endswith(b'\n') for line in p.open('rb')) for p in records),
                             'pilot_verified': old['models'][name]['stages']['verification']['categories'].get('verified',0),
                             'pilot_attempts':old['models'][name]['stages']['verification']['attempts'],
                             'pilot_extracted':old['models'][name]['stages']['extraction']['extracted'],
                             'scientific_decision':'inconclusive'}
    for stage in ('positional','whitening'):
        folder = root/'e1-controls/pilot'/name/stage
        if (folder/'manifest.json').exists():
            inputs.append(folder/'manifest.json')
            summary['sidecars'][name+'/'+stage] = read_json(folder/'metrics.json') if (folder/'metrics.json').exists() else rows(folder/'results.jsonl')
metrics = write_once(out/'metrics.json', summary)
lines = ['# Жорес: готовность и дополнительные запуски, 11 сентября 2026', '', 'Срез UTC: '+summary['as_of_utc']+'.', '',
         'Ранее запущенная серия сохранена: ни её задания, ни tmux-диспетчер не остановлены. Исходный код основной серии остаётся в прежнем неизменяемом snapshot.', '',
         '## Что уже получили', '', '| Модель | Verified в пилоте | Извлечено трасс | Сохранено ответов main |', '|---|---:|---:|---:|']
for name,m in summary['models'].items():
    lines.append('| {} | {}/{} | {} | {} |'.format(name,m['pilot_verified'],m['pilot_attempts'],m['pilot_extracted'],m['main_attempts_saved']))
lines += ['', 'Main: план 20 016 ответов, результаты ещё собираются. Сохранённый ответ ещё не означает проверенное доказательство.',
          'Пилот не подтверждает P1–P3: мало независимых задач, нет устойчивого преимущества jump над surprisal; в первичной whitening-ячейке порог превышался на всех допустимых шагах. Ошибочно успешные граничные GPD-подгонки исправлены и исключены из пригодных оценок.', '',
          '## Новая серия', '', 'Очередь расширения: `'+json.dumps(summary['expansion_counts'],sort_keys=True)+'`; всего узлов '+str(summary['expansion_tasks'])+' (включая зависимости на проверки и загрузку модели). WAITING означает будущий этап, а не уже запущенный Slurm job.', '',
          '- P1–P3: 800 Monte Carlo наборов (4 сценария × 200), по 500 task-bootstrap повторов и 200 внутренних повторов выбора k; позиционные контроли; 3 уровня shrinkage, разделение калибровки transform/threshold и 50 refit на модель для main.',
          '- P4: 5 пар обычных/перемешанных меток, по 40 000 обновлений; веса/optimizer/RNG сохраняются каждые 100 шагов. Фиксированные финальные Fourier-частоты, одинаковое окно сравнения в паре и отдельная полная статистика на фиксированной сетке checkpoints.',
          '- P5 и синтетические P1–P3: Qwen2.5-7B-Instruct на новом контролируемом modus-ponens наборе. Пилот 80 попыток; 5 600 основных попыток автоматически допускаются только после технического gate пилота. Это отдельная задача, не полное воспроизведение PrOntoQA.', '',
          '| Этап | Job ID | Состояние |', '|---|---|---|']
for key,t in queue['tasks'].items():
    if t.get('job_id'):
        lines.append('| {} | {} | {} |'.format(key,t['job_id'],t['state']))
lines += ['', 'Новые измерения whitening (доля превышений на допустимых оценочных шагах):', '', '| Модель | Transform и порог на одних данных | Раздельная калибровка |', '|---|---:|---:|']
for name in ('deepseek','goedel','kimina'):
    variants = {r['trace_id']:r for r in summary['sidecars'].get(name+'/whitening',[]) if isinstance(r,dict) and 'trace_id' in r}
    if 'all-calibration-0.1' in variants and 'disjoint-transform-and-threshold' in variants:
        a=variants['all-calibration-0.1']['P3']['accepted_step_exceedance']
        b=variants['disjoint-transform-and-threshold']['P3']['accepted_step_exceedance']
        lines.append('| {} | {} | {} |'.format(name,a,b))
lines += ['', 'Изменение согласуется с сильным эффектом самокалибровки. Оно не подтверждает P3: контрольная калибровка мала, фактическая частота превышений не становится гарантированно равной номинальной. Во всех пилотных позиционных стратах только по одной задаче, поэтому корректный task-permutation p-value не вычисляется.']
lines += ['', 'Статус контролей пилота: '+', '.join(sorted(summary['sidecars']))+'.', '', '## Проверки и устойчивость', '']
for name,record in summary['tests'].items():
    lines.append('- {}: {} tests, {} failures, {} errors, {} skipped.'.format(name,record['tests'],record['failures'],record['errors'],record['skipped']))
lines += ['','Lint/format/mypy, живой Lean, ML-тесты, исходные token IDs, точное возобновление P4 и символический верификатор входят в проверки. Научные расчёты и тесты выполняются на Slurm. Диспетчеры `onebigjump-recovery` и `onebigjump-expansion` работают в отдельных tmux; разрыв SSH не останавливает задания. Новые GPU-задачи имеют пониженный приоритет.', '',
          '## Что усилит статью', '',
          'Нужно повышать достоверность измерений и независимость свидетельств. Повышение доли правильных доказательств само по себе не является целью: для P1/P2 нужны и правильные, и ошибочные трассы. Не ремонтировать и не отбирать main по успеху, не ослаблять политику аксиом. Улучшение prompting/repair — только отдельная заранее описанная ветка с одинаковым бюджетом и полной отчётностью.', '',
          'Следующие решения: проверить main и калибровку интервалов; сравнить позиционные и whitening-контроли; провести независимую ручную ревизию меток; проверить P4 на парных seeds; для P5 добавить task-bootstrap и проверку предсказания на отложенных длинах/задачах. Новые независимые задачи полезнее ещё одной серии попыток на тех же miniF2F.', '',
          'Two-hop, recurrent depth, Tracr/ngram, supervised probes и остальные модели не выданы за готовые эксперименты: их проверенных реализаций пока нет. В текущем контракте пять предсказаний P1–P5. Эти расширения — отдельный следующий этап либо соответствующие обещания нужно убрать из статьи. Пять пар P4 и пилот P5 сами по себе не дают подтверждающего вывода.', '',
          'Протокол и ограничения: `docs/e1/READINESS_20260911.md`. Основной репозиторий: https://github.com/Kilkaintomat/Scoltech-big_jump . Числа этого отчёта созданы из metrics/manifest и очередей, paper_outputs не менялись.']
report = out/'REPORT.md'
report.write_text('\n'.join(lines)+'\n',encoding='utf8')
outputs = [p for p in out.iterdir() if p.is_file()]
finish(out, stage='readiness-audit-report', context={'as_of_utc':now.isoformat()}, inputs=inputs,
       outputs=outputs, metrics={'source':str(source),'report':str(report)})
(audit/'latest-report.txt').write_text(str(out)+'\n')
print(str(out),flush=True)
