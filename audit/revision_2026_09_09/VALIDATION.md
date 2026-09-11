# Проверки ревизии 9 сентября 2026

Отчёт создан программой из JUnit XML и результатов живых Lean-проверок.

Slurm job полного прогона: `8462797`.

| Проверка | Passed | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| make-test | 498 | 0 | 0 | 0 |
| make-test-all | 585 | 0 | 0 | 0 |

Живые E1 fixtures: 17, failed: 0.
Проверено исходных statements: 457.
Полные ответы Lean: `/beegfs/home/denis.rakhmankin/onebigjump/runs/e1_20260908T171727Z/checks/lean-smoke-smoke-20260909T142259Z`.

DeepSeek-Prover-7B: GPU engine preflight пройден; Slurm job 8462759.
Slurm accounting: [slurm-accounting.tsv](slurm-accounting.tsv).

Неуспешные прогоны сохранены отдельно. Ошибки чтения BeeGFS не считаются проверками kernel labels.

Запуски эксперимента записываются в `runs/e1_20260908T171727Z/pilot/submission-*.json`.
Это development pilot; подтверждающий main protocol ещё не завершён.
