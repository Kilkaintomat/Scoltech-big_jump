# Проверка замечаний рецензентов и дополнительные эксперименты

Серия reviewer_gaps_20261110_v1. Числа в таблицах получены из сохранённых метрик; незавершённые опыты не считаются результатами. Старые задания и артефакты сохранены.

## Готовые результаты на новых задачах Putnam

Это точность локализации первой отклонённой тактики среди пригодных траекторий, с равным весом групп задач. Это не доля доказанных теорем.

| Модель | Пригодных / назначенных | Групп | MD: признаки + surprisal/изменения | + норма скачка | + полный вектор | + вектор приращения |
|---|---:|---:|---:|---:|---:|---:|
| deepseek | 118 / 304 | 58 | 33.48% | 34.20% | 49.43% | 35.06% |
| goedel | 48 / 304 | 35 | 45.71% | 45.71% | 50.95% | 36.19% |

| Модель | Сравнение с MD | Изменение точности, п.п. | 95% CI, п.п. |
|---|---|---:|---|
| deepseek | MDW-MD | +0.72 | [-1.72, 3.16] |
| deepseek | MD_state-MD | +15.95 | [5.03, 27.01] |
| goedel | MDW-MD | +0.00 | [0.0, 0.0] |
| goedel | MD_state-MD | +5.24 | [-10.48, 20.95] |

Полный вектор даёт более заметный результат, чем одна норма, особенно у DeepSeek. Но существующий локализатор рассматривает готовое решение целиком. Его результат нельзя переносить на последовательный детектор без отдельной проверки. Для Goedel нулевой парный выигрыш нормы на этой выборке не является доказательством эквивалентности методов.

## Проверка без ошибок на первом шаге

| Модель | Попытки / группы | MD | Полный вектор, переобучение без первых ошибок |
|---|---:|---:|---:|
| deepseek | 107 / 56 | 35.42% | 48.36% |
| goedel | 44 / 31 | 39.25% | 51.61% |

## Сопоставление с рецензиями

| Замечание | Состояние | Уже выполнено / новое действие |
|---|---|---|
| Incremental value beyond surprisal and its changes | done | revision_20261107_v1 E2/E2_online; extensions E8. Do not duplicate. Report small model-dependent norm contribution, include signed and absolute adjacent surprisal changes. |
| Layers, whitening/shrinkage, formal-entry versus prompt anchor | done | revision_20261107_v1 E3, controlled anchor recalibration. Use all predefined cells, no selection of a favourable layer. |
| Coverage, exclusions and absent last-step failures | done | revision_20261107_v1 E1 and last-step Lean fixtures; E8 full denominator. Retain unknown first-error status of exclusions. Do not turn unfinished proofs into tactic errors. |
| Hidden-state probe baseline | done plus new E14 | revision E4; frozen Putnam E8; nonfirst-refit E11; permutation E12. Existing retrospective vector benefit motivates causal online comparison, which is not yet measured. |
| Process reward model comparison | new E15 | No genuine pretrained PRM in completed campaigns; ProcessBench B2 already available. Qwen2.5-Math-PRM-7B on identical archived ProcessBench texts/splits; raw scores and nested M0+PRM versus M0+PRM+jump. |
| Practical causal online error detection | new E14 | Old HD/HDW are causal; full state/increment comparisons were retrospective. No final L or future steps; archive nested group training, verified-calibrated thresholds, frozen Putnam transfer. External FPR unavailable if no verified external examples. |
| Beyond Lean and 7-8B scale | domain done; new size E16 | Completed NNG_B2 ProcessBench Qwen2.5-7B reader, NNG_B1 symbolic reader. Same natural-language benchmark, Qwen2.5-1.5B-Instruct reader, same task split and learning protocol. Reader trajectories are not original generator trajectories. |
| Constant hazard and other explanations of success-length law | done | experiments/E2_length_law/a and b: fitted held-out success-length alternatives and local failure hazards. Present alternatives. Exponential decay alone does not identify extreme-value dynamics. |
| Does empirical tail behaviour support Kesten/EVT? | done diagnostics; text needs revision | Signed Hill/moment/GPD diagnostics; E9 held-out Pareto/exponential/lognormal/GPD comparison. Do not identify the Kesten surrogate with transformer dynamics or assume coupling supported by data. No experiment selected just to obtain a positive tail claim. |
| Matched-prefix alternatives and correctness versus semantic novelty | E5/E6/E7 done; E10/E13 underway | Same-text controlled examples and accepted transitions complete; expanded natural alternatives and formal-entry continuations being verified. Keep current E10/E13 jobs. E13 formal-entry results cannot be substituted for interior-prefix results; mixed-outcome support must be reported. |
| First reasoning error versus first rejected Lean tactic; framing and organization | editorial limitation | Lean labels and current validation protocol identify first kernel/tactic rejection only. Use operational label in title/claims. ProcessBench adds human-annotated math errors but does not retrospectively establish earliest semantic error in Lean traces. |

