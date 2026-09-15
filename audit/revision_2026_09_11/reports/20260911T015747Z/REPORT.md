# Ревизия Жореса — 11 сентября 2026

Срез UTC: 2026-09-11T01:57:47.040219+00:00.

При подключении активных заданий не было. Предыдущая серия остановилась 9 сентября до основной выборки.
Исправленная обработка выполняется в отдельной серии; исходная генерация и все прежние артефакты сохранены.

Промежуточный повтор lean_recovery_20260911 содержал регрессию выбора финального блока DeepSeek из-за Unicode EOS. Его зависимые стадии остановлены; финальная серия — lean_recovery_20260911_v3; она сохраняет исправленные разметку и активации v2, пересчитывая статистику с контролем сходимости GPD. Парсер дополнительно проверен на всех исходных ответах; ранее корректно выделенные тела доказательств DeepSeek/Goedel сохранены.

| Модель | Исходных попыток | Старых verified | Новых verified | Новых расхождений | Извлечено трасс | Допуск main |
|---|---:|---:|---:|---:|---:|---|
| deepseek | 80 | 37 | 40 | 0 | 69 | пройден |
| goedel | 80 | 35 | 38 | 0 | 65 | пройден |
| kimina | 80 | 0 | 39 | 0 | 71 | пройден |

Verified учитывает завершённые доказательства без обрыва по лимиту токенов. Доли пилота не являются оценками всей основной выборки.

## Текущая основная выборка

План: по 6672 попытки на каждую из трёх моделей, всего 20016; генерация, разметка, активации и анализ идут через Slurm.
Очередь: `{"COMPLETED": 22, "PENDING": 3, "RUNNING": 3, "WAITING": 78}`.

- deepseek: 0 записанных основных ответов; задания: 8464468 RUNNING, 8464471 PENDING.
- goedel: 0 записанных основных ответов; задания: 8464469 RUNNING, 8464472 PENDING.
- kimina: 0 записанных основных ответов; задания: 8464470 RUNNING, 8464473 PENDING.

## Причины остановки и исправления

- Многострочные `<;>`/`;` разделялись на неверные шаги. Операторы и операнды сохраняются в одном сегменте с исходными координатами.
- Блоки `tactics` в рассуждениях сбивали поиск финального Lean-кода Kimina. Исправлено сопоставление Markdown-ограждений и выделение финального ответа.
- Gate проверял не то имя категории инфраструктурной ошибки; исправлены категория, контроль кода extraction и повторное использование shard-манифестов с расхождениями.
- Пустой анализ сообщал об учтённых попытках без явного числа извлечённых трасс. Теперь эти числа разделены, отсутствие данных указано явно.
- Интервалы P3 учитывают число задач с реальными превышениями порога и существующие требования к калибровочным/оценочным превышениям.
- Подгонка GPD ошибочно объявляла граничные решения с gamma ≤ −1 успешными. Сырые значения сохранены в диагностике, но такие решения исключены из оценок, bootstrap-интервалов и сравнений хвостовых моделей. Допустимые отрицательные оценки не обрезаются.
- Проверки campaign больше не исправляют код автоматически. Добавлены отдельный восстановитель и диспетчер в scripts/campaign.

## Проверки

| JUnit | Тесты | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| checks-8464410.xml | 517 | 0 | 0 | 0 |
| checks-8464412.xml | 522 | 0 | 0 | 0 |
| checks-8464413.xml | 523 | 0 | 0 | 0 |
| checks-8464429.xml | 528 | 0 | 0 | 0 |
| checks-8464459.xml | 534 | 0 | 0 | 0 |
| full-8464415.xml | 610 | 1 | 0 | 52 |
| full-8464417.xml | 610 | 0 | 0 | 0 |
| full-8464430.xml | 615 | 0 | 0 | 0 |
| full-8464460.xml | 621 | 0 | 0 | 0 |

Прогоны частично перекрываются; количества не суммируются. Полный финальный прогон относится к неизменяемому snapshot. Ранний full-8464415 запускал тесты из изолированного дерева без нужных fixtures/.git/Lean; он дал один сбой и 52 пропуска. Обёртка исправлена; последующие полные прогоны проверяют совпадение файлов с snapshot и выполняют живые Lean/ML-тесты без пропусков.

## Результаты и ограничения

### deepseek

Категории по температуре: `{"0.6": {"generation_truncation": 4, "localized_tactic_failure": 12, "parse_error": 3, "verified": 21}, "1.0": {"generation_truncation": 3, "localized_tactic_failure": 17, "parse_error": 1, "verified": 19}}`.

Первичная ячейка: T=0.6, слой 14 (индекс с нуля), whitened.
P2: задач 5, refuted трасс 8; jump top1 0.125, surprisal top1 0.375, шанс 0.33854166666666663.

P1, диагностические оценки (без подтверждающих интервалов):

| Подвыборка | Шагов | Задач | Hill | Moment | GPD | Статус |
|---|---:|---:|---:|---:|---:|---|
| at_post | 25 | 5 | None | None | None | insufficient_positive_steps |
| refuted_all | 28 | 5 | None | None | None | insufficient_positive_steps |
| verified | 37 | 6 | None | None | None | insufficient_positive_steps |

P3, q=0.01: положительных превышений 8 на 5 задачах; калибровочных превышений 1 на 1 задачах. GPD raw gamma=-4.787332166794306, пригодная оценка=None, converged=False, сообщение=nonregular endpoint solution: gamma <= -1; no usable GPD estimate.
Доля превышений порога на допустимых шагах: 1.0; покрытие ошибочных шагов: 1.0.

