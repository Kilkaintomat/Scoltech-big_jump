# Эксперименты E7–E9: результаты

Все таблицы автоматически построены из сохранённых метрик. Группировка и bootstrap выполняются по независимым задачам, а не по отдельным попыткам.

## Устройство серии

E8 использует 76 новых для истории проекта задач PutnamBench, 4 попытки на задачу и две модели. Отдельные 12 пилотных задач исключены из итоговых метрик. LLM заморожены, BF16; temperature=0.6, максимум 8192 новых токенов. Локализаторы обучены исключительно на старом ProofNet, включая выбор регуляризации и преобразований. Это перенос между наборами задач, а не ещё одна выборка ProofNet.

Новизна относится к истории этого проекта: отсутствие задач в предобучении моделей не установлено. Совместимость формулировок проверена Lean с технической заглушкой; эта проверка не является проверкой эталонного доказательства. Исходные токены, полные ответы, исключения и причины потерь покрытия сохранены.

MD использует признаки шага, surprisal и его изменения; MDW добавляет размер скачка представления. Дополнительно проверяются полный вектор состояния и вектор приращения. Метрики локализации относятся к траекториям с установленной первой ошибкой. Hit — доля точных локализаций; window1 — ошибка не более одного шага; NLL — минус логарифм вероятности истинного шага. Успех генерации полного доказательства — другая величина.

Доверительные интервалы используют 20000 перевыборок групп при минимум 20 группах. Для двух моделей поправка Holm применяется отдельно к основной точности и NLL. При недостаточном числе групп приводятся описательные оценки. Мощность для эффекта 2–3 процентных пункта заранее не гарантируется.

## E8: покрытие и перенос

| Модель | Всего тестовых попыток | Пригодны для локализации | Группы |
| --- | --- | --- | --- |
| deepseek | 304 | 118 | 58 |
| goedel | 304 | 48 | 35 |


| Модель | Популяция | Метод | Hit, % | ±1 шаг, % | NLL |
| --- | --- | --- | --- | --- | --- |
| deepseek | all | MD | 33.4770 | 41.6667 | 1.9359 |
| deepseek | all | MDW | 34.1954 | 41.3793 | 1.9202 |
| deepseek | all | MD_state | 49.4253 | 51.2931 | 1.7205 |
| deepseek | all | MD_increment | 35.0575 | 44.1092 | 2.0507 |
| deepseek | nonfirst | MD | 35.4167 | 43.6012 | 1.9241 |
| deepseek | nonfirst | MDW | 37.3512 | 45.0893 | 1.9090 |
| goedel | all | MD | 45.7143 | 49.5238 | 2.0755 |
| goedel | all | MDW | 45.7143 | 49.5238 | 2.1098 |
| goedel | all | MD_state | 50.9524 | 59.0476 | 1.8459 |
| goedel | all | MD_increment | 36.1905 | 42.3810 | 2.1105 |
| goedel | nonfirst | MD | 39.2473 | 49.4624 | 2.0979 |
| goedel | nonfirst | MDW | 38.7097 | 47.8495 | 2.1325 |


