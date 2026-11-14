# Дополнительные проверки локализации и обнаружения отказа Lean

Дата сборки UTC: 2026-11-12T01:31:11.709804+00:00

**Итоговая сборка завершённых A–D.**

## 1. Что проверяется

Две замороженные LLM: DeepSeek-Prover-V2-7B и Goedel-Prover-V2-8B. Состояния имеют 4096 координат и снимаются после блоков 14 и 17 (нумерация с нуля), на конце завершённой AST-тактики. X0 — вход в формальную часть после неформального вступления. Обучаются только пробники.

Отдельно рассматриваются локализация первого отказа в готовой ошибочной попытке, наличие отказа во всей попытке, обнаружение по префиксу и прогноз будущего отказа при ещё принятом префиксе. Предотвращение ошибки не проверяется. Метка относится к Lean-rejection, а не к первому ошибочному математическому замыслу.

## 2. Аудит отбора и verified

| модель | все попытки | strict verified | whole_ok | sorryAx среди предполагаемых недостающих | локализованные отказы | покрытие nonverified, % |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | 840 | 111 | 155 | 44 | 452 | 62.0027 |
| goedel | 840 | 79 | 167 | 88 | 259 | 34.0342 |

Поле whole_proof_ok означает успешность определённого этапа elaboration и само по себе не гарантирует отсутствие дыр в доказательстве. Все предполагаемые недостающие verified-попытки имеют зависимость от sorryAx; их replay не подтверждает корректность. Их нельзя добавлять как отрицательные примеры ошибки. Все действительно verified-попытки уже имеют состояния. Восстановление дополнительных verified-состояний и refit расширенного v2 в этой популяции не требуются: допустимое множество не расширилось.

Предложенная замена покрытия на 66,0% / 38,5% не применяется. Знаменатель nonverified равен всем evaluation-попыткам минус строго verified. Существующие примерно 62% / 34% согласуются с этим определением. Технические pilot-попытки не подмешиваются в evaluation.

В population_manifest сохранены исходные и строгие метки, SHA исходных записей, причины исключения и пересекающиеся флаги. AST и токеновые длины при отсутствии корректного измерения остаются пропусками. Состав тактик рассчитывается по AST, с отдельными весами по тактикам и по задачам/попыткам.

## 3. Воспроизведение исходных пробников

| model | dataset | arm | hit | nll |
| --- | --- | --- | --- | --- |
| deepseek | ProofNet | MD | 0.3939 | 1.7797 |
| deepseek | ProofNet | MDW | 0.4220 | 1.7705 |
| deepseek | ProofNet | MD_increment | 0.4682 | 1.7875 |
| deepseek | ProofNet | MD_state | 0.4764 | 1.6291 |
| goedel | ProofNet | MD | 0.5732 | 1.5706 |
| goedel | ProofNet | MDW | 0.5569 | 1.6262 |
| goedel | ProofNet | MD_increment | 0.5149 | 1.7415 |
| goedel | ProofNet | MD_state | 0.5033 | 1.6739 |

NLL и Hit@1 получены заново из сохранённых предсказаний, с равными весами задач и попыток внутри задачи. На проверенном outer-fold вероятности state/increment пробников воспроизведены точно, максимальное расхождение равно нулю. Эта проверка сверяет саму подготовку признаков и состояния, а не только округлённые таблицы.

## 4. Новые сравнения B

B — прежний сильный ретроспективный MD-baseline: splines позиции, доли пройденного готового текста, длины тактики и surprisal; first/last, тип тактики, изменение surprisal и его модуль. Сравнения добавляют Xprev, dX, X, пары (Xprev,dX)/(Xprev,X). B+Xprev не является прогнозом до тактики: baseline уже видит текущую тактику и длину готового доказательства.

Для приращения сохраняется независимое историческое whitening rho=0.1. z — преобразованный вектор, r=norm(z), u=z/r при r>1e-12, иначе u=0. Сравниваются log1p(r), u, их аддитивная комбинация и z. Для уровня состояния используется отдельное train-центрирование X: a=norm(X-mu_X), e=(X-mu_X)/a при a>1e-12, иначе e=0. Ковариация приращений к X не применяется.