## Новые постановки

**E14. Последовательный детектор.** Для DeepSeek и Goedel сравниваются HD, HDW, HD+state и HD+increment. Полный вектор имеет 4096 координат, PCA не применяется. Используются шаги до первой ошибки включительно и корректные доказательства. Ни полная будущая длина, ни признаки будущих шагов не подаются модели. Преобразования и регуляризация обучаются внутри nested group CV. Порог задаётся по максимумам оценок на корректных валидационных траекториях для целевого FPR 10% и 20%; фактический FPR измеряется отдельно на тесте. Замороженный перенос — на Putnam. Отдельно выводится срез ошибок после первого шага.

**E15. Настоящая PRM.** Qwen2.5-Math-PRM-7B оценивает исходные размеченные шаги ProcessBench. Сравниваются argmin её оценки с argmax нормы скачка/surprisal, а также первое значение p(correct)<0.5 с известной первой ошибкой. Доля корректно принятых верных решений и точность первого обнаружения ошибки объединяются гармоническим средним, которое не следует путать с binary classification F1. Дополнительно обучаются M0, M1, M0+PRM, M1+PRM с разделением задач. Контекст PRM 4096: без обрезки; отдельный учёт покрытия и сравнение на общих примерах. Это PRM для математики, а не дообученный на Lean верификатор.

**E16. Меньшая модель.** Qwen2.5-1.5B-Instruct читает те же решения ProcessBench, что и готовый 7B-эксперимент; zero-based слой14 из28, shrinkage0.1, параметры whitening только по корректной calibration. Сохраняются исходные группы и разделение30/70, отчёты по четырём поднаборам и семействам генераторов. Новых ответов не генерируется. Это сравнение траекторий чтения, а не состояний исходных моделей-авторов решений.

Гиперпараметры не выбираются по новой тестовой выборке. Bootstrap перевыбирает задачи; при числе вносящих вклад групп меньше20 доверительный интервал не публикуется. Интервалы используют фиксированные предсказания, без повторного обучения в bootstrap.

## Уже имевшийся опыт вне Lean

ProcessBench, reader Qwen2.5-7B-Instruct: M0 39.49%, M1 с нормой скачка 39.16%; разница -0.32 п.п. Этот опыт повторно не запускается.

## Статус новой серии

| Этап | Готовый результат / текущий артефакт |
|---|---|
| E14/deepseek | Готово: runs/reviewer_gaps_20261110_v1/E14/deepseek/metrics.json |
| E14/goedel | Готово: runs/reviewer_gaps_20261110_v1/E14/goedel/metrics.json |
| E15 | Готово: runs/reviewer_gaps_20261110_v1/E15/metrics.json |
| E16 | Готово: runs/reviewer_gaps_20261110_v1/E16/metrics.json |

E15: назначено 3400, подготовлено 3400, исключено 0; контекст 4096 токенов.

E16: назначено 3400, подготовлено 3400, исключено 0; контекст 32768 токенов.

### Итог E14/deepseek

| Выборка | Метод | Exact при пороге FPR10% | Фактический FPR | NLL |
|---|---|---:|---:|---:|
| ProofNet | HD | 14.62% | 15.62% | 0.4452 |
| ProofNet | HDW | 13.59% | 15.62% | 0.4434 |
| ProofNet | HD_state | 13.80% | 15.62% | 0.346 |
| ProofNet | HD_increment | 13.60% | 15.62% | 0.3867 |
| Putnam_frozen | HD | 8.62% | — | 0.3544 |
| Putnam_frozen | HDW | 7.76% | — | 0.3516 |
| Putnam_frozen | HD_state | 11.78% | — | 0.3209 |
| Putnam_frozen | HD_increment | 13.51% | — | 0.3722 |

Полные интервалы, страты и проверки находятся в metrics.json рядом с отчётом.

### Итог E14/goedel

| Выборка | Метод | Exact при пороге FPR10% | Фактический FPR | NLL |
|---|---|---:|---:|---:|
| ProofNet | HD | 8.33% | 4.39% | 0.3947 |
| ProofNet | HDW | 8.96% | 4.39% | 0.3872 |
| ProofNet | HD_state | 12.71% | 10.53% | 0.3741 |
| ProofNet | HD_increment | 17.59% | 5.26% | 0.4078 |
| Putnam_frozen | HD | 4.29% | — | 0.3218 |
| Putnam_frozen | HDW | 8.10% | — | 0.3263 |
| Putnam_frozen | HD_state | 6.19% | — | 0.349 |
| Putnam_frozen | HD_increment | 5.71% | — | 0.4239 |