| Модель | Популяция | Сравнение | Метрика | Изменение | 95% CI | p Holm |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | all | MDW-MD | hit | 0.7184 | [-0.017241379310344827, 0.03160919540229885] | 1.0000 |
| deepseek | all | MDW-MD | nll | 0.0156 | [-0.01038483762970493, 0.041298217316394985] | 0.2372 |
| deepseek | all | MDW-MD | window1 | -0.2874 | [-0.02586206896551724, 0.017241379310344827] | — |
| deepseek | all | MD_state-MD | hit | 15.9483 | [0.05028735632183909, 0.27011494252873564] | — |
| deepseek | all | MD_state-MD | nll | 0.2154 | [0.044062231807643286, 0.39926665127647226] | — |
| deepseek | all | MD_state-MD | window1 | 9.6264 | [-0.001436781609195401, 0.1954022988505747] | — |
| deepseek | all | MD_increment-MD | hit | 1.5805 | [-0.054597701149425276, 0.09195402298850575] | — |
| deepseek | all | MD_increment-MD | nll | -0.1149 | [-0.2888360803542094, 0.07008019138459338] | — |
| deepseek | all | MD_increment-MD | window1 | 2.4425 | [-0.048850574712643674, 0.10488505747126438] | — |
| deepseek | all | MDW-MD_state | hit | -15.2299 | [-0.264367816091954, -0.04166666666666667] | — |
| deepseek | all | MDW-MD_state | nll | -0.1997 | [-0.38660812003966194, -0.024654103763392575] | — |
| deepseek | all | MDW-MD_state | window1 | -9.9138 | [-0.19827586206896552, -1.1389356890559531e-17] | — |
| deepseek | nonfirst | MDW-MD | hit | 1.9345 | [-0.008928571428571428, 0.06547619047619048] | — |
| deepseek | nonfirst | MDW-MD | nll | 0.0150 | [-0.006626171367015105, 0.036761068323260426] | — |
| deepseek | nonfirst | MDW-MD | window1 | 1.4881 | [0.0, 0.038690476190476185] | — |
| goedel | all | MDW-MD | hit | 0.0000 | [0.0, 0.0] | 1.0000 |
| goedel | all | MDW-MD | nll | -0.0343 | [-0.07784625299457446, 0.007688264272501178] | 0.2294 |
| goedel | all | MDW-MD | window1 | 0.0000 | [0.0, 0.0] | — |
| goedel | all | MD_state-MD | hit | 5.2381 | [-0.10476190476190476, 0.20952380952380953] | — |
| goedel | all | MD_state-MD | nll | 0.2296 | [-0.08085771608178777, 0.5689201712593532] | — |
| goedel | all | MD_state-MD | window1 | 9.5238 | [-0.07142857142857142, 0.2571428571428571] | — |
| goedel | all | MD_increment-MD | hit | -9.5238 | [-0.2666666666666666, 0.07619047619047618] | — |
| goedel | all | MD_increment-MD | nll | -0.0350 | [-0.39992371935115273, 0.34555461139617416] | — |
| goedel | all | MD_increment-MD | window1 | -7.1429 | [-0.2476190476190476, 0.1] | — |
| goedel | all | MDW-MD_state | hit | -5.2381 | [-0.20952380952380953, 0.10476190476190476] | — |
| goedel | all | MDW-MD_state | nll | -0.2639 | [-0.6103438629330253, 0.05037208304905674] | — |
| goedel | all | MDW-MD_state | window1 | -9.5238 | [-0.2571428571428571, 0.07142857142857142] | — |
| goedel | nonfirst | MDW-MD | hit | -0.5376 | [-0.08602150537634409, 0.059139784946236555] | — |
| goedel | nonfirst | MDW-MD | nll | -0.0346 | [-0.08007802897517395, 0.009410309820317809] | — |
| goedel | nonfirst | MDW-MD | window1 | -1.6129 | [-0.0967741935483871, 0.04838709677419355] | — |

Изменения Hit и window1 показаны в процентных пунктах; их CI в таблице хранится в долях. Для NLL положительное изменение означает уменьшение потерь. H1/H3 и H2 с фактическим покрытием приведены в metrics.json; H2 в этой серии описательный, без bootstrap-интервалов.

## E7: естественные продолжения
На одну задачу выбирается один естественный принятый префикс по фиксированному хеш-порядку без отбора по w/q или исходам. Генерируются восемь продолжений. Lean оценивает первую полностью завершённую тактику; незавершённые, неоднозначные, ресурсные и токенизационные случаи исключаются с указанием причины. Primary-анализ сохраняет частоты повторяющихся валидных текстов; чувствительность по уникальным текстам приведена отдельно.


| Модель | Назначено префиксов | Измерено | Со смешанными исходами | Валидные альтернативы |
| --- | --- | --- | --- | --- |
| deepseek | 5 | 5 | 0 | 25 |
| goedel | 3 | 2 | 0 | 14 |


| Модель | Выборка | Признак | Pair rank, % | 95% CI |
| --- | --- | --- | --- | --- |
| deepseek | raw_pair_rank | w | — | None |
| deepseek | raw_pair_rank | q | — | None |
| deepseek | raw_pair_rank | delta_q | — | None |
| deepseek | distinct_text_pair_rank | w | — | None |
| deepseek | distinct_text_pair_rank | q | — | None |
| deepseek | distinct_text_pair_rank | delta_q | — | None |
| goedel | raw_pair_rank | w | — | None |
| goedel | raw_pair_rank | q | — | None |
| goedel | raw_pair_rank | delta_q | — | None |
| goedel | distinct_text_pair_rank | w | — | None |
| goedel | distinct_text_pair_rank | q | — | None |
| goedel | distinct_text_pair_rank | delta_q | — | None |

Pair rank оценивает вероятность большего признака у отвергнутой тактики, с половинным вкладом равенств. Нулевая величина — 50%. Для обучаемого сравнения simple и simple+jump используется вложенная групповая кросс-валидация; все продолжения одного префикса остаются в одной группе.

### deepseek: обучаемое сравнение

```json
{
  "status": "insufficient_mixed_groups"
}
```

### goedel: обучаемое сравнение

```json
{
  "status": "insufficient_mixed_groups"
}
```

