# One Big Jump: общая ревизия и проверка порога P3

Срез на Жоресе: 2026-09-13T17:21:24.720573Z — 2026-09-13T17:40:44.629748+00:00. Все числа автоматически прочитаны из артефактов серверных запусков. Slurm job отчёта: 8466143. Время — UTC; Москва UTC+3.

## Главный вывод

**Новый текущий блокер: kimina/main-verify-1 (job 8466099).** Шард сохранил 752 меток, но содержит 1 необъяснённое whole-proof/replay расхождение и не прошёл gate. Поэтому наличие его manifest не означает готовности downstream анализа. Этот дефект теперь первый приоритет.

Измерительный контур стал надёжнее, но основные научные предсказания пока нельзя объявить подтверждёнными. Генерация сохранена; исправленная проверка Lean продолжается. P4 воспроизвёл обучение без подтверждённого перехода хвостового индекса. Дедукционные пилоты не прошли допуск по формату. Новая проверка P3 отделяет проблемы оптимизации от порога, отбора и малого объёма калибровки.

Новая независимая проверка завершена: 1000 родительских наборов и 2000 условий по объёму calibration. Кандидат зафиксирован заранее: larger/independent_floor/percentile. Семейная проверка Monte Carlo обнаружила недопокрытие: bounded_null, exponential_null, lower_support. Основной метод не заменён.

Для дальнейшей работы: [план](NEXT_PLAN.md), [задание другому GPT](FOR_REVIEWING_GPT.md), [метрики](metrics.json), [все ячейки P3](P3_ALL_CELLS.md), [независимая сверка интервалов](selection-integrity.json).

## Границы ревизии

Проверены текущие очереди, завершённые main-шарды, валидация Lean и смысл native-policy исключений, оба пилота дедукции, происхождение пилотных контролей, все парные P4, новый и предыдущий P3. Хеши проверяются рекурсивно на сервере. Полные веса и активации остаются на сервере. Это не новый прогон всех исторических симуляций и всех экспериментов draft.

| Ветка | Вычислительное состояние | Научное состояние |
| --- | --- | --- |
| Основная Lean | Генерация сохранена; проверка/последующие стадии выполняются | Полные P1/P2/P3 ещё не готовы |
| P3 optimizer | Численные проверки и независимая валидация завершены | Ремонт optimizer сам по себе не устраняет недопокрытие |
| P3 threshold/selection | Новая фиксированная проверка завершена | Ограничения и все сценарии ниже |
| Whitening/позиция | Пилотная сетка завершена; main ждёт измерений | Чувствительность к calibration и первому шагу |
| P4 | Парные real/null завершены | Обучение есть; ожидаемый переход xi не показан |
| Дедукция/P5 | Два development-пилота не прошли gate | Main закрыт; P5 пока не тестируется |
| Программа draft | Реализована частично | Нельзя заявлять полную репликацию |

## Основная кампания

| Модель | Сохранено генераций | Задач | Шардов с manifest | Архивных меток шардов | Строк в текущих журналах |
| --- | --- | --- | --- | --- | --- |
| deepseek | 6672 | 417 | 2 | 1600 | 1862 |
| goedel | 6672 | 417 | 2 | 1600 | 1894 |
| kimina | 6672 | 417 | 2 | 1600 | 1894 |

Всего сохранено 20016 попыток. Архивные метки шардов с manifest (включая шард с непройденным gate) сверены по request_sha256=identity исходных попыток; посторонних ID, дублей и нарушений absorption не найдено. Исходные токены не перегенерировались. Это проверка целостности и формальных инвариантов, не ручное доказательство правильности каждой метки.

| Очередь | Состояния | Последний опрос UTC |
| --- | --- | --- |
| controls_20260913_local | {"COMPLETED": 40, "WAITING": 69} | 2026-09-13T17:21:00.021227Z |
| development_20260913 | {"COMPLETED": 16, "FAILED": 1} | 2026-09-13T13:59:56.068441Z |
| development_20260913_exactlength | {"COMPLETED": 7, "FAILED": 1} | 2026-09-13T15:50:44.399892Z |
| lean_reverification_20260913 | {"BLOCKED": 36, "COMPLETED": 51, "FAILED": 18} | 2026-09-13T15:44:21.106879Z |
| lean_reverification_20260913_local | {"BLOCKED": 12, "COMPLETED": 49, "FAILED": 1, "RUNNING": 4, "WAITING": 38} | 2026-09-13T17:21:06.372163Z |

| Модель | Стадия | Итоговый manifest доступен |
| --- | --- | --- |
| deepseek | verification | False |
| deepseek | extraction | False |
| deepseek | measurement | False |
| deepseek | analysis | False |
| goedel | verification | False |
| goedel | extraction | False |
| goedel | measurement | False |
| goedel | analysis | False |
| kimina | verification | False |
| kimina | extraction | False |
| kimina | measurement | False |
| kimina | analysis | False |

Захваченный squeue:

~~~text
JOBID  PARTITION                                                         NAME      STATE       TIME     CPUS NODELIST(REASON)
           8466124    ais-htc                          obj0913local-deepseek-main-verify-3    RUNNING       6:20       32 cn70
           8466118    ais-htc                            obj0913local-kimina-main-verify-2    RUNNING      15:51       32 cn55
           8466115    ais-htc                            obj0913local-goedel-main-verify-2    RUNNING      23:22       32 cn56
           8466112    ais-htc                          obj0913local-deepseek-main-verify-2    RUNNING      27:53       32 cn70