Полные интервалы, страты и проверки находятся в metrics.json рядом с отчётом.

### Итог E15

| Срез | PRM argmin | Норма скачка | Surprisal |
|---|---:|---:|---:|
| pooled | 52.15% | 20.29% | 19.94% |
| gsm8k | 71.09% | 27.89% | 27.21% |
| math | 56.76% | 18.96% | 20.65% |
| olympiadbench | 51.11% | 18.22% | 19.60% |
| omnimath | 43.83% | 20.40% | 17.55% |
| Qwen_family | 50.23% | 20.44% | 21.45% |
| other_generator | 54.39% | 20.33% | 17.85% |

Полные интервалы, страты и проверки находятся в metrics.json рядом с отчётом.

### Итог E16

| Срез | M0 | M1 | Delta, п.п. |
|---|---:|---:|---:|
| pooled | 39.99% | 39.72% | -0.276 |
| Qwen_family | 41.79% | 41.70% | -0.087 |
| other_generator | 35.63% | 35.04% | -0.589 |
| gsm8k | 45.58% | 46.94% | 1.361 |
| math | 39.98% | 39.98% | 0.0 |
| olympiadbench | 36.54% | 36.10% | -0.443 |
| omnimath | 40.42% | 39.56% | -0.854 |

Полные интервалы, страты и проверки находятся в metrics.json рядом с отчётом.

## Задания и воспроизводимость

```json
{
  "date": "2026-11-10",
  "jobs": {
    "download": 8532134,
    "initial_vector_validation": 8532136,
    "preflight": 8532138,
    "gaps-prepare": 8532152,
    "E14-deepseek": 8532153,
    "E14-deepseek-resume": 8532154,
    "E14-goedel": 8532155,
    "E14-goedel-resume": 8532156,
    "E15-PRM-1": 8532157,
    "E15-PRM-2": 8532158,
    "E16-1p5B-1": 8532159,
    "E16-1p5B-2": 8532160,
    "E15-analysis": 8532161,
    "E16-analysis": 8532162,
    "gaps-final-report": 8532163,
    "gaps-launch-report": 8532164
  },
  "new_GPU_reservation_hours_max": 8,
  "gpu_concurrency": 1,
  "gpu_session_hours": 2,
  "protected_existing_jobs": [
    8532108,
    8532109,
    8532110,
    8532111
  ],
  "model_ids": [
    "Qwen/Qwen2.5-Math-PRM-7B",
    "Qwen/Qwen2.5-1.5B-Instruct"
  ],
  "source_sha256": {
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/PROTOCOL.md": "91daa6fd2e8243581ba88218b6b61e8c4025d7db98120b5feea0cc2b9328eccb",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/online_vectors.py": "6da49fba90b447f50cd590cea39324d77a988b38530e615470cea6c17bd53bf1",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/prm_analysis.py": "3adf73d65eca0bd616105830bc07d709785fe6fddd48853c817d7aa43f18096a",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/prepare_readers.py": "1a21fd9fa3f349dca8d14319f5a895999798a8e23bebe70e94e2dec892a74b0d",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/gpu.sbatch": "0575d83fe248f7d890e2761943020052d11d3a19d60aeabe102fdc71f44367c4",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/review_matrix.json": "4550b1a2ea701e32ac50da861af7d7f0fdb56d4e1df3c75e9925777f97c102e0",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/preflight.py": "aaa2302ed356f60c3e0533977bbff611ecb6df8dd74b3edf8daa917d83858434",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/small_extract.py": "30cf7b8aa9bbb47a9a287c178ed86b407ddb5c77c747c1862affbf3816d8a206",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/gap_common.py": "6f993d221a00c1e477b5787e355ba8237ffc13cafb9706dc25c0b0b64a6f0db5",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/report_gaps.py": "dc2785b5346b2cddf93a4dbccdf0cc268f90c08de11f4760c5ffd3d822be7034",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/prm_extract.py": "c0f3a891636e1968358fd01901045989f6ca08a599e2b896e6c63d80c52a4873",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/cpu.sbatch": "410047959522042bc8e18bd89462b62c691f762fd6845459ce6a4884a057f1aa",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/reviewer_comments.txt": "7ac67280b83040ca17c47a7575252f96c818f9390afc4f3d58058e07a8d34f39",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/download.py": "30256f86ca74254800787d481cbdd336e56261dcec581ee133233d78151163d8",
    "/beegfs/home/denis.rakhmankin/onebigjump/experiments/reviewer_gaps_20261110_v1/small_analysis.py": "0050582fbdd3d0dbdc065f24c241f5509921d653c38bec01a632a0795a16db4d"
  }
}
```