## E9: хвосты и ранговое объяснение

E9 — анализ архивных ProofNet-траекторий на прежних групповых разбиениях. Пороги хвостов выбираются только на train; accepted-pre и first-error анализируются отдельно. Подгонка требует не менее 80 превышений и 20 обучающих групп. Недостаток данных не заменяется ослаблением порогов. Знаки moment и GPD сохраняются; положительный Hill сам по себе не устанавливает семейство хвоста.

| Модель | Популяция / квантиль | Семейство | Фолдов | Тестовых превышений | Групп | NLL | Вне поддержки |
| --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | accepted_pre/0.9 | pareto | 5 | 212 | 72 | 3.5015 | 0 |
| deepseek | accepted_pre/0.9 | exponential | 5 | 212 | 72 | 3.4922 | 0 |
| deepseek | accepted_pre/0.9 | lognormal | 5 | 212 | 72 | 3.4896 | 0 |
| deepseek | accepted_pre/0.9 | gpd | 5 | 212 | 72 | 3.4873 | 0 |
| deepseek | accepted_pre/0.95 | pareto | 5 | 116 | 49 | 3.3776 | 0 |
| deepseek | accepted_pre/0.95 | exponential | 5 | 116 | 49 | 3.3703 | 0 |
| deepseek | accepted_pre/0.95 | lognormal | 5 | 116 | 49 | 3.3668 | 0 |
| deepseek | accepted_pre/0.95 | gpd | 5 | 116 | 49 | 3.3668 | 0 |
| deepseek | accepted_pre/0.975 | pareto | 0 | 0 | 0 | — | 0 |
| deepseek | accepted_pre/0.975 | exponential | 0 | 0 | 0 | — | 0 |
| deepseek | accepted_pre/0.975 | lognormal | 0 | 0 | 0 | — | 0 |
| deepseek | accepted_pre/0.975 | gpd | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.9 | pareto | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.9 | exponential | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.9 | lognormal | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.9 | gpd | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.95 | pareto | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.95 | exponential | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.95 | lognormal | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.95 | gpd | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.975 | pareto | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.975 | exponential | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.975 | lognormal | 0 | 0 | 0 | — | 0 |
| deepseek | first_error/0.975 | gpd | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.9 | pareto | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.9 | exponential | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.9 | lognormal | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.9 | gpd | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.95 | pareto | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.95 | exponential | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.95 | lognormal | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.95 | gpd | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.975 | pareto | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.975 | exponential | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.975 | lognormal | 0 | 0 | 0 | — | 0 |
| goedel | accepted_pre/0.975 | gpd | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.9 | pareto | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.9 | exponential | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.9 | lognormal | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.9 | gpd | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.95 | pareto | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.95 | exponential | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.95 | lognormal | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.95 | gpd | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.975 | pareto | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.975 | exponential | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.975 | lognormal | 0 | 0 | 0 | — | 0 |
| goedel | first_error/0.975 | gpd | 0 | 0 | 0 | — | 0 |


| Модель | Популяция / квантиль | Fold | Статус | Hill | Moment | GPD shape |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | accepted_pre/0.9 | 0 | fitted | 0.0810 | -0.2367 | -0.2227 |
| deepseek | accepted_pre/0.9 | 1 | fitted | 0.0716 | -0.1455 | -0.1707 |
| deepseek | accepted_pre/0.9 | 2 | fitted | 0.0746 | -0.0917 | -0.1276 |
| deepseek | accepted_pre/0.9 | 3 | fitted | 0.0774 | -0.1463 | -0.1601 |
| deepseek | accepted_pre/0.9 | 4 | fitted | 0.0720 | -0.1147 | -0.1273 |
| deepseek | accepted_pre/0.95 | 0 | fitted | 0.0645 | -0.1400 | -0.1689 |
| deepseek | accepted_pre/0.95 | 1 | fitted | 0.0598 | -0.0912 | -0.1145 |
| deepseek | accepted_pre/0.95 | 2 | fitted | 0.0610 | -0.1044 | -0.1295 |
| deepseek | accepted_pre/0.95 | 3 | fitted | 0.0626 | -0.0394 | -0.0649 |
| deepseek | accepted_pre/0.95 | 4 | fitted | 0.0596 | -0.0764 | -0.0888 |
| deepseek | accepted_pre/0.975 | 0 | insufficient_training_tail | — | — | — |
| deepseek | accepted_pre/0.975 | 1 | insufficient_training_tail | — | — | — |
| deepseek | accepted_pre/0.975 | 2 | insufficient_training_tail | — | — | — |
| deepseek | accepted_pre/0.975 | 3 | insufficient_training_tail | — | — | — |
| deepseek | accepted_pre/0.975 | 4 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.9 | 0 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.9 | 1 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.9 | 2 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.9 | 3 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.9 | 4 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.95 | 0 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.95 | 1 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.95 | 2 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.95 | 3 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.95 | 4 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.975 | 0 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.975 | 1 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.975 | 2 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.975 | 3 | insufficient_training_tail | — | — | — |
| deepseek | first_error/0.975 | 4 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.9 | 0 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.9 | 1 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.9 | 2 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.9 | 3 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.9 | 4 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.95 | 0 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.95 | 1 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.95 | 2 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.95 | 3 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.95 | 4 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.975 | 0 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.975 | 1 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.975 | 2 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.975 | 3 | insufficient_training_tail | — | — | — |
| goedel | accepted_pre/0.975 | 4 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.9 | 0 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.9 | 1 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.9 | 2 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.9 | 3 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.9 | 4 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.95 | 0 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.95 | 1 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.95 | 2 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.95 | 3 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.95 | 4 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.975 | 0 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.975 | 1 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.975 | 2 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.975 | 3 | insufficient_training_tail | — | — | — |
| goedel | first_error/0.975 | 4 | insufficient_training_tail | — | — | — |