Гибкий baseline содержит линейный skip и один GELU-слой ширины 32/64. Вложенный подбор weight decay, три фиксированных seed; для обеих ветвей усредняются вероятности всех seed. Ветка состояния линейная. Early stopping использует только inner-validation; outer-test не управляет остановкой.

Сохранены прежние 5 outer × 3 inner групповых разбиения. Все scaler, vocabulary и spline knots обучаются внутри train. 108 новых линейных единиц и 24 единицы гибкого baseline включают OOF и source-only refit. В чувствительности T>1 первая позиция остаётся среди кандидатов; прежний E11 с её удалением — отдельный oracle-протокол.

Основной знак эффекта: delta NLL = NLL(base)-NLL(new), delta Hit = Hit(new)-Hit(base) в процентных пунктах. 10000 bootstrap-повторов по задачам; неопределённость условна на уже обученные модели. Для четырёх основных DeepSeek-сравнений на двух evaluation-domain применяется Holm по восьми контрастам. Goedel — дополнительная репликация.

### Основные контрасты

| model | dataset | new | reference | delta | ci95 | ci_family_bonferroni8 | p_holm8 | tasks | attempts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | ProofNet | state | B | 0.1506 | [0.04799286663216905, 0.2575663514037345] | [0.005851002605364031, 0.2995439003912403] | 0.0132 | 166 | 452 |
| deepseek | ProofNet | state | prev | 0.4376 | [0.3279184803076688, 0.5528436778282877] | [0.2831124411090857, 0.5966197193779877] | 0.0008 | 166 | 452 |
| deepseek | ProofNet | u | r | -0.1163 | [-0.2157201741239891, -0.014133622884932355] | [-0.2537787071145294, 0.026553459767423092] | 0.0308 | 166 | 452 |
| deepseek | ProofNet | flexstate | flex | 0.2127 | [0.09624044986934976, 0.33351289933367007] | [0.04641859664838299, 0.3799109967059259] | 0.0025 | 166 | 452 |
| deepseek | Putnam | state | B | 0.2154 | [0.04659399156957907, 0.39738332314671393] | [-0.017435543967651585, 0.47188540745534874] | 0.0308 | 58 | 118 |
| deepseek | Putnam | state | prev | 0.8469 | [0.7005439958841752, 0.9893754857999078] | [0.6452556102088225, 1.049738976411883] | 0.0008 | 58 | 118 |
| deepseek | Putnam | u | r | -0.2735 | [-0.4396609075071856, -0.09962691650222019] | [-0.49402563511031455, -0.028452030957810688] | 0.0048 | 58 | 118 |
| deepseek | Putnam | flexstate | flex | 0.4244 | [0.24214041441084763, 0.605253153444099] | [0.1675602986401478, 0.6794160331611098] | 0.0008 | 58 | 118 |

## 5. Matched-prefix C

Старый обработчик поддерживал только верхний уровень AST и оставлял по 11 задач. До генерации зафиксирована поправка C-1: поддержка вложенных контекстов при сохранении точного токенового префикса, Lean header, целей и локального контекста. Доступны 165/114 исходных задач; feasibility pilot — по 40 задач и 8 альтернатив. Задачи пилота исключаются из основного анализа.

Проверяется первая завершённая AST-тактика, а не первая строка. Accepted, включая завершение доказательства, даёт Y=0; надёжное семантическое отклонение — Y=1. Parse, timeout, resource, sorry, несовпадение контекста и неполная токеновая граница не превращаются в семантические ошибки. Все дубликаты и исключения сохраняются.

Для каждой группы альтернатив используется одна форма padded-forward и каноническое измерение префикса. Xprev должен совпадать побитно, previous-q общий. Замороженные B/BH/BD детекторы взяты из соответствующего OOF-fold исходной задачи. BH содержит текущее состояние и среднее по уже наблюдённому префиксу; отдельно показывается только векторный вклад ретроспективного state-probe. Полный ретроспективный score с неизвестными L/last не применяется.

