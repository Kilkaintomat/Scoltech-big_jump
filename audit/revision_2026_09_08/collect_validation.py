"""Assemble validation evidence on Zhores from completed Slurm test logs (stdlib only)."""
import datetime
import hashlib
import json
import platform
import re
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def digest(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def git(args):
    return subprocess.check_output(['git'] + args, cwd=str(ROOT)).decode('utf-8').strip()


def junit(stem):
    cases = ET.parse(str(OUT / (stem + '.xml'))).getroot().findall('.//testcase')
    failed = sum(c.find('failure') is not None for c in cases)
    errors = sum(c.find('error') is not None for c in cases)
    skipped = sum(c.find('skipped') is not None for c in cases)
    deselected = re.findall(r'(\d+) deselected', (OUT / (stem + '.log')).read_text(encoding='utf-8'))
    return dict(cases=len(cases), passed=len(cases)-failed-errors-skipped,
                failures=failed, errors=errors, skipped=skipped,
                deselected=int(deselected[-1]) if deselected else None,
                test_seconds=sum(float(c.get('time', 0)) for c in cases))


def main():
    checks = {'server-tests': junit('server-tests'), 'server-make-test': junit('server-make-test'), 'server-make-test-all': junit('server-make-test-all')}
    for name, check in checks.items():
        assert check['cases'] and not check['failures'] and not check['errors'], (name, check)
    total = checks['server-make-test-all']['cases']
    for check in checks.values():
        if check['deselected'] is None:
            check['deselected'] = total - check['cases']
    accounting = (OUT / 'cluster-accounting.txt').read_text(encoding='utf-8')
    assert '8462208|COMPLETED|0:0|' in accounting, accounting
    assert '8462258|COMPLETED|0:0|' in accounting, accounting
    tracked = git(['ls-files']).splitlines()
    source_names = sorted(set(p for p in tracked if p.startswith(('src/', 'tests/', 'scripts/', 'configs/')))
                          | {'AGENTS.md', 'Makefile', 'pyproject.toml', 'uv.lock', 'analysis_plan.yaml',
                             'scripts/revision_diagnostics.py', 'tests/unit/test_revision_regressions.py'})
    archive = OUT / 'reviewed-source.tar.gz'
    with tarfile.open(str(archive), 'w:gz') as tf:
        for name in source_names:
            tf.add(str(ROOT / name), arcname=name, recursive=False)
    patch = subprocess.check_output(['git', 'diff', '--binary'], cwd=str(ROOT))
    for name in ('scripts/revision_diagnostics.py', 'tests/unit/test_revision_regressions.py'):
        proc = subprocess.Popen(['git', 'diff', '--no-index', '--', '/dev/null', name], cwd=str(ROOT), stdout=subprocess.PIPE)
        data, _ = proc.communicate()
        assert proc.returncode in (0, 1)
        patch += data
    (OUT / 'changes.patch').write_bytes(patch)
    server_manifest = json.loads((OUT / 'manifest-revision-server-report.json').read_text(encoding='utf-8'))
    assert server_manifest['status'] == 'ok'
    diag_manifest = json.loads((OUT / 'server-diagnostics/manifest-revision-diagnostics.json').read_text(encoding='utf-8'))
    assert diag_manifest['status'] == 'ok'
    git_state = dict(commit=git(['rev-parse','HEAD']), dirty=bool(git(['status','--porcelain'])), status=git(['status','--porcelain']))
    result = dict(
        baseline_commit='a3988f76ca27ff5ecc476a192b9d61797e861b65',
        draft_sha256='c8477f7cad4e48a407b0e2751d0a348af6b5f6515ac8e4368ae86bcdba3d1d4b',
        authoritative_repository=str(ROOT), final_job=8462208, precommit_job=8462258, checks=checks,
        earlier_local_make_test=junit('test'), local_final_repeat='interrupted at user request; not counted as passed',
        source_files={name:digest(ROOT/name) for name in source_names}, source_archive_digest=digest(archive),
        baseline_archive_digest=digest(OUT/'zhores-baseline.tar.gz'), cluster_accounting=accounting,
        test_environment=server_manifest['environment'], report_display_checks=server_manifest['metrics'],
        archived_results_preservation=json.loads((OUT/'archive-preservation.json').read_text(encoding='utf-8')),
        command='sbatch audit/revision_2026_09_08/final-checks.sbatch',
        limitations=['Remote Lean explicitly deselected because Mathlib/REPL is not ready.',
                     'CPU container validation is not a 7B prover/GPU/vLLM run.',
                     'Audit runs preceded the commit; no clean-tree reproducibility claim.',
                     'No further local work after the user requested server-only execution.'])
    write_json(OUT/'validation.json', result)
    lines = ['# Проверка ревизии на Жоресе', '',
             'Сформировано collect_validation.py на сервере из JUnit XML, Slurm accounting и манифестов.', '',
             '| Запуск | Passed | Failures | Errors | Skipped | Deselected |',
             '|---|---:|---:|---:|---:|---:|']
    for name, check in checks.items():
        lines.append('| {} | {} | {} | {} | {} | {} |'.format(name,check['passed'],check['failures'],check['errors'],check['skipped'],check['deselected']))
    lines += ['', 'Итоговый job: `8462208`, команда: `sbatch audit/revision_2026_09_08/final-checks.sbatch`.',
              'Повторная диагностика Kesten и обработка архива P4 выполнены на сервере в том же job.',
              'Проверены пять случаев отображения provenance и включение null-прогонов в отчёт.', '',
              'На Жоресе Lean-тесты исключены явно: Mathlib/REPL пока не готов. Это не успешные тесты Lean.',
              'Ранний локальный make test завершился успешно; последующий локальный повтор test-all остановлен по указанию пользователя и не засчитан.',
              'Ранее локально проходили live Lean/GPT-2 проверки. Они не подтверждают готовность удалённого Lean.',
              'Ruff/mypy и обе цели make выполнены на Жоресе, precommit job 8462258. Pytest использовал четыре процесса (уже установленный pytest-xdist). Makefile выполняется на host, uv-run вызовы передаются установленным модулям контейнера через audit/bin/uv; синхронизация зависимостей не выполняется. Shell-синтаксис и git diff --check проверены на сервере.', '',
              '```text', accounting.strip(), '```', '',
              '## Артефакты', '',
              '- [Итоговый лог](server-tests.log), [JUnit XML](server-tests.xml)',
              '- [Команда Slurm](final-checks.sbatch), [precommit](precommit.sbatch)',
              '- [make test](server-make-test.log), [make test-all](server-make-test-all.log)',
              '- [Серверные измерения](server-diagnostics/MEASUREMENTS.md)',
              '- [Метаданные проверки](validation.json), [manifest](manifest-revision-validation.json)',
              '- [Проверенные исходники](reviewed-source.tar.gz), [patch](changes.patch)',
              '- [Прерванный локальный повтор](local-interrupted-test-all.log)',
              '- [Первый Slurm-прогон с найденными сбоями](cluster-first.log)', '',
              'Диагностические прогоны выполнены до коммита, на изменённом дереве. Новая генерация prover и полная экспериментальная кампания не проводились.']
    (OUT/'VALIDATION.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    report = OUT/'REPORT.md'
    body = report.read_text(encoding='utf-8').split('<!-- GENERATED VALIDATION -->')[0].rstrip()
    table = ['| Проверка | Passed | Failures | Skipped | Deselected |', '|---|---:|---:|---:|---:|']
    for name, c in checks.items():
        table.append('| {} | {} | {} | {} | {} |'.format(name,c['passed'],c['failures'],c['skipped'],c['deselected']))
    report.write_text(body+'\n\n<!-- GENERATED VALIDATION -->\n## Итог серверной проверки\n\n'+'\n'.join(table)+'\n\nSlurm jobs: 8462208 (тесты, диагностика, reporter), 8462258 (make test и make test-all). Ruff/mypy прошли на сервере. Lean на сервере не проверен: toolchain не готов. Последний локальный повтор остановлен по указанию пользователя.\n',encoding='utf-8')
    output_names = ['validation.json','VALIDATION.md','reviewed-source.tar.gz','changes.patch','REPORT.md',
                    'server-tests.xml','server-tests.log','cluster-accounting.txt','collect_validation.py',
                    'final-checks.sbatch','precommit.sbatch','bin/uv','check_report.py','archive-preservation.json',
                    'server-make-test.xml','server-make-test.log','server-make-test-all.xml','server-make-test-all.log']
    manifest = dict(name='revision-validation',kind='audit',status='ok',reproducible=False,
                    finished_at=datetime.datetime.utcnow().isoformat()+'Z',
                    config={'final_job':8462208,'assembly':'stdlib artifact assembly on Zhores; numerical tests executed via Slurm'},
                    environment={'git':git_state,'packages':{'python':sys.version},
                                 'hardware':{'node':platform.node(),'platform':platform.platform()},
                                 'test_execution':server_manifest['environment']},
                    outputs=[{'path':str(OUT/name),'digest':digest(OUT/name),'bytes':(OUT/name).stat().st_size} for name in output_names])
    write_json(OUT/'manifest-revision-validation.json',manifest)
    print(json.dumps(checks))


if __name__ == '__main__':
    main()