| Модель | Длина | Метод | Наблюдаемый hit | Предсказанный hit | Brier | Групп |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek | all | pooled | 0.4127 | 0.3049 | 0.1812 | 148 |
| deepseek | all | conditioned | 0.4127 | 0.3071 | 0.1811 | 148 |
| deepseek | all | uniform | 0.4127 | 0.2400 | 0.1991 | 148 |
| deepseek | 2-4 | pooled | 0.6667 | 0.4367 | 0.2394 | 94 |
| deepseek | 2-4 | conditioned | 0.6667 | 0.4425 | 0.2400 | 94 |
| deepseek | 2-4 | uniform | 0.6667 | 0.3679 | 0.2730 | 94 |
| deepseek | 5-10 | pooled | 0.2222 | 0.2148 | 0.1648 | 87 |
| deepseek | 5-10 | conditioned | 0.2222 | 0.2148 | 0.1648 | 87 |
| deepseek | 5-10 | uniform | 0.2222 | 0.1462 | 0.1709 | 87 |
| deepseek | 11+ | pooled | 0.1410 | 0.1139 | 0.1167 | 39 |
| deepseek | 11+ | conditioned | 0.1410 | 0.1139 | 0.1167 | 39 |
| deepseek | 11+ | uniform | 0.1410 | 0.0638 | 0.1228 | 39 |
| goedel | all | pooled | 0.3762 | 0.3198 | 0.2014 | 105 |
| goedel | all | conditioned | 0.3762 | 0.3198 | 0.2014 | 105 |
| goedel | all | uniform | 0.3762 | 0.2464 | 0.2106 | 105 |
| goedel | 2-4 | pooled | 0.6120 | 0.4412 | 0.2662 | 61 |
| goedel | 2-4 | conditioned | 0.6120 | 0.4412 | 0.2662 | 61 |
| goedel | 2-4 | uniform | 0.6120 | 0.3723 | 0.2866 | 61 |
| goedel | 5-10 | pooled | 0.1812 | 0.2372 | 0.1550 | 46 |
| goedel | 5-10 | conditioned | 0.1812 | 0.2372 | 0.1550 | 46 |
| goedel | 5-10 | uniform | 0.1812 | 0.1566 | 0.1516 | 46 |
| goedel | 11+ | pooled | 0.2174 | 0.1250 | 0.1708 | 23 |
| goedel | 11+ | conditioned | 0.2174 | 0.1250 | 0.1708 | 23 |
| goedel | 11+ | uniform | 0.2174 | 0.0604 | 0.1893 | 23 |

## Покрытие и артефакты

```json
{
  "deepseek": {
    "assigned_attempts": 328,
    "pilot_groups": 12,
    "test_groups": 76,
    "E7_requested": 40,
    "E7_labels": {
      "rejected": 25,
      "runtime_error": 4,
      "resource_error": 2,
      "no_complete_first_tactic": 9
    }
  },
  "goedel": {
    "assigned_attempts": 328,
    "pilot_groups": 12,
    "test_groups": 76,
    "E7_requested": 24,
    "E7_labels": {
      "no_complete_first_tactic": 10,
      "rejected": 14
    }
  }
}
```

Проверено 155 manifests, 13847 ссылок с хешами и 966 распределений вероятностей. Полные метрики: metrics.json; плоский экспорт: metrics.csv; проверки: validation.json. Исходные версии и причины технических повторов находятся в manifests, source_history и EXECUTION_NOTES.md.