~~~

COMPLETED в графе задач включает сохранённые входы и зависимости; это не процент научной готовности. Частичные журналы не заменяют итоговый gather. Отдельная старая очередь относится к истории прежнего инцидента. В текущем v7 есть собственный отказ Kimina, разобранный ниже.

| Модель | Категория архивных меток | Число |
| --- | --- | --- |
| deepseek | context_statement_mismatch | 12 |
| deepseek | generation_truncation | 213 |
| deepseek | localized_tactic_failure | 569 |
| deepseek | parse_error | 36 |
| deepseek | timeout_resource | 81 |
| deepseek | verified | 689 |
| goedel | context_statement_mismatch | 26 |
| goedel | generation_truncation | 270 |
| goedel | localized_tactic_failure | 495 |
| goedel | parse_error | 35 |
| goedel | sorry_invalid_proof | 4 |
| goedel | timeout_resource | 49 |
| goedel | verified | 721 |
| kimina | context_statement_mismatch | 7 |
| kimina | generation_truncation | 213 |
| kimina | localized_tactic_failure | 468 |
| kimina | parse_error | 18 |
| kimina | sorry_invalid_proof | 100 |
| kimina | terminal_unsolved_goals | 24 |
| kimina | timeout_resource | 21 |
| kimina | unsupported_segmentation | 1 |
| kimina | verified | 748 |

## Новый блокер Kimina и проверка исправления

Сохранённый случай: main:mathd_algebra_215:T1.0:a06. В _finalise удалялось фиксированное число символов, а не только пробелы; у строки с меньшим отступом оператор <;> превращался в >. Диагностика выполнялась на тех же исходных токенах в свежих REPL-сессиях.

| Режим | Whole proof | Replay | Категория |
| --- | --- | --- | --- |
| original | True | False | unsupported_segmentation |
| candidate | True | True | verified |

Изолированный кандидат прошёл ограниченную проверку: True; сохранение токенов 8/8; прежние регрессии 6/6. Это не полный допуск новой production-версии. Основные метки, очередь и guard не переписаны.

| Модель | Шарды с архивным manifest | Из них gate passed | Архивные метки | Метки gate-passed шардов |
| --- | --- | --- | --- | --- |
| deepseek | 2 | 2 | 1600 | 1600 |
| goedel | 2 | 2 | 1600 | 1600 |
| kimina | 2 | 1 | 1600 | 848 |

Более свежий срез очередей перед финализацией:

| Очередь | Состояния | Последний опрос UTC |
| --- | --- | --- |
| controls_20260913_local | {"COMPLETED": 40, "WAITING": 69} | 2026-09-13T17:40:02.885818Z |
| lean_reverification_20260913_local | {"COMPLETED": 49, "FAILED": 1, "RUNNING": 4, "WAITING": 38, "BLOCKED": 12} | 2026-09-13T17:40:08.507904Z |

Продолжить: оформить узкое исправление в новом snapshot, выполнить полный набор тестов и live-gate, затем восстановить зависимую ветку в новой recovery lineage с прежними генерациями. Нельзя просто заменить FAILED на COMPLETED или удалить несогласованную трассу. Продолжающиеся основные задачи сохраняют свои результаты.

## Lean: надёжность и исключения

Авторитетный snapshot: /beegfs/home/denis.rakhmankin/onebigjump/audit/revision_2026_09_13/snapshots/lean-local-toolchain-v7. SHA256 source-manifest: 8d6abb2370a0be16b9cd52e20f2da2fd58e7b57488145bce4b6712989a6a7488. Git commit и dirty state записаны в manifests. Точная версия задаётся замороженными хешами, а не только commit.

| Полная валидация | Результат |
| --- | --- |
| errors | 0 |
| failures | 0 |
| skipped | 0 |
| tests | 708 |

Полный набор включал live Lean и GPT-2. Дополнительно проверены реальные доказательства, scopes без переноса константы-ответа, proofStatus, очистка процессов, отделение I/O от математических ошибок и полный toolchain на диске узла. Успех этих проверок не означает, что первопричина сетевого I/O установлена.

Содержательный разбор фиксированного gate-пакета: 36 примеров, 52 компиляций; инфраструктурных ошибок 0, нарушений absorption 0. Это ревью ассистентом, не человеческая подпись и не случайная выборка main. [Пояснения по каждому случаю](artifacts/audit/revision_2026_09_13/8466083-review-attestation/case-review.json).

| Модель | Native-policy-only исключения | Меток в проверенных main-шардах |
| --- | --- | --- |
| deepseek | 0 | 1600 |
| goedel | 0 | 1600 |
| kimina | 97 | 1600 |

Native-policy-only: whole proof и replay прошли, буквальных formal sorry/admit нет, но фиксированная allowlist не разрешает вспомогательную аксиому native_decide, которую создаёт pinned Lean. Это нельзя называть математической ошибкой модели. Основные метки сохранены. Native-inclusive анализ потребует отдельного режима доверия, проверки происхождения аксиом и нового manifest; регулярная allowlist только по имени недостаточна.

