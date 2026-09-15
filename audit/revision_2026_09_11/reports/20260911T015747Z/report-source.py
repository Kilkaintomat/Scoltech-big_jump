"""Generate an audit from retained manifests, JSONL records and Slurm accounting."""
import datetime
import difflib
import json
import os
import tarfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.stages import rows

base = Path('/beegfs/home/denis.rakhmankin/onebigjump')
audit = base/'audit/revision_2026_09_11'
source = Path((audit/'snapshot-path.txt').read_text().strip())
original = base/'runs/lean_all_20260909'
recovery = base/'runs/lean_recovery_20260911_v3'
now = datetime.datetime.now(datetime.timezone.utc)
out = audit/'reports'/now.strftime('%Y%m%dT%H%M%SZ')
out.mkdir(parents=True)
inputs = [source/'source-manifest.json', audit/'before-metrics.json', audit/'code-before.tar.gz', recovery/'recovery.json', audit/'prepare-v3.py']
(out/'report-source.py').write_bytes(Path(__file__).read_bytes())
queue = read_json(recovery/'queue.json')
write_once(out/'queue.json', queue)
accounting_path = Path(os.environ['AUDIT_ACCOUNTING_PATH'])
accounting = accounting_path.read_text()
inputs.append(accounting_path)
(out/'slurm-accounting.tsv').write_text(accounting)
summary = {'as_of_utc':now.isoformat(), 'source':str(source), 'original_counts':read_json(original/'queue.json').get('counts'),
           'recovery_counts':queue.get('counts'), 'before':read_json(audit/'before-metrics.json'), 'models':{}, 'tests':{}}
parser_manifest = audit/'parser-8464431/manifest.json'
verify_manifest(parser_manifest)
inputs.append(parser_manifest)
summary['parser_regression'] = read_json(parser_manifest)['metrics']
(out/'review-notes.md').write_bytes((audit/'review-notes.md').read_bytes())
for path in sorted(audit.glob('*.xml')):
    suites = ET.parse(path).getroot()
    cases = list(suites.iter('testcase'))
    summary['tests'][path.name] = {'tests':len(cases), 'failures':len(list(suites.iter('failure'))), 'errors':len(list(suites.iter('error'))), 'skipped':len(list(suites.iter('skipped')))}
    inputs.append(path)
for name in ('deepseek','goedel','kimina'):
    root = recovery/name
    config = read_json(root/'pilot/protocol.json')
    model = {'model_id':config['model_id'], 'pilot_generation_reused':True, 'stages':{}, 'live_checks':[]}
    for check in sorted((root/'checks').glob('lean-smoke-*/manifest.json')):
        verify_manifest(check)
        model['live_checks'].append(read_json(check.parent/'summary.json'))
        inputs.append(check)
    for stage in ('verification','extraction','measurement','analysis'):
        manifest = root/'pilot'/stage/'manifest.json'
        if manifest.exists():
            verify_manifest(manifest)
            model['stages'][stage] = read_json(manifest)['metrics']
            inputs.append(manifest)
        else:
            model['stages'][stage] = {'status':'not_completed'}
    if 'attempts' in model['stages']['verification']:
        labels = rows(root/'pilot/verification/labels.jsonl')
        model['by_temperature'] = {str(t):dict(Counter(r['category'] for r in labels if r['temperature']==t)) for t in config['temperatures']}
        model['invalid_proof_reasons'] = dict(Counter(
            'native_decide_extra_axioms' if any('.native_decide.' in a for a in r.get('axioms',[]))
            else 'sorry_or_other_unapproved_axioms'
            for r in labels if r['category']=='sorry_invalid_proof'))
        model['whole_proof_ok'] = sum(r['whole_proof_ok'] is True for r in labels)
        model['whole_proof_ok_nontruncated'] = sum(r['whole_proof_ok'] is True and r['category']!='generation_truncation' for r in labels)
    if (root/'pilot/analysis/manifest.json').exists():
        metrics = read_json(root/'pilot/analysis/metrics.json')
        model['primary_cell'] = next(c for c in metrics['cells'] if c['temperature']==config['primary_temperature'] and c['layer']==config['primary_layer'] and c['statistic']==config['primary_statistic'])
        model['scientific_decision'] = metrics['scientific_decision']
    gate = root/'main/collection-gate/manifest.json'
    model['main_gate_passed'] = False
    if gate.exists():
        verify_manifest(gate)
        model['main_gate_passed'] = read_json(gate)['metrics']['passed']
        inputs.append(gate)
    model['main_jobs'] = {k:v for k,v in queue['tasks'].items() if k.startswith(name+'/main-') and v.get('job_id')}
    model['main_samples_written'] = sum(
        1 for path in (root/'main/generation').glob('*/samples.jsonl')
        for line in path.open(encoding='utf-8') if line.endswith('\n') and line.strip())
    summary['models'][name] = model