Within-prefix AUC усредняется по независимым задачам; ties дают 0.5. Основной контраст — BH-B. При числе mixed-задач меньше 20 доверительный интервал не выводится. Основной M и K фиксируются из пилотной дисперсии, частоты mixed-групп и профиля ресурсов. Верхние пределы: 400 задач/модель, K=16, всего 60 новых GPU-часов и 1200 Lean CPU-часов. Сбор не продолжается до значимости.

| model | phase | score | metric | value | ci95 | ci95_MC_seed2 | independent_mixed_tasks | bootstrap_replicates | primary | CI_halfwidth | precision_halfwidth_target | precision_target_met | CI_missing_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | pilot | BH-B | paired_delta_AUC | 0.0000 | — | — | 2 | 10000 | False | — | 0.1000 | False | fewer_than_20_groups |
| deepseek | pilot | BD-B | paired_delta_AUC | 0.0000 | — | — | 2 | 10000 | False | — | 0.1000 | False | fewer_than_20_groups |
| deepseek | main | BH-B | paired_delta_AUC | 0.1144 | — | — | 9 | 10000 | True | — | 0.1000 | False | fewer_than_20_groups |
| deepseek | main | BD-B | paired_delta_AUC | 0.0911 | — | — | 9 | 10000 | False | — | 0.1000 | False | fewer_than_20_groups |
| goedel | pilot | BH-B | paired_delta_AUC | 0.0357 | — | — | 4 | 10000 | False | — | 0.1000 | False | fewer_than_20_groups |
| goedel | pilot | BD-B | paired_delta_AUC | 0.0000 | — | — | 4 | 10000 | False | — | 0.1000 | False | fewer_than_20_groups |
| goedel | main | BH-B | paired_delta_AUC | 0.0380 | — | — | 10 | 10000 | True | — | 0.1000 | False | fewer_than_20_groups |
| goedel | main | BD-B | paired_delta_AUC | -0.0076 | — | — | 10 | 10000 | False | — | 0.1000 | False | fewer_than_20_groups |

## 6. Presence/forecast D

Предыдущая серия завершена: 144/144 fit-единиц и 24/24 summaries. Проверены хеши сохранённых предсказаний и конечные градиенты оптимизации. Заново обучать её не потребовалось. Новые diagnostics пересчитывают рабочие точки из тех же предсказаний.

Offline, present, future1/future3/future5 и future_end имеют разные метки и множества допустимых префиксов. В causal-ветвях нет будущего L, t/L, last или AST-типов, определённых будущим суффиксом. Синтетические проверки подтверждают неизменность признаков раннего префикса при изменении/удалении суффикса.

Порог выбирается по source inner-OOF и затем замораживается. Номинальная частота ложных тревог не подменяет фактическую. В streaming_operating_points.csv разделены prefix FPR, any-alarm FPR на полностью корректных попытках, ранняя/точная/поздняя тревога, пропуск, задержка и тревоги на принятых префиксах ошибочных попыток.

На Putnam в текущем измеримом cohort нет полностью verified-попыток. Поэтому offline AUROC/AP как discrimination и whole-proof FPR не определены; это не нулевой FPR. Для prefix-задач проверяется наличие обоих классов отдельно. Старые интервалы имеют 2000 bootstrap-повторов; дополнительные интервалы first-alarm — 10000.

### NLL: обучение на ProofNet, OOF или замороженный перенос