## P3: от численной ошибки к порогу и отбору

Предыдущая диагностика выявила неустойчивость старого fit около границы параметров. Ограниченный кандидат ищет внутренние stationary maxima при gamma > -1 и сравнивает их с uniform boundary. Победа границы остаётся недоступной оценкой, а внутренние отрицательные gamma сохраняются.

Численный preflight: 31 случаев; проверено на плотной сетке 1600 точек, расхождений 0. Предыдущая независимая validation: 800 наборов. [Полный предыдущий отчёт](artifacts/audit/revision_2026_09_13/reviews/p3-constrained-validation-v3/REPORT.md).

Если ошибки отбираются только выше c, fit excess Z−tau при tau<c использует неверную нижнюю границу. При корректном u>=c условная GPD сохраняет gamma, а scale меняется как sigma+gamma*u. Эта идентичность проверена до новой генерации. [Первичная работа о threshold exceedances](https://academic.oup.com/jrsssb/article/52/3/393/7027838).

| Параметр нового протокола | Значение |
| --- | --- |
| Seed | 919130000 |
| Наборов на сценарий | 200 |
| Calibration задач | {'current': 48, 'larger': 192} |
| Evaluation задач | 48 |
| Support-pilot задач | 48 |
| Calibration шагов/задачу | 48 |
| Failure значений/задачу | 3 |
| q | 0.01 |
| Bootstrap | 500 |
| Минимум задач | 20 |
| Primary candidate | larger/independent_floor/percentile |

| Метод | Правило и данные |
| --- | --- |
| original | tau из calibration; fit на evaluation |
| observed_minimum | max(tau,min evaluation failure): выбор нижней границы на той же выборке |
| independent_floor | max(tau,min support-pilot failure): отдельная выборка для границы, fit на evaluation |
| oracle_correct_selection | max(tau,true c): диагностическое недоступное на реальных данных знание |
| pooled_original | tau из calibration; fit на evaluation+pilot: тот же общий failure-бюджет, что у independent_floor |

Calibration двух объёмов вложена. Потоки calibration/evaluation/support независимы; bootstrap пересэмплирует задачи во всех группах и пересчитывает порог. Optimizer совпадает с ранее замороженным байт-в-байт. Все методы и percentile/basic сохранены. SeedSequence и роли потоков указаны в протоколе. [Документация NumPy](https://numpy.org/doc/stable/reference/random/bit_generators/generated/numpy.random.SeedSequence.html).

Hard-сценарии включают положительную форму с двумя границами отбора, exponential и bounded null. Soft stress использует плавную вероятность отбора с ненулевым фоном: конечная выбранная выборка не имеет точного GPD-распределения. Её результаты — восстановление parent/asymptotic target при ошибке спецификации, а не точное coverage GPD. Oracle там неприменим.

### Результаты percentile: все методы и бюджеты

| Сценарий | Calibration | Метод | Доступность | Покрытие доступных | Попадание / все | Bias | Width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bounded_null | current | original | 188/200 (94.00%) | 173/188 (92.02%) | 173/200 (86.50%) | -0.052911 | 0.52411 |
| bounded_null | current | observed_minimum | 188/200 (94.00%) | 173/188 (92.02%) | 173/200 (86.50%) | -0.052911 | 0.52407 |
| bounded_null | current | independent_floor | 188/200 (94.00%) | 173/188 (92.02%) | 173/200 (86.50%) | -0.052911 | 0.52408 |
| bounded_null | current | oracle_correct_selection | 188/200 (94.00%) | 173/188 (92.02%) | 173/200 (86.50%) | -0.052911 | 0.52409 |
| bounded_null | current | pooled_original | 200/200 (100.00%) | 180/200 (90.00%) | 180/200 (90.00%) | -0.028734 | 0.33567 |
| bounded_null | larger | original | 194/200 (97.00%) | 168/194 (86.60%) | 168/200 (84.00%) | -0.055075 | 0.51778 |
| bounded_null | larger | observed_minimum | 194/200 (97.00%) | 168/194 (86.60%) | 168/200 (84.00%) | -0.055075 | 0.51778 |
| bounded_null | larger | independent_floor | 194/200 (97.00%) | 168/194 (86.60%) | 168/200 (84.00%) | -0.055075 | 0.51778 |
| bounded_null | larger | oracle_correct_selection | 194/200 (97.00%) | 168/194 (86.60%) | 168/200 (84.00%) | -0.055075 | 0.51778 |
| bounded_null | larger | pooled_original | 200/200 (100.00%) | 175/200 (87.50%) | 175/200 (87.50%) | -0.029001 | 0.32416 |
| exponential_null | current | original | 189/200 (94.50%) | 167/189 (88.36%) | 167/200 (83.50%) | -0.038038 | 0.58815 |
| exponential_null | current | observed_minimum | 189/200 (94.50%) | 167/189 (88.36%) | 167/200 (83.50%) | -0.038038 | 0.58802 |
| exponential_null | current | independent_floor | 189/200 (94.50%) | 167/189 (88.36%) | 167/200 (83.50%) | -0.038038 | 0.58804 |
| exponential_null | current | oracle_correct_selection | 189/200 (94.50%) | 167/189 (88.36%) | 167/200 (83.50%) | -0.038038 | 0.588 |
| exponential_null | current | pooled_original | 200/200 (100.00%) | 180/200 (90.00%) | 180/200 (90.00%) | -0.018548 | 0.38892 |
| exponential_null | larger | original | 197/200 (98.50%) | 175/197 (88.83%) | 175/200 (87.50%) | -0.031407 | 0.57088 |
| exponential_null | larger | observed_minimum | 197/200 (98.50%) | 175/197 (88.83%) | 175/200 (87.50%) | -0.031407 | 0.57088 |
| exponential_null | larger | independent_floor | 197/200 (98.50%) | 175/197 (88.83%) | 175/200 (87.50%) | -0.031407 | 0.57088 |
| exponential_null | larger | oracle_correct_selection | 197/200 (98.50%) | 175/197 (88.83%) | 175/200 (87.50%) | -0.031407 | 0.57088 |
| exponential_null | larger | pooled_original | 200/200 (100.00%) | 179/200 (89.50%) | 179/200 (89.50%) | -0.015064 | 0.3705 |
| lower_support | current | original | 190/200 (95.00%) | 173/190 (91.05%) | 173/200 (86.50%) | -0.045977 | 0.6602 |
| lower_support | current | observed_minimum | 190/200 (95.00%) | 173/190 (91.05%) | 173/200 (86.50%) | -0.045977 | 0.66053 |
| lower_support | current | independent_floor | 190/200 (95.00%) | 173/190 (91.05%) | 173/200 (86.50%) | -0.045977 | 0.66059 |
| lower_support | current | oracle_correct_selection | 190/200 (95.00%) | 173/190 (91.05%) | 173/200 (86.50%) | -0.045977 | 0.66049 |
| lower_support | current | pooled_original | 200/200 (100.00%) | 189/200 (94.50%) | 189/200 (94.50%) | -0.022489 | 0.44883 |
| lower_support | larger | original | 197/200 (98.50%) | 177/197 (89.85%) | 177/200 (88.50%) | -0.046789 | 0.63892 |
| lower_support | larger | observed_minimum | 197/200 (98.50%) | 177/197 (89.85%) | 177/200 (88.50%) | -0.046789 | 0.63892 |
| lower_support | larger | independent_floor | 197/200 (98.50%) | 177/197 (89.85%) | 177/200 (88.50%) | -0.046789 | 0.63892 |
| lower_support | larger | oracle_correct_selection | 197/200 (98.50%) | 177/197 (89.85%) | 177/200 (88.50%) | -0.046789 | 0.63892 |
| lower_support | larger | pooled_original | 200/200 (100.00%) | 184/200 (92.00%) | 184/200 (92.00%) | -0.017895 | 0.43191 |
| original_support | current | original | 200/200 (100.00%) | 162/200 (81.00%) | 162/200 (81.00%) | -0.094104 | 0.52126 |
| original_support | current | observed_minimum | 148/200 (74.00%) | 137/148 (92.57%) | 137/200 (68.50%) | -0.021181 | 0.48414 |
| original_support | current | independent_floor | 147/200 (73.50%) | 137/147 (93.20%) | 137/200 (68.50%) | -0.021143 | 0.48376 |
| original_support | current | oracle_correct_selection | 149/200 (74.50%) | 139/149 (93.29%) | 139/200 (69.50%) | -0.021006 | 0.48229 |
| original_support | current | pooled_original | 200/200 (100.00%) | 163/200 (81.50%) | 163/200 (81.50%) | -0.080549 | 0.39958 |
| original_support | larger | original | 200/200 (100.00%) | 167/200 (83.50%) | 167/200 (83.50%) | -0.065415 | 0.45592 |
| original_support | larger | observed_minimum | 200/200 (100.00%) | 183/200 (91.50%) | 183/200 (91.50%) | -0.021176 | 0.4328 |
| original_support | larger | independent_floor | 200/200 (100.00%) | 184/200 (92.00%) | 184/200 (92.00%) | -0.021513 | 0.432 |
| original_support | larger | oracle_correct_selection | 200/200 (100.00%) | 186/200 (93.00%) | 186/200 (93.00%) | -0.021406 | 0.43086 |
| original_support | larger | pooled_original | 200/200 (100.00%) | 166/200 (83.00%) | 166/200 (83.00%) | -0.053714 | 0.34253 |
| soft_selection_stress | current | original | 130/200 (65.00%) | 113/130 (86.92%) | 113/200 (56.50%) | -0.058425 | 0.72249 |
| soft_selection_stress | current | observed_minimum | 130/200 (65.00%) | 113/130 (86.92%) | 113/200 (56.50%) | -0.058425 | 0.72249 |
| soft_selection_stress | current | independent_floor | 130/200 (65.00%) | 113/130 (86.92%) | 113/200 (56.50%) | -0.058425 | 0.72249 |
| soft_selection_stress | current | pooled_original | 200/200 (100.00%) | 176/200 (88.00%) | 176/200 (88.00%) | -0.034836 | 0.52596 |
| soft_selection_stress | larger | original | 136/200 (68.00%) | 118/136 (86.76%) | 118/200 (59.00%) | -0.052211 | 0.71585 |
| soft_selection_stress | larger | observed_minimum | 136/200 (68.00%) | 118/136 (86.76%) | 118/200 (59.00%) | -0.052211 | 0.71585 |
| soft_selection_stress | larger | independent_floor | 136/200 (68.00%) | 118/136 (86.76%) | 118/200 (59.00%) | -0.052211 | 0.71585 |
| soft_selection_stress | larger | pooled_original | 200/200 (100.00%) | 179/200 (89.50%) | 179/200 (89.50%) | -0.02614 | 0.49942 |

«Попадание / все» считает отсутствие интервала неуспехом процедуры. Это не условное покрытие. Все basic, Monte Carlo CI, направления промахов и причины недоступности — в P3_ALL_CELLS.md.

![P3: доступность и попадание в target](p3-selection.png)

### Зафиксированный кандидат: неопределённость Monte Carlo

| Hard-сценарий | Покрытие | Семейные MC bounds | Недопокрытие обнаружено |
| --- | --- | --- | --- |
| bounded_null | 168/194 (86.60%) | [0.79377, 0.92051] | True |
| exponential_null | 175/197 (88.83%) | [0.82064, 0.93746] | True |
| lower_support | 177/197 (89.85%) | [0.83278, 0.94511] | True |
| original_support | 184/200 (92.00%) | [0.8596, 0.9605] | False |

Семейные bounds учитывают четыре hard-сценария фиксированного кандидата. Это не поправка за выбор лучшей ячейки из всей сетки и не тест эквивалентности номинальному уровню. Выбирать победителя после просмотра этой таблицы нельзя.

| Сценарий | Calibration | Сравнение independent_floor с | Общие доступные | Попадания reference / candidate | Выиграно / потеряно интервалов |
| --- | --- | --- | --- | --- | --- |
| bounded_null | current | original | 188 | 173 / 173 | 0 / 0 |
| bounded_null | current | pooled_original | 188 | 169 / 173 | 0 / 12 |
| bounded_null | current | oracle_correct_selection | 188 | 173 / 173 | 0 / 0 |
| bounded_null | larger | original | 194 | 168 / 168 | 0 / 0 |
| bounded_null | larger | pooled_original | 194 | 170 / 168 | 0 / 6 |
| bounded_null | larger | oracle_correct_selection | 194 | 168 / 168 | 0 / 0 |
| exponential_null | current | original | 189 | 167 / 167 | 0 / 0 |
| exponential_null | current | pooled_original | 189 | 171 / 167 | 0 / 11 |
| exponential_null | current | oracle_correct_selection | 189 | 167 / 167 | 0 / 0 |
| exponential_null | larger | original | 197 | 175 / 175 | 0 / 0 |
| exponential_null | larger | pooled_original | 197 | 176 / 175 | 0 / 3 |
| exponential_null | larger | oracle_correct_selection | 197 | 175 / 175 | 0 / 0 |
| lower_support | current | original | 190 | 173 / 173 | 0 / 0 |
| lower_support | current | pooled_original | 190 | 179 / 173 | 0 / 10 |
| lower_support | current | oracle_correct_selection | 190 | 173 / 173 | 0 / 0 |
| lower_support | larger | original | 197 | 177 / 177 | 0 / 0 |
| lower_support | larger | pooled_original | 197 | 181 / 177 | 0 / 3 |
| lower_support | larger | oracle_correct_selection | 197 | 177 / 177 | 0 / 0 |
| original_support | current | original | 147 | 132 / 137 | 0 / 53 |
| original_support | current | pooled_original | 147 | 133 / 137 | 0 / 53 |
| original_support | current | oracle_correct_selection | 147 | 137 / 137 | 0 / 2 |
| original_support | larger | original | 200 | 167 / 184 | 0 / 0 |
| original_support | larger | pooled_original | 200 | 166 / 184 | 0 / 0 |
| original_support | larger | oracle_correct_selection | 200 | 186 / 184 | 0 / 0 |
| soft_selection_stress | current | original | 130 | 113 / 113 | 0 / 0 |
| soft_selection_stress | current | pooled_original | 130 | 113 / 113 | 0 / 70 |
| soft_selection_stress | larger | original | 136 | 118 / 118 | 0 / 0 |
| soft_selection_stress | larger | pooled_original | 136 | 121 / 118 | 0 / 64 |

Independent floor меняет само правило порога; его перенос в primary P3 был бы изменением протокола. Oracle — контроль механизма, не практическое решение. Увеличение calibration одновременно влияет на точность tau и прохождение gate; поэтому оба показателя отчётны.

q=0.001, межзадачная heterogeneity, сильная зависимость шагов, whitening и поглощающий отбор первой ошибки не проверены этим генератором. Значения внутри синтетических групп независимы; task-bootstrap не делает их реалистично зависимыми. Хороший результат здесь не устанавливает калибровку реального Lean.

Независимая сверка по сохранённым draws: 9600 условий gate/массивов, 96 сводных ячеек, несовпадений 0. Это аудит отчётности, не второй независимый симулятор.

### Содержательные выводы новой проверки

В original_support исходный current/original даёт 162/200 (81.00%). При большей calibration original даёт 167/200 (83.50%), independent_floor 184/200 (92.00%), oracle 186/200 (93.00%). Все эти larger-методы доступны на 200 наборах. Pooled original при том же общем failure-бюджете даёт 166/200 (83.00%). Это поддерживает диагноз ошибки нижней границы: эффект не объясняется одним только добавлением failure-наблюдений.

У current independent_floor условное покрытие 137/147 (93.20%) достигается при доступности 147/200 (73.50%). У larger доступность 200/200 (100.00%). Поэтому прежняя потеря интервалов действительно связана с объёмом calibration, но её устранение не гарантирует правильного coverage.

| Hard-сценарий | Percentile primary | Basic того же метода | Промахи percentile ниже / выше истины | Point bias | Порог ниже support (point / bootstrap) |
| --- | --- | --- | --- | --- | --- |
| bounded_null | 168/194 (86.60%) | 181/194 (93.30%) | 25 / 1 | -0.055075 | 0 / 0 |
| exponential_null | 175/197 (88.83%) | 186/197 (94.42%) | 21 / 1 | -0.031407 | 0 / 0 |
| lower_support | 177/197 (89.85%) | 182/197 (92.39%) | 20 / 0 | -0.046789 | 0 / 0 |
| original_support | 184/200 (92.00%) | 184/200 (92.00%) | 14 / 2 | -0.021513 | 0 / 0 |

В остальных hard-сценариях порог уже лежит выше c; методы original, independent_floor и oracle в larger-режиме совпадают. Недопокрытие сохраняется даже с известной истинной границей. Почти все промахи направлены вниз, point bias отрицателен. Это указывает на оставшуюся проблему конечновыборочного смещения/центрирования bootstrap-интервала; данная проверка не разделяет до конца вклад MLE, случайного числа превышений и bootstrap.

Basic частично улучшает долю попаданий, но не был фиксированным primary. Переназначить его победителем по этой таблице нельзя. Следующий ограниченный диагноз: сравнить известный фиксированный threshold с пересчитываемым threshold на сохранённых моделях, затем зафиксировать одну inferential процедуру и проверить её на fresh validation. Не требуется новая генерация моделей.

В soft stress primary доступен на 136/200 (68.00%), условное восстановление target 118/136 (86.76%), попадание на всей запланированной выборке 118/200 (59.00%). Причины недоступности: {"failure_excesses_insufficient": 64}. При мягком отборе независимый минимум не даёт полезной hard-support гарантии; ограничение объёма failure-tail остаётся.

Итоговое решение P3: кандидат не прошёл критерий надёжного номинального percentile coverage. Основной production не меняется. Простое увеличение calibration и ремонт optimizer не закрывают статистическую задачу.

## Whitening и позиционные эффекты

Пилотная сетка сохранена из раннего lineage. Сравнение семантических меток с текущей версией ниже. Оно не доказывает равенства заново извлечённых активаций. Main-контроли работают от новой основной кампании и до завершения зависимостей не считаются полученными.

| Модель | Control root | Общих ID | Изменённых семантических меток | ID только с одной стороны |
| --- | --- | --- | --- | --- |
| deepseek | /beegfs/home/denis.rakhmankin/onebigjump/runs/lean_reverification_20260912/deepseek | 80 | 0 | 0 |
| goedel | /beegfs/home/denis.rakhmankin/onebigjump/runs/lean_reverification_20260912/goedel | 80 | 0 | 0 |
| kimina | /beegfs/home/denis.rakhmankin/onebigjump/runs/lean_reverification_20260912/kimina | 80 | 0 | 0 |

| Модель | Вариант | Disjoint | Drop first | Shrinkage | Fit шагов | Fit задач | Overlap задач | tau | Accepted > tau | Доля |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | whitening-00 | False | False | 0.05 | 26 | 6 | 6 | 5.0268 | 40/40 | 1 |
| deepseek | whitening-01 | False | False | 0.1 | 26 | 6 | 6 | 5.1606 | 40/40 | 1 |
| deepseek | whitening-02 | False | False | 0.2 | 26 | 6 | 6 | 5.464 | 40/40 | 1 |
| deepseek | whitening-03 | True | False | 0.05 | 13 | 3 | 0 | 242.26 | 10/40 | 0.25 |
| deepseek | whitening-04 | True | False | 0.1 | 13 | 3 | 0 | 171.32 | 10/40 | 0.25 |
| deepseek | whitening-05 | True | False | 0.2 | 13 | 3 | 0 | 121.16 | 10/40 | 0.25 |
| deepseek | whitening-06 | False | True | 0.05 | 16 | 6 | 6 | 3.8471 | 27/27 | 1 |
| deepseek | whitening-07 | False | True | 0.1 | 16 | 6 | 6 | 3.9522 | 27/27 | 1 |
| deepseek | whitening-08 | False | True | 0.2 | 16 | 6 | 6 | 4.191 | 27/27 | 1 |
| deepseek | whitening-09 | True | True | 0.05 | 8 | 3 | 0 | 307.57 | 8/27 | 0.2963 |
| deepseek | whitening-10 | True | True | 0.1 | 8 | 3 | 0 | 217.48 | 8/27 | 0.2963 |
| deepseek | whitening-11 | True | True | 0.2 | 8 | 3 | 0 | 153.79 | 8/27 | 0.2963 |
| goedel | whitening-00 | False | False | 0.05 | 32 | 6 | 6 | 5.6157 | 50/50 | 1 |
| goedel | whitening-01 | False | False | 0.1 | 32 | 6 | 6 | 5.762 | 50/50 | 1 |
| goedel | whitening-02 | False | False | 0.2 | 32 | 6 | 6 | 6.0936 | 50/50 | 1 |
| goedel | whitening-03 | True | False | 0.05 | 17 | 3 | 0 | 242.77 | 5/50 | 0.1 |
| goedel | whitening-04 | True | False | 0.1 | 17 | 3 | 0 | 171.7 | 5/50 | 0.1 |
| goedel | whitening-05 | True | False | 0.2 | 17 | 3 | 0 | 121.47 | 5/50 | 0.1 |
| goedel | whitening-06 | False | True | 0.05 | 21 | 6 | 6 | 4.4771 | 36/36 | 1 |
| goedel | whitening-07 | False | True | 0.1 | 21 | 6 | 6 | 4.5991 | 36/36 | 1 |
| goedel | whitening-08 | False | True | 0.2 | 21 | 6 | 6 | 4.8764 | 36/36 | 1 |
| goedel | whitening-09 | True | True | 0.05 | 11 | 3 | 0 | 306.46 | 7/36 | 0.19444 |
| goedel | whitening-10 | True | True | 0.1 | 11 | 3 | 0 | 216.71 | 7/36 | 0.19444 |
| goedel | whitening-11 | True | True | 0.2 | 11 | 3 | 0 | 153.26 | 7/36 | 0.19444 |
| kimina | whitening-00 | False | False | 0.05 | 40 | 5 | 5 | 6.3216 | 84/84 | 1 |
| kimina | whitening-01 | False | False | 0.1 | 40 | 5 | 5 | 6.4891 | 84/84 | 1 |
| kimina | whitening-02 | False | False | 0.2 | 40 | 5 | 5 | 6.8687 | 84/84 | 1 |
| kimina | whitening-03 | True | False | 0.05 | 31 | 3 | 0 | 302.49 | 5/84 | 0.059524 |
| kimina | whitening-04 | True | False | 0.1 | 31 | 3 | 0 | 213.98 | 5/84 | 0.059524 |
| kimina | whitening-05 | True | False | 0.2 | 31 | 3 | 0 | 151.41 | 5/84 | 0.059524 |
| kimina | whitening-06 | False | True | 0.05 | 30 | 3 | 5 | 5.4308 | 70/70 | 1 |
| kimina | whitening-07 | False | True | 0.1 | 30 | 3 | 5 | 5.578 | 70/70 | 1 |
| kimina | whitening-08 | False | True | 0.2 | 30 | 3 | 5 | 5.9124 | 70/70 | 1 |
| kimina | whitening-09 | True | True | 0.05 | 25 | 2 | 0 | 326.81 | 6/70 | 0.085714 |
| kimina | whitening-10 | True | True | 0.1 | 25 | 2 | 0 | 231.13 | 6/70 | 0.085714 |
| kimina | whitening-11 | True | True | 0.2 | 25 | 2 | 0 | 163.49 | 6/70 | 0.085714 |

Повторное использование calibration для transform и threshold занижает порог относительно новых трасс. Disjoint меняет результат, но малая выборка не устанавливает номинальную tail-вероятность. Shrinkage и исключение первого приращения остаются вторичными проверками; основной слой/статистика/температура сохранены.

| Модель | Статистика | Трасс/задач | Jump top1 | Surprisal top1 | Парный gain | CI |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | innovation | 8/5 | 0.25 | 0.375 | -0.125 | NA |
| deepseek | raw | 8/5 | 0.75 | 0.375 | 0.375 | NA |
| deepseek | whitened | 8/5 | 0.125 | 0.375 | -0.25 | NA |
| goedel | innovation | 7/4 | 0.28571 | 0.57143 | -0.28571 | NA |
| goedel | raw | 7/4 | 0.28571 | 0.57143 | -0.28571 | NA |
| goedel | whitened | 7/4 | 0.42857 | 0.57143 | -0.14286 | NA |
| kimina | innovation | 6/3 | 0.33333 | 0.33333 | 0 | NA |
| kimina | raw | 6/3 | 0.5 | 0.33333 | 0.16667 | NA |
| kimina | whitened | 6/3 | 0.5 | 0.33333 | 0.16667 | NA |

Jump и surprisal сравниваются на одинаковых trace IDs. При недостатке независимых задач CI отсутствует. Исключение первого шага может исключить и трассы, ошибившиеся на нём: популяция меняется. Высокий raw top1 без позиционного контроля не доказывает локализацию математического отказа.

## P4: все парные real/null

| Arm | Seed | Финальная test accuracy | Moment до / после | GPD до / после | Hill до / после | Решение |
| --- | --- | --- | --- | --- | --- | --- |
| real | 0 | 1 | -0.10339 / -0.17473 | -0.11221 / -0.18308 | 0.047473 / 0.041629 | inconclusive |
| real | 1 | 1 | -0.1142 / -0.11776 | -0.14367 / -0.14556 | 0.055362 / 0.050418 | inconclusive |
| real | 2 | 1 | -0.19935 / -0.19325 | -0.20135 / -0.14932 | 0.04202 / 0.03505 | inconclusive |
| real | 3 | 0.99799 | -0.057102 / -0.24542 | -0.053824 / -0.20142 | 0.045918 / 0.050231 | inconclusive |
| real | 4 | 1 | -0.095462 / -0.21877 | -0.10945 / -0.17188 | 0.047787 / 0.041167 | inconclusive |
| null | 0 | 0.0089495 | NA / NA | NA / NA | NA / NA | inconclusive |
| null | 1 | 0.010516 | NA / NA | NA / NA | NA / NA | inconclusive |
| null | 2 | 0.0090614 | NA / NA | NA / NA | NA / NA | inconclusive |
| null | 3 | 0.0080546 | NA / NA | NA / NA | NA / NA | inconclusive |
| null | 4 | 0.0072715 | NA / NA | NA / NA | NA / NA | inconclusive |

NA у null означает отсутствие собственного перехода generalization. Парное сравнение использует real-reference каждого seed:

| Seed | Reference step | Δ moment real | Δ moment null | Парная Δ moment | Парная Δ GPD | Парная Δ Hill |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 21900 | -0.071334 | -0.028747 | -0.042587 | -0.046346 | -0.0064256 |
| 1 | 21000 | -0.0035671 | 0.015868 | -0.019435 | -0.0077478 | -0.0056336 |
| 2 | 15300 | 0.0060999 | -0.0015122 | 0.0076121 | 0.052494 | -0.0061686 |
| 3 | 14500 | -0.18832 | 0.018412 | -0.20673 | -0.15086 | 0.0074449 |
| 4 | 21600 | -0.1233 | -0.01839 | -0.10491 | -0.048599 | -0.0064615 |

Окна вокруг устойчивого перехода test accuracy и fixed-final-frequency измерения сохранены в metrics. Null сопоставляется по парной reference-точке. Независимая единица межзапускового сравнения — training seed. Checkpoint и примеры сложения не увеличивают число независимых training-репликаций.

Пять пар дают ограниченную мощность. Итог: обучение подтверждено; ожидаемый переход xi не продемонстрирован. Отрицательная точечная moment/GPD сама по себе не доказывает bounded support, а положительный Hill не доказывает тяжёлый хвост. Все три оценивателя показаны без clipping gamma.

Fixed-fraction кривые measurement и полная tail-сетка с выбором k — разные анализы. Полные tail/step-*.json включены. Старые GPD bootstrap сохраняют ограничения прежнего fit и не заменены новым кандидатом в этой ревизии.

## Дедукция и P5

worked-example-v2: {"attempts": 80, "categories": {"format_error": 25, "invalid_inference": 43, "verified": 12}, "format_eligible": 55}. Полный аудит в metrics.json → deduction_v2_review. numbered-slots-v3: {"attempts": 80, "categories": {"format_error": 43, "generation_truncation": 1, "invalid_inference": 35, "verified": 1}, "format_eligible": 36}. Оба пилота не прошли gate; main остаётся закрыт.

Gold-checker проверки, исходные ответы и причины исключений сохранены. Задачи между пилотами свежие: это не парный причинный тест промптов. Неизвестные строки/комментарии не удалялись ради gate. Формат и reasoning разделены: повтор исходного факта не считается новым modus ponens.

P5 требует управляемой длины и отложенных задач/длин. Из одной зависимости exp(-theta*L*Fbar(tau)) свободные theta и tau не определяются раздельно без дополнительных ограничений: length-данные определяют произведение. Нужно фиксировать tau и calibration law, отдельно проверять зависимость; сильное утверждение о tolerance требует интервенции по tolerance.

## Остаток полного контракта статьи

| Раздел | Что ещё нужно |
| --- | --- |
| P1/P2/P3 main | Полная разметка → активации → измерения → фиксированный анализ → согласованные контроли |
| P1 | Все три gamma, k-устойчивость и bands, семейства задач, split-half, task resampling и честные NA |
| P2 | Парный surprisal, позиционный null по длине/семейству, первый шаг, ROC; supervised probe отдельной работой |
| P3 | q=0.001, зависимость, heterogeneity, selection и независимая калибровка до confirmatory CI |
| P4 | Итоговый paired seed рисунок/вывод с ограничениями; без новых seeds ради желаемого знака |
| P5 | Допуск deduction, held-out длины/задачи, идентифицируемая модель и зависимый null |
| Kesten/Figure 1 | Отдельно сверить publication-run с контрактом и digests; здесь симуляция заново не запускалась |
| Другие ветки | ProofNet/PutnamBench, другие deduction-модели, two-hop, recurrent depth, Tracr/ngram нельзя считать завершёнными |
| Публикация | Generated tables/figures, compute accounting, исключения, анонимный репозиторий и ограничения |

## Следующие действия и независимый аудит

Подробные приоритеты, зависимости и критерии завершения — в [NEXT_PLAN.md](NEXT_PLAN.md). Ближайший результат: целостная основная выборка и контроли на одной версии измерений, затем научное решение по фиксированной ячейке. Рост данных не исправляет ошибку модели отбора.

artifact-index.json сопоставляет серверные пути, копии и SHA256. manifest.json содержит provenance отчёта, package versions, hardware и digests. source/ — основной v7; экспериментальный P3-код — в artifacts/audit/revision_2026_09_13/p3_selection_v1/code. Все новые bootstrap draws включены. Отсутствующие внешние веса/активации reviewer должен явно перечислить как непроверенные.