Новая очередь ограничена четырьмя последовательными двухчасовыми GPU-слотами: до8 зарезервированных A100-часов. Это верхняя граница бронирования, а не уже потраченное время. Каждая траектория сохраняется отдельно; продолжения используют готовые файлы. CPU-обучение не требует новых LLM-forward. Внешние GPU-задания зависят от ранее поставленного E10/E13, поэтому не прерывают его.

Снимок Slurm:

```text
JobID|JobName|State|ExitCode|Elapsed|Start|End
8532109|obj-E10E13-states-resume|COMPLETED|0:0|00:09:12|2026-11-10T19:47:46|2026-11-10T19:56:58
8532110|obj-E10E13-analysis-resume|COMPLETED|0:0|00:00:27|2026-11-10T19:56:58|2026-11-10T19:57:25
8532111|obj-recovery-final-report|COMPLETED|0:0|00:00:20|2026-11-10T19:57:25|2026-11-10T19:57:45
8532108_2|obj-E13-Lean-resume|COMPLETED|0:0|00:08:14|2026-11-10T19:25:11|2026-11-10T19:33:25
8532108_3|obj-E13-Lean-resume|COMPLETED|0:0|00:22:20|2026-11-10T19:25:11|2026-11-10T19:47:31
8532134|obj-gaps-download|COMPLETED|0:0|00:04:11|2026-11-10T19:37:08|2026-11-10T19:41:19
8532136|obj-E14-validate|COMPLETED|0:0|00:00:26|2026-11-10T19:40:24|2026-11-10T19:40:50
8532138|obj-gaps-preflight|COMPLETED|0:0|00:00:22|2026-11-10T19:42:17|2026-11-10T19:42:39
8532152|obj-gaps-prepare|COMPLETED|0:0|00:01:09|2026-11-10T19:45:24|2026-11-10T19:46:33
8532153|obj-E14-deepseek|COMPLETED|0:0|00:21:21|2026-11-10T19:45:24|2026-11-10T20:06:45
8532154|obj-E14-deepseek-resume|COMPLETED|0:0|00:00:13|2026-11-10T20:06:45|2026-11-10T20:06:58
8532155|obj-E14-goedel|COMPLETED|0:0|00:25:18|2026-11-10T19:45:24|2026-11-10T20:10:42
8532156|obj-E14-goedel-resume|COMPLETED|0:0|00:00:13|2026-11-10T20:10:42|2026-11-10T20:10:55
8532157|obj-E15-PRM-1|COMPLETED|0:0|00:04:44|2026-11-10T19:57:46|2026-11-10T20:02:30
8532158|obj-E15-PRM-2|COMPLETED|0:0|00:00:21|2026-11-10T20:02:46|2026-11-10T20:03:07
8532159|obj-E16-1p5B-1|COMPLETED|0:0|00:03:24|2026-11-10T20:03:46|2026-11-10T20:07:10
8532160|obj-E16-1p5B-2|COMPLETED|0:0|00:00:27|2026-11-10T20:07:46|2026-11-10T20:08:13
8532161|obj-E15-analysis|COMPLETED|0:0|00:01:32|2026-11-10T20:03:07|2026-11-10T20:04:39
8532162|obj-E16-analysis|COMPLETED|0:0|00:03:15|2026-11-10T20:08:13|2026-11-10T20:11:28
8532163|obj-gaps-final-report|RUNNING|0:0|00:00:03|2026-11-10T20:11:28|Unknown
8532164|obj-gaps-launch-report|COMPLETED|0:0|00:00:13|2026-11-10T19:46:33|2026-11-10T19:46:46

```

## Что остаётся ограничением исследования

Сами дополнительные опыты не устанавливают Kesten-механизм в трансформере и не превращают первую отклонённую Lean-тактику в первую ошибку рассуждения. Разницу между предпосылками теорем, диагностикой и измеренными результатами нужно отразить в тексте статьи. Экспоненциальное снижение успеха с длиной имеет альтернативное объяснение через риск ошибки на каждом шаге; соответствующие сравнения уже выполнены. Возможное пересечение ProcessBench с предобучением моделей неизвестно. В новых опытах нет заранее гарантированного положительного эффекта.

Официальные источники: [PRM](https://huggingface.co/Qwen/Qwen2.5-Math-PRM-7B), [ProcessBench](https://github.com/QwenLM/ProcessBench), [1.5B reader](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct).