| model | evaluation | target | B | BD | BH | BW |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | ProofNet | future1 | 0.6056 | 0.6077 | 0.5710 | 0.6073 |
| deepseek | ProofNet | future3 | 0.6596 | 0.6573 | 0.6392 | 0.6589 |
| deepseek | ProofNet | future5 | 0.6010 | 0.5850 | 0.5745 | 0.6019 |
| deepseek | ProofNet | future_end | 0.4299 | 0.3505 | 0.2942 | 0.4288 |
| deepseek | ProofNet | offline | 0.3223 | 0.3562 | 0.3364 | 0.3153 |
| deepseek | ProofNet | present | 0.4745 | 0.4725 | 0.4249 | 0.4720 |
| deepseek | Putnam | future1 | 0.5621 | 0.5705 | 0.5263 | 0.5621 |
| deepseek | Putnam | future3 | 0.6779 | 0.7011 | 0.7030 | 0.6776 |
| deepseek | Putnam | future5 | 0.6089 | 0.6295 | 0.6513 | 0.6090 |
| deepseek | Putnam | future_end | 0.1900 | 0.1115 | 0.0525 | 0.1801 |
| deepseek | Putnam | offline | 0.0858 | 0.0442 | 0.0221 | 0.0879 |
| deepseek | Putnam | present | 0.4352 | 0.4022 | 0.3711 | 0.4297 |
| goedel | ProofNet | future1 | 0.6269 | 0.6767 | 0.6011 | 0.6238 |
| goedel | ProofNet | future3 | 0.6257 | 0.6338 | 0.5869 | 0.6269 |
| goedel | ProofNet | future5 | 0.5568 | 0.5289 | 0.4997 | 0.5536 |
| goedel | ProofNet | future_end | 0.4156 | 0.3305 | 0.2630 | 0.4122 |
| goedel | ProofNet | offline | 0.3614 | 0.3539 | 0.3246 | 0.3469 |
| goedel | ProofNet | present | 0.4595 | 0.4297 | 0.4129 | 0.4522 |
| goedel | Putnam | future1 | 0.5686 | 0.5883 | 0.5732 | 0.5658 |
| goedel | Putnam | future3 | 0.6824 | 0.7850 | 0.7312 | 0.6835 |
| goedel | Putnam | future5 | 0.5775 | 0.6396 | 0.6444 | 0.5773 |
| goedel | Putnam | future_end | 0.1734 | 0.1178 | 0.0669 | 0.1727 |
| goedel | Putnam | offline | 0.1025 | 0.0297 | 0.0133 | 0.1006 |
| goedel | Putnam | present | 0.5327 | 0.5079 | 0.4091 | 0.5087 |

### Present: фактические рабочие точки при source-номинале 10%

| model | arm | exact | prefix_fpr | trajectory_fpr |
| --- | --- | --- | --- | --- |
| deepseek | B | 0.0617 | 0.0295 | 0.0901 |
| deepseek | BD | 0.0956 | 0.0262 | 0.1554 |
| deepseek | BH | 0.0956 | 0.0166 | 0.0473 |
| deepseek | BW | 0.0879 | 0.0373 | 0.1014 |
| goedel | B | 0.0457 | 0.0291 | 0.1000 |
| goedel | BD | 0.1190 | 0.0116 | 0.0722 |
| goedel | BH | 0.0789 | 0.0125 | 0.0556 |
| goedel | BW | 0.0865 | 0.0239 | 0.1111 |

## 7. Состояние выполнения и воспроизводимость

Завершено 161 из 162 контролируемых этапов. Это число включает инфраструктурные и агрегирующие этапы, а не число независимых научных экспериментов.

Блокировки: {}

Контроллер сохраняет checkpoints и атомарные результаты, уважает QOS, запускает не более 6 управляемых CPU и 3 GPU-заданий. На научной ошибке останавливается соответствующая зависимая ветвь; исправные задания продолжаются. Учёт бюджета включает резерв для активных GPU-заданий. Самопроизвольного увеличения лимита и перезапуска всего старого каталога нет.

Рабочая ветка сервера была dirty до начала работы. Исходный diff и статус сохранены; для воспроизводимости приложены хеши новых файлов, зависимостей, split manifests, версий моделей/tokenizer и Lean/mathlib. Старые outputs не изменяются. ProofNet OOF и ProofNet→Putnam — исторические/исследовательские результаты; новые продолжения прежних задач не объявляются новым независимым test.

## 8. Что можно и нельзя утверждать

