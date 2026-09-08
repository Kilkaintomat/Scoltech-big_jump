# Проверка ревизии на Жоресе

Сформировано collect_validation.py на сервере из JUnit XML, Slurm accounting и манифестов.

| Запуск | Passed | Failures | Errors | Skipped | Deselected |
|---|---:|---:|---:|---:|---:|
| server-tests | 536 | 0 | 0 | 0 | 18 |
| server-make-test | 469 | 0 | 0 | 0 | 85 |
| server-make-test-all | 536 | 0 | 0 | 18 | 0 |

Итоговый job: `8462208`, команда: `sbatch audit/revision_2026_09_08/final-checks.sbatch`.
Повторная диагностика Kesten и обработка архива P4 выполнены на сервере в том же job.
Проверены пять случаев отображения provenance и включение null-прогонов в отчёт.

На Жоресе Lean-тесты исключены явно: Mathlib/REPL пока не готов. Это не успешные тесты Lean.
Ранний локальный make test завершился успешно; последующий локальный повтор test-all остановлен по указанию пользователя и не засчитан.
Ранее локально проходили live Lean/GPT-2 проверки. Они не подтверждают готовность удалённого Lean.
Ruff/mypy и обе цели make выполнены на Жоресе, precommit job 8462258. Pytest использовал четыре процесса (уже установленный pytest-xdist). Makefile выполняется на host, uv-run вызовы передаются установленным модулям контейнера через audit/bin/uv; синхронизация зависимостей не выполняется. Shell-синтаксис и git diff --check проверены на сервере.

```text
JobID|State|ExitCode|Elapsed|NodeList
8462197|FAILED|1:0|00:07:09|cn70
8462197.batch|FAILED|1:0|00:07:09|cn70
8462197.extern|COMPLETED|0:0|00:07:09|cn70
8462204|COMPLETED|0:0|00:07:02|cn70
8462204.batch|COMPLETED|0:0|00:07:02|cn70
8462204.extern|COMPLETED|0:0|00:07:02|cn70
8462208|COMPLETED|0:0|00:07:20|cn70
8462208.batch|COMPLETED|0:0|00:07:20|cn70
8462208.extern|COMPLETED|0:0|00:07:20|cn70
8462212|FAILED|127:0|00:00:00|cn70
8462212.batch|FAILED|127:0|00:00:00|cn70
8462212.extern|COMPLETED|0:0|00:00:00|cn70
8462256|FAILED|2:0|00:00:00|cn70
8462256.batch|FAILED|2:0|00:00:00|cn70
8462256.extern|COMPLETED|0:0|00:00:00|cn70
8462257|FAILED|2:0|00:01:12|cn70
8462257.batch|FAILED|2:0|00:01:12|cn70
8462257.extern|COMPLETED|0:0|00:01:12|cn70
8462258|COMPLETED|0:0|00:06:21|cn70
8462258.batch|COMPLETED|0:0|00:06:21|cn70
8462258.extern|COMPLETED|0:0|00:06:21|cn70
```

## Артефакты

- [Итоговый лог](server-tests.log), [JUnit XML](server-tests.xml)
- [Команда Slurm](final-checks.sbatch), [precommit](precommit.sbatch)
- [make test](server-make-test.log), [make test-all](server-make-test-all.log)
- [Серверные измерения](server-diagnostics/MEASUREMENTS.md)
- [Метаданные проверки](validation.json), [manifest](manifest-revision-validation.json)
- [Проверенные исходники](reviewed-source.tar.gz), [patch](changes.patch)
- [Прерванный локальный повтор](local-interrupted-test-all.log)
- [Первый Slurm-прогон с найденными сбоями](cluster-first.log)

Диагностические прогоны выполнены до коммита, на изменённом дереве. Новая генерация prover и полная экспериментальная кампания не проводились.
