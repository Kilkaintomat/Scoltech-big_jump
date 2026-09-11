# Запуск первого реального пилота

Состояние зафиксировано: 2026-09-09T17:35:34.108272+03:00.

DeepSeek-Prover-V2-7B; 20 заранее выбранных задач; 80 попыток. Генерация без обратной связи от Lean.

| Job | Стадия | Состояние | Лимит времени |
|---|---|---|---|
| 8462802 | e1-generation | PENDING | 02:00:00 |
| 8462803 | e1-verification | PENDING | 12:00:00 |
| 8462804 | e1-extraction | PENDING | 02:00:00 |
| 8462805 | e1-measurement | PENDING | 12:00:00 |
| 8462806 | e1-analysis | PENDING | 12:00:00 |

Зависимости: generation → verification → extraction → measurement → analysis.
GPU-стадии ограничены двумя часами каждая; научные параметры не менялись.
Snapshot: `/beegfs/home/denis.rakhmankin/onebigjump/runs/e1_20260908T171727Z/snapshots/pilot-20260909T143152Z`.
Source commit: `5302b9f8435c0e653c4a0c5eeacd50fb25e3df07`; dirty=True.
Используется неизменяемая копия исходников с digest каждого файла; commit после ревизии не создавался.

Логи: `/beegfs/home/denis.rakhmankin/onebigjump/runs/e1_20260908T171727Z/logs/`.
Готовый отчёт эксперимента появится в `/beegfs/home/denis.rakhmankin/onebigjump/runs/e1_20260908T171727Z/pilot/analysis/REPORT.md`.
Проверка GPU engine уже пройдена (8462759); текущая очередь не означает ошибки установки.

Результаты не помещаются в paper_outputs и не объявляются подтверждением гипотез.
