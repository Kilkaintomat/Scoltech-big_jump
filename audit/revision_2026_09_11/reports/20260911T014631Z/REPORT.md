# Ревизия Жореса — 11 сентября 2026

Срез UTC: 2026-09-11T01:46:31.203177+00:00.

При подключении активных заданий не было. Предыдущая серия остановилась 9 сентября до основной выборки.
Исправленная обработка выполняется в отдельной серии; исходная генерация и все прежние артефакты сохранены.

Промежуточный повтор lean_recovery_20260911 содержал регрессию выбора финального блока DeepSeek из-за Unicode EOS. Его зависимые стадии остановлены; окончательная серия — lean_recovery_20260911_v2. Парсер дополнительно проверен на всех исходных ответах; ранее корректно выделенные тела доказательств DeepSeek/Goedel сохранены.

| Модель | Исходных попыток | Старых verified | Новых verified | Новых расхождений | Извлечено трасс | Допуск main |
|---|---:|---:|---:|---:|---:|---|
| deepseek | 80 | 37 | 40 | 0 | 69 | не пройден |
| goedel | 80 | 35 | 38 | 0 | 65 | пройден |
| kimina | 80 | 0 | 39 | 0 | 71 | пройден |

Verified учитывает завершённые доказательства без обрыва по лимиту токенов. Доли пилота не являются оценками всей основной выборки.

## Причины остановки и исправления

- Многострочные `<;>`/`;` разделялись на неверные шаги. Операторы и операнды сохраняются в одном сегменте с исходными координатами.
- Блоки `tactics` в рассуждениях сбивали поиск финального Lean-кода Kimina. Исправлено сопоставление Markdown-ограждений и выделение финального ответа.
- Gate проверял не то имя категории инфраструктурной ошибки; исправлены категория, контроль кода extraction и повторное использование shard-манифестов с расхождениями.
- Пустой анализ сообщал об учтённых попытках без явного числа извлечённых трасс. Теперь эти числа разделены, отсутствие данных указано явно.
- Интервалы P3 учитывают число задач с реальными превышениями порога и существующие требования к калибровочным/оценочным превышениям.
- Проверки campaign больше не исправляют код автоматически. Добавлены отдельный восстановитель и диспетчер в scripts/campaign.

## Проверки

| JUnit | Тесты | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| checks-8464410.xml | 517 | 0 | 0 | 0 |
| checks-8464412.xml | 522 | 0 | 0 | 0 |
| checks-8464413.xml | 523 | 0 | 0 | 0 |
| checks-8464429.xml | 528 | 0 | 0 | 0 |
| full-8464415.xml | 610 | 1 | 0 | 52 |
| full-8464417.xml | 610 | 0 | 0 | 0 |
| full-8464430.xml | 615 | 0 | 0 | 0 |

Прогоны частично перекрываются; количества не суммируются. Полный прогон относится к неизменяемому snapshot.

## Результаты и ограничения

### deepseek

Категории по температуре: `{"0.6": {"generation_truncation": 4, "localized_tactic_failure": 12, "parse_error": 3, "verified": 21}, "1.0": {"generation_truncation": 3, "localized_tactic_failure": 17, "parse_error": 1, "verified": 19}}`.

Первичная ячейка: T=0.6, слой 14 (индекс с нуля), whitened.
P2: задач 5, refuted трасс 8; jump top1 0.125, surprisal top1 0.375, шанс 0.33854166666666663.

### goedel

Категории по температуре: `{"0.6": {"generation_truncation": 1, "localized_tactic_failure": 12, "parse_error": 6, "verified": 21}, "1.0": {"context_statement_mismatch": 3, "generation_truncation": 2, "localized_tactic_failure": 15, "parse_error": 3, "verified": 17}}`.

Первичная ячейка: T=0.6, слой 17 (индекс с нуля), whitened.
P2: задач 4, refuted трасс 7; jump top1 0.42857142857142855, surprisal top1 0.5714285714285714, шанс 0.2836219336219336.

### kimina

Категории по температуре: `{"0.6": {"generation_truncation": 4, "localized_tactic_failure": 10, "parse_error": 2, "sorry_invalid_proof": 4, "verified": 20}, "1.0": {"generation_truncation": 1, "localized_tactic_failure": 14, "parse_error": 2, "sorry_invalid_proof": 4, "verified": 19}}`.

Причины недопуска доказательств: `{"native_decide_extra_axioms": 8}`. Native_decide с новыми аксиомами исключается по закреплённой политике; это не означает буквальный sorry в исходнике.

Первичная ячейка: T=0.6, слой 17 (индекс с нуля), whitened.
P2: задач 3, refuted трасс 6; jump top1 0.5, surprisal top1 0.3333333333333333, шанс 0.19532163742690056.

Научные выводы P1–P3: **inconclusive**. Пилот содержит слишком мало независимых задач. Основная выборка, ручная проверка, статистическая калибровка и недостающие sensitivity/null остаются отдельными требованиями. Полный протокол статьи не завершён.

## Воспроизводимость

- Серия: `/beegfs/home/denis.rakhmankin/onebigjump/runs/lean_recovery_20260911_v2`.
- Snapshot: `/beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_11/snapshots/recovery-v2-20260911T012551Z`.
- Очередь: `/beegfs/home/denis.rakhmankin/onebigjump/runs/lean_recovery_20260911_v2/queue.json`.
- tmux: `onebigjump-recovery`.
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
- `src/onebigjump/lean/segmentation.py`
- `src/onebigjump/reporting/._report.py`
- `tests/unit/test_e1_revision_0911.py`