final_job = (audit/'validation-job.txt').read_text().strip()
for filename in ('full-'+final_job+'.xml','full-'+final_job+'.log'):
    path=audit/filename
    if path.exists():
        (out/filename).write_bytes(path.read_bytes())
        inputs.append(path)
summary['final_validation_job'] = final_job
write_once(out/'metrics.json', summary)
# Diff against the exact state saved before this audit, including previously untracked code.
with tarfile.open(audit/'code-before.tar.gz') as archive:
    old_files = {m.name:archive.extractfile(m).read() for m in archive.getmembers() if m.isfile() and '__pycache__' not in m.name and not m.name.endswith('.pyc') and not Path(m.name).name.startswith('._') and m.name.startswith(('src/','scripts/','tests/','docs/e1/'))}
new_files = {str(p.relative_to(source)):p.read_bytes() for folder in ('src','scripts','tests','docs/e1') for p in (source/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
patch=[]
changed=[]
for name in sorted(set(old_files)|set(new_files)):
    old_bytes,new_bytes=old_files.get(name,b''),new_files.get(name,b'')
    if old_bytes==new_bytes: continue
    changed.append(name)
    try:
        patch.extend(difflib.unified_diff(old_bytes.decode('utf-8').splitlines(True),new_bytes.decode('utf-8').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
    except UnicodeDecodeError:
        patch.append('Binary files differ: '+name+'\n')
(out/'revision.patch').write_text(''.join(patch),encoding='utf-8')
lines=['# Ревизия Жореса — 11 сентября 2026','', 'Срез UTC: '+summary['as_of_utc']+'.','',
'При подключении активных заданий не было. Предыдущая серия остановилась 9 сентября до основной выборки.',
'Исправленная обработка выполняется в отдельной серии; исходная генерация и все прежние артефакты сохранены.','',
'Промежуточный повтор lean_recovery_20260911 содержал регрессию выбора финального блока DeepSeek из-за Unicode EOS. Его зависимые стадии остановлены; финальная серия — lean_recovery_20260911_v3; она сохраняет исправленные разметку и активации v2, пересчитывая статистику с контролем сходимости GPD. Парсер дополнительно проверен на всех исходных ответах; ранее корректно выделенные тела доказательств DeepSeek/Goedel сохранены.','',
'| Модель | Исходных попыток | Старых verified | Новых verified | Новых расхождений | Извлечено трасс | Допуск main |',
'|---|---:|---:|---:|---:|---:|---|']
for name,m in summary['models'].items():
    old=summary['before'][name]
    v=m['stages']['verification']; e=m['stages']['extraction']
    lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(name,old['attempts'],old['categories'].get('verified',0),v.get('categories',{}).get('verified','ожидание'),v.get('unexplained_disagreements','ожидание'),e.get('extracted','ожидание'),'пройден' if m['main_gate_passed'] else 'не пройден'))
lines += ['', 'Verified учитывает завершённые доказательства без обрыва по лимиту токенов. Доли пилота не являются оценками всей основной выборки.', '',
'## Текущая основная выборка','',
'План: по 6672 попытки на каждую из трёх моделей, всего 20016; генерация, разметка, активации и анализ идут через Slurm.',
'Очередь: `'+json.dumps(summary['recovery_counts'],sort_keys=True)+'`.','']
for name,m in summary['models'].items():
    jobs = ', '.join(str(t['job_id'])+' '+t['state'] for t in m['main_jobs'].values() if t['state'] in {'RUNNING','PENDING','COMPLETING'})
    lines += ['- '+name+': '+str(m['main_samples_written'])+' записанных основных ответов; задания: '+(jobs or 'нет активных на этом срезе')+'.']
lines += ['', '## Причины остановки и исправления','',
'- Многострочные `<;>`/`;` разделялись на неверные шаги. Операторы и операнды сохраняются в одном сегменте с исходными координатами.',
'- Блоки `tactics` в рассуждениях сбивали поиск финального Lean-кода Kimina. Исправлено сопоставление Markdown-ограждений и выделение финального ответа.',
'- Gate проверял не то имя категории инфраструктурной ошибки; исправлены категория, контроль кода extraction и повторное использование shard-манифестов с расхождениями.',
'- Пустой анализ сообщал об учтённых попытках без явного числа извлечённых трасс. Теперь эти числа разделены, отсутствие данных указано явно.',
'- Интервалы P3 учитывают число задач с реальными превышениями порога и существующие требования к калибровочным/оценочным превышениям.',
'- Подгонка GPD ошибочно объявляла граничные решения с gamma ≤ −1 успешными. Сырые значения сохранены в диагностике, но такие решения исключены из оценок, bootstrap-интервалов и сравнений хвостовых моделей. Допустимые отрицательные оценки не обрезаются.',
'- Проверки campaign больше не исправляют код автоматически. Добавлены отдельный восстановитель и диспетчер в scripts/campaign.','',
'## Проверки','', '| JUnit | Тесты | Failures | Errors | Skipped |','|---|---:|---:|---:|---:|']
for name,t in summary['tests'].items():
    lines.append('| {} | {} | {} | {} | {} |'.format(name,t['tests'],t['failures'],t['errors'],t['skipped']))
lines+=['','Прогоны частично перекрываются; количества не суммируются. Полный финальный прогон относится к неизменяемому snapshot. Ранний full-8464415 запускал тесты из изолированного дерева без нужных fixtures/.git/Lean; он дал один сбой и 52 пропуска. Обёртка исправлена; последующие полные прогоны проверяют совпадение файлов с snapshot и выполняют живые Lean/ML-тесты без пропусков.','',
'## Результаты и ограничения','']
for name,m in summary['models'].items():
    lines+=['### '+name,'', 'Категории по температуре: `'+json.dumps(m.get('by_temperature',{}),ensure_ascii=False,sort_keys=True)+'`.','']
    if m.get('invalid_proof_reasons'):
        lines += ['Причины недопуска доказательств: `'+json.dumps(m['invalid_proof_reasons'],ensure_ascii=False,sort_keys=True)+'`. Native_decide с новыми аксиомами исключается по закреплённой политике; это не означает буквальный sorry в исходнике.','']
    cell=m.get('primary_cell')
    if cell and cell['available']:
        p2=cell['P2']
        lines+=['Первичная ячейка: T={}, слой {} (индекс с нуля), {}.'.format(cell['temperature'],cell['layer'],cell['statistic']),
                'P2: задач {}, refuted трасс {}; jump top1 {}, surprisal top1 {}, шанс {}.'.format(p2['n_tasks'],p2['n_traces'],p2.get('jump',{}).get('top1'),p2.get('surprisal',{}).get('top1'),p2.get('chance')),'']
        lines += ['P1, диагностические оценки (без подтверждающих интервалов):','',
                  '| Подвыборка | Шагов | Задач | Hill | Moment | GPD | Статус |',
                  '|---|---:|---:|---:|---:|---:|---|']
        for subset,p1 in cell['P1'].items():
            if subset not in {'verified','refuted_all','at_post'}: continue
            lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
                subset,p1['n_steps'],p1['n_tasks'],p1.get('hill'),p1.get('moment'),
                p1.get('gpd'),p1.get('fit_status')))
        p3 = next(item for item in cell['P3'] if item['q']==0.01)
        fit = p3.get('gpd') or {}
        lines += ['', 'P3, q=0.01: положительных превышений {} на {} задачах; '
                  'калибровочных превышений {} на {} задачах. GPD raw gamma={}, '
                  'пригодная оценка={}, converged={}, сообщение={}.'.format(
                      p3.get('positive_excesses'),p3.get('positive_excess_tasks'),
                      p3.get('calibration_exceedances'),p3.get('calibration_tail_tasks'),
                      fit.get('gamma'),fit.get('shape_estimate'),fit.get('converged'),
                      fit.get('message','')), 'Доля превышений порога на допустимых шагах: {}; покрытие ошибочных шагов: {}.'.format(p3.get('accepted_step_exceedance'),p3.get('failure_coverage')),'']
    else:
        lines+=['Первичная ячейка ещё недоступна.','']
lines+=['Малые калибровочные наборы делают whitening и пороги нестабильными; высокая доля превышений на допустимых шагах не означает успешную локализацию.','', 'Научные выводы P1–P3: **inconclusive**. Пилот содержит слишком мало независимых задач. Основная выборка, ручная проверка, статистическая калибровка и недостающие sensitivity/null остаются отдельными требованиями. Полный протокол статьи не завершён.','',
'## Воспроизводимость','', '- Серия: `'+str(recovery)+'`.','- Snapshot: `'+str(source)+'`.','- Очередь: `'+str(recovery/'queue.json')+'`.','- tmux: `onebigjump-recovery`.', '- При обновлении статистики четыре задания v2 (8464445, 8464446, 8464453, 8464454) отменены до появления записей samples.jsonl; журналы и пустые startup-артефакты сохранены. Все исходные 240 пилотных ответов переиспользованы без пересэмплирования.','- Изменения относительно начала этой ревизии: [revision.patch](revision.patch).','- Числа и детали: [metrics.json](metrics.json); [Slurm](slurm-accounting.tsv).','- Ревизия реальных примеров: [review-notes.md](review-notes.md).','',
'Исторические paper_outputs не изменены. Чужие незакоммиченные изменения сохранены в code-before.tar.gz и before.patch.','',
'Изменённые файлы:'] + ['- `'+name+'`' for name in changed]
(out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
finish(out,stage='revision-audit-report',context={'as_of_utc':summary['as_of_utc'],'source':digest(source/'source-manifest.json')},inputs=inputs,outputs=list(out.glob('*')),metrics={'models':len(summary['models']),'scientific_decision':'inconclusive'})
(audit/'latest-report.txt').write_text(str(out)+'\n')
print(out,flush=True)