Аудит отвечает на вопрос о якобы потерянных verified: потерянной корректной подвыборки не обнаружено, причина — неоднозначность поля whole_proof_ok. Это не отменяет selection bias остальных технических исключений; для них представлены длины, AST-состав и доступность измерений.

Сильнейший вид векторной информации, устойчивость к Xprev/гибкому baseline и разделение нормы/направления оцениваются только по завершённой сводке B. Для C вывод зависит от paired AUC и числа mixed-задач. Если точность недостаточна, результат остаётся неопределённым. Успех локализации или обнаружения не является свидетельством предотвращения ошибок или доказательством тяжёлохвостого причинного механизма.

## 9. Команды наблюдения

```bash
ssh zhores "squeue -u denis.rakhmankin"
ssh zhores "tail -30 /beegfs/home/denis.rakhmankin/onebigjump/runs/priority_checks_20261112_v1/controller.log"
ssh zhores "cat /beegfs/home/denis.rakhmankin/onebigjump/runs/priority_checks_20261112_v1/controller_state.json"
# Возобновление dispatcher безопасно при уже работающем экземпляре (flock):
ssh zhores "cd /beegfs/home/denis.rakhmankin/onebigjump && nohup python3 -u /beegfs/home/denis.rakhmankin/onebigjump/experiments/priority_checks_20261112_v1/controller.py >> /beegfs/home/denis.rakhmankin/onebigjump/runs/priority_checks_20261112_v1/controller.log 2>&1 < /dev/null &"
```

Финальный отчёт автоматически собирается в /beegfs/home/denis.rakhmankin/onebigjump/runs/priority_checks_20261112_v1/delivery. Публичная публикация и сообщения рецензентам не выполнялись.

## 10. Дополнительные таблицы аудита и технический статус

Числа ниже получены из selection_final после восстановления формальных токеновых границ и AST корректных попыток. Первичная классификация использует согласованную архивную причину исключения. В failed-элаборации Lean может сам вставлять recovery-hole: наличие sorryAx там не тождественно явно сгенерированному sorry. В спорных whole_ok-попытках отдельно подтверждено именно сгенерированное sorry. initial selection/ и selection_extra/ сохранены для аудита изменений, но заменены selection_v2/selection_extra_v2/selection_final.

Таблица категорий: attempt-weighted квантили, доступность каждого измерения в отдельных колонках; task-weighted длины и парные интервалы разностей приведены в selection_comparisons.csv. Included означает cohort локализации, excluded включает и строго verified.

| model | category | attempts | groups | formal_tokens_measurable | ast_tactics_measurable | truncation_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | accepted_but_unsolved | 22 | 21 | 22 | 22 | 0.0000 |
| deepseek | ambiguous_localization | 50 | 37 | 50 | 50 | 0.0000 |
| deepseek | context_mismatch | 9 | 7 | 0 | 0 | 0.0000 |
| deepseek | generation_truncation | 55 | 41 | 1 | 0 | 1.0000 |
| deepseek | included_reproducible_rejection | 452 | 166 | 452 | 452 | 0.0000 |
| deepseek | parse_error | 38 | 19 | 38 | 0 | 0.0000 |
| deepseek | resource_or_internal | 54 | 34 | 54 | 0 | 0.0000 |
| deepseek | sorry_invalid | 1 | 1 | 1 | 0 | 0.0000 |
| deepseek | sorry_invalid_proof | 44 | 37 | 41 | 0 | 0.7500 |
| deepseek | token_boundary_incomplete | 4 | 4 | 4 | 4 | 0.0000 |
| deepseek | verified | 111 | 37 | 111 | 111 | 0.0000 |
| goedel | accepted_but_unsolved | 14 | 10 | 14 | 14 | 0.0000 |
| goedel | ambiguous_localization | 48 | 36 | 48 | 48 | 0.0000 |
| goedel | context_mismatch | 7 | 4 | 0 | 0 | 0.0000 |
| goedel | generation_truncation | 294 | 136 | 2 | 0 | 1.0000 |
| goedel | included_reproducible_rejection | 259 | 133 | 259 | 259 | 0.0000 |
| goedel | parse_error | 32 | 21 | 32 | 0 | 0.0000 |
| goedel | resource_or_internal | 16 | 14 | 16 | 0 | 0.0000 |
| goedel | sorry_invalid_proof | 88 | 63 | 84 | 0 | 0.9659 |
| goedel | token_boundary_incomplete | 3 | 3 | 3 | 3 | 0.0000 |
| goedel | verified | 79 | 30 | 79 | 79 | 0.0000 |