### goedel

Категории по температуре: `{"0.6": {"generation_truncation": 1, "localized_tactic_failure": 12, "parse_error": 6, "verified": 21}, "1.0": {"context_statement_mismatch": 3, "generation_truncation": 2, "localized_tactic_failure": 15, "parse_error": 3, "verified": 17}}`.

Первичная ячейка: T=0.6, слой 17 (индекс с нуля), whitened.
P2: задач 4, refuted трасс 7; jump top1 0.42857142857142855, surprisal top1 0.5714285714285714, шанс 0.2836219336219336.

P1, диагностические оценки (без подтверждающих интервалов):

| Подвыборка | Шагов | Задач | Hill | Moment | GPD | Статус |
|---|---:|---:|---:|---:|---:|---|
| at_post | 26 | 4 | None | None | None | insufficient_positive_steps |
| refuted_all | 36 | 4 | None | None | None | insufficient_positive_steps |
| verified | 40 | 5 | None | None | None | insufficient_positive_steps |

P3, q=0.01: положительных превышений 7 на 4 задачах; калибровочных превышений 1 на 1 задачах. GPD raw gamma=-4.976054499573729, пригодная оценка=None, converged=False, сообщение=nonregular endpoint solution: gamma <= -1; no usable GPD estimate.
Доля превышений порога на допустимых шагах: 1.0; покрытие ошибочных шагов: 1.0.

### kimina

Категории по температуре: `{"0.6": {"generation_truncation": 4, "localized_tactic_failure": 10, "parse_error": 2, "sorry_invalid_proof": 4, "verified": 20}, "1.0": {"generation_truncation": 1, "localized_tactic_failure": 14, "parse_error": 2, "sorry_invalid_proof": 4, "verified": 19}}`.

Причины недопуска доказательств: `{"native_decide_extra_axioms": 8}`. Native_decide с новыми аксиомами исключается по закреплённой политике; это не означает буквальный sorry в исходнике.

Первичная ячейка: T=0.6, слой 17 (индекс с нуля), whitened.
P2: задач 3, refuted трасс 6; jump top1 0.5, surprisal top1 0.3333333333333333, шанс 0.19532163742690056.

P1, диагностические оценки (без подтверждающих интервалов):

| Подвыборка | Шагов | Задач | Hill | Moment | GPD | Статус |
|---|---:|---:|---:|---:|---:|---|
| at_post | 18 | 3 | None | None | None | insufficient_positive_steps |
| refuted_all | 54 | 3 | 0.11112223995417171 | -0.7749780852548436 | None | partial_fit |
| verified | 48 | 5 | None | None | None | insufficient_positive_steps |

P3, q=0.01: положительных превышений 6 на 3 задачах; калибровочных превышений 1 на 1 задачах. GPD raw gamma=-6.827822222059157, пригодная оценка=None, converged=False, сообщение=nonregular endpoint solution: gamma <= -1; no usable GPD estimate.
Доля превышений порога на допустимых шагах: 1.0; покрытие ошибочных шагов: 1.0.

Малые калибровочные наборы делают whitening и пороги нестабильными; высокая доля превышений на допустимых шагах не означает успешную локализацию.

Научные выводы P1–P3: **inconclusive**. Пилот содержит слишком мало независимых задач. Основная выборка, ручная проверка, статистическая калибровка и недостающие sensitivity/null остаются отдельными требованиями. Полный протокол статьи не завершён.

## Воспроизводимость

- Серия: `/beegfs/home/denis.rakhmankin/onebigjump/runs/lean_recovery_20260911_v3`.
- Snapshot: `/beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_11/snapshots/recovery-v3-20260911T015014Z`.
- Очередь: `/beegfs/home/denis.rakhmankin/onebigjump/runs/lean_recovery_20260911_v3/queue.json`.
- tmux: `onebigjump-recovery`.
- При обновлении статистики четыре задания v2 (8464445, 8464446, 8464453, 8464454) отменены до появления записей samples.jsonl; журналы и пустые startup-артефакты сохранены. Все исходные 240 пилотных ответов переиспользованы без пересэмплирования.
- Изменения относительно начала этой ревизии: [revision.patch](revision.patch).
- Числа и детали: [metrics.json](metrics.json); [Slurm](slurm-accounting.tsv).
- Ревизия реальных примеров: [review-notes.md](review-notes.md).

Исторические paper_outputs не изменены. Чужие незакоммиченные изменения сохранены в code-before.tar.gz и before.patch.

Изменённые файлы:
- `docs/e1/REVISION_20260911.md`
- `scripts/campaign/checks.sbatch`
- `scripts/campaign/dispatch.py`
- `scripts/campaign/final_checks.sbatch`
- `scripts/campaign/recover.py`
- `src/onebigjump/e1/analysis.py`
- `src/onebigjump/e1/campaign.py`
- `src/onebigjump/e1/main_analysis.py`
- `src/onebigjump/e1/smoke.py`
- `src/onebigjump/e1/spans.py`
- `src/onebigjump/experiments/p3_overshoot.py`
- `src/onebigjump/experiments/p4_grokking.py`
- `src/onebigjump/experiments/p5_length_law.py`
- `src/onebigjump/lean/segmentation.py`
- `src/onebigjump/stats/estimators.py`
- `src/onebigjump/stats/gpd.py`
- `tests/unit/test_e1_revision_0911.py`
- `tests/unit/test_gpd.py`