Compound: сегмент с несколькими AST-узлами или вложенными AST-потомками; правило не подобрано по исходу. Указываются pooled tactic-weight и равные веса задач/попыток.

| model | selection | attempts | measurable_attempts | measurable_groups | compound_tactic_pooled_fraction | compound_equal_task_attempt_fraction | ci95_equal_task | bootstrap_replicates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | included | 452 | 452 | 166 | 0.1170 | 0.1862 | [0.1676495041449319, 0.2061655600040611] | 10000 |
| deepseek | excluded | 388 | 187 | 88 | 0.1389 | 0.2013 | [0.1731740237597137, 0.23186562941544617] | 10000 |
| goedel | included | 259 | 259 | 133 | 0.1093 | 0.2044 | [0.17917145020887126, 0.23055122813373247] | 10000 |
| goedel | excluded | 581 | 144 | 73 | 0.1374 | 0.2314 | [0.1957256200208707, 0.26915309401821147] | 10000 |

### Завершённые новые arms B

Полная сводка B собрана; основные контрасты выше, seed-level значения в flexible_seed_metrics.csv и размеры/регуляризация в fit_diagnostics.csv.

### Matched-prefix: готовность данных

| model | pilot_generation_complete | pilot_label_shards_complete | pilot_measured_alternatives | pilot_measured_prefixes | main_generation_complete | main_label_shards_complete | main_measured_alternatives | main_measured_prefixes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | True | 4 | 172 | 27 | True | 4 | 1167 | 94 |
| goedel | True | 4 | 148 | 25 | True | 4 | 517 | 52 |

Технический GPU smoke завершён: 4 альтернатив на 2 префиксах. Все проверки общего prefix-state прошли побитно. Это проверка измерения, не оценка научного эффекта.

### Зафиксированный основной объём

| model | pilot_tasks | mixed_tasks | mixed_tasks_required_power80 | M | K | draws | projected_gpu_hours_upper | precision_target_feasible_by_conservative_planning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | 40 | 2 | 50 | 125 | 16 | 2000 | 6.6667 | False |
| goedel | 40 | 4 | 50 | 74 | 16 | 1184 | 3.9467 | False |

Power/precision simulation сохраняет независимость на уровне задач; число bad-good пар не увеличивает sample size. Нижняя Wilson-оценка mixed-rate и floor дисперсии дают консервативную sensitivity; ориентир мощности не является обещанием достижимой точности.

### Объём сохранённых состояний

| model | pilot_state_files | pilot_state_bytes | mean_bytes_per_measured_alternative | main_state_bytes_if_all_draws_measured | scope |
| --- | --- | --- | --- | --- | --- |
| deepseek | 172 | 12413562 | 72171.8721 | 144343744.1860 | compressed previous/current/canonical prefix arrays; excludes generation text, Lean detail archives, and repeated checkpoint storage |
| goedel | 148 | 9838181 | 66474.1959 | 78705448.0000 | compressed previous/current/canonical prefix arrays; excludes generation text, Lean detail archives, and repeated checkpoint storage |

### Фактические online рабочие точки с неопределённостью

Present-пороги калиброваны именно по max score на корректной source inner-OOF траектории (worker.thresholds), затем заморожены. В таблице доли, не проценты. CI условны на фиксированные fits, 10000 resampling по задачам. Числа групп/попыток для FPR относятся только к strictly verified; exact — к надёжно локализованным отказам.

| model | arm | metric | value | ci95 | groups | attempts |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | B | trajectory_fpr | 0.0901 | [0.018018018018018018, 0.17117117117117117] | 37.0000 | 111.0000 |
| deepseek | B | exact | 0.0617 | [0.03614457831325301, 0.09186746987951808] | 166.0000 | 452.0000 |
| deepseek | BW | trajectory_fpr | 0.1014 | [0.03153153153153153, 0.1891891891891892] | 37.0000 | 111.0000 |
| deepseek | BW | exact | 0.0879 | [0.056224899598393566, 0.12399598393574296] | 166.0000 | 452.0000 |
| deepseek | BH | trajectory_fpr | 0.0473 | [0.006756756756756757, 0.10135135135135134] | 37.0000 | 111.0000 |
| deepseek | BH | exact | 0.0956 | [0.06325301204819277, 0.13102660642570277] | 166.0000 | 452.0000 |
| deepseek | BD | trajectory_fpr | 0.1554 | [0.060810810810810814, 0.2635135135135135] | 37.0000 | 111.0000 |
| deepseek | BD | exact | 0.0956 | [0.06224899598393573, 0.13353413654618473] | 166.0000 | 452.0000 |
| goedel | B | trajectory_fpr | 0.1000 | [0.02222222222222222, 0.19999999999999998] | 30.0000 | 79.0000 |
| goedel | B | exact | 0.0457 | [0.018170426065162906, 0.07769423558897244] | 133.0000 | 259.0000 |
| goedel | BW | trajectory_fpr | 0.1111 | [0.027777777777777776, 0.2222222222222222] | 30.0000 | 79.0000 |
| goedel | BW | exact | 0.0865 | [0.04887218045112782, 0.12781954887218044] | 133.0000 | 259.0000 |
| goedel | BH | trajectory_fpr | 0.0556 | [0.0, 0.12222222222222222] | 30.0000 | 79.0000 |
| goedel | BH | exact | 0.0789 | [0.041979949874686714, 0.12030075187969924] | 133.0000 | 259.0000 |
| goedel | BD | trajectory_fpr | 0.0722 | [0.016666666666666666, 0.13333333333333333] | 30.0000 | 79.0000 |
| goedel | BD | exact | 0.1190 | [0.07644110275689223, 0.16604010025062657] | 133.0000 | 259.0000 |

BH использует текущее X и среднее X наблюдённого префикса; BD — соответствующие приращения. Они не равны чистому scalar-jump detector. Для старого E14 отдельно приложен воспроизведённый рост exact одновременно с ростом FPR; это другой cohort корректных попыток.

### Незавершённые результаты

Полный пофайловый список — pending_outputs.csv / pending_outputs.json. Число ожидаемых единиц: 0. Финальные probe_* таблицы, matched_prefix_* таблицы и delivery/REPORT_RU.md появляются только после завершения соответствующих зависимостей.

Точный commit не описывает dirty-дерево целиком: initial_worktree.diff фиксирует состояние до работы, source_dependencies.csv и per-run manifests — конкретные файлы. Добавлены sealed Lean runtime manifest и registry primary_contrasts.yaml, экспортированный из уже зафиксированного протокола.

## 11. Графики

calibration_presence_forecast (исходный путь: figures/calibration_presence_forecast.png)

matched_prefix_AUC (исходный путь: figures/matched_prefix_AUC.png)

matched_prefix_paired_effects (исходный путь: figures/matched_prefix_paired_effects.png)

probe_effects (исходный путь: figures/probe_effects.png)

quality_vs_actual_FPR (исходный путь: figures/quality_vs_actual_FPR.png)

radial_directional (исходный путь: figures/radial_directional.png)

selection_formal_ECDF_availability (исходный путь: figures/selection_formal_ECDF_availability.png)

selection_length_ecdf (исходный путь: figures/selection_length_ecdf.png)

selection_tactic_composition (исходный путь: figures/selection_tactic_composition.png)

truncation_by_category (исходный путь: figures/truncation_by_category.png)

