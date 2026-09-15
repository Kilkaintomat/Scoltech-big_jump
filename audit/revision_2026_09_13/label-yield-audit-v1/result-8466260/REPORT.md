# Проверка цифр и причин исходов Lean

Срез: 2026-09-13T19:59:35.458161+00:00

Все приведённые ниже числа автоматически пересчитаны из журналов. Основные метки и протоколы не изменены.

## Снимок с рисунка

| Модель | Обработано | verified | verified / обработано | Локализована ошибка |
|---|---:|---:|---:|---:|
| deepseek | 2024 | 825 | 40.76% | 687 |
| goedel | 1945 | 864 | 44.42% | 549 |
| kimina | 1901 | 875 | 46.03% | 548 |

{
  "processed": 5870,
  "verified": 2564,
  "localized_tactic_failure": 1784,
  "processed_fraction": 0.2932653876898481,
  "verified_per_processed": 0.43679727427597953,
  "verified_per_all_generated": 0.12809752198241406,
  "not_yet_processed_at_claim": 14146,
  "all_model_counts_reproduced": true
}

Исторические счётчики проверяются реконструкцией префиксов неизменённых исходных журналов; точное время снимка не восстановлено.
Значение «принятые доказательства» на рисунке соответствует verified. Принятая запись обработки может иметь любой подтверждённый исход.

## Текущие завершённые и проверенные порции

| Модель | Записей с проверенным происхождением | verified | Доля verified |
|---|---:|---:|---:|
| deepseek | 4880 | 2229 | 45.68% |
| goedel | 5664 | 2598 | 45.87% |
| kimina | 4976 | 2371 | 47.65% |

## Сравнение на одинаковых задачах

Общих полностью проверенных задач: 262. На каждую модель и задачу приходится 16 попыток: по 8 при каждой из двух температур.

| Модель | Попыток | verified | Доля | Задач с хотя бы одним verified |
|---|---:|---:|---:|---:|
| deepseek | 4192 | 1899 | 45.30% | 166 / 262 |
| goedel | 4192 | 1961 | 46.78% | 174 / 262 |
| kimina | 4192 | 2037 | 48.59% | 166 / 262 |

### Все категории на одинаковых задачах

| Категория | deepseek | goedel | kimina |
|---|---:|---:|---:|
| context_statement_mismatch | 26 | 74 | 34 |
| generation_truncation | 553 | 772 | 566 |
| localized_tactic_failure | 1344 | 1115 | 1039 |
| parse_error | 138 | 150 | 97 |
| sorry_invalid_proof | 4 | 7 | 296 |
| terminal_unsolved_goals | 1 | 0 | 68 |
| timeout_resource | 227 | 113 | 55 |
| verified | 1899 | 1961 | 2037 |

### Разбиение по семейству задач

| Модель | Семейство | Задач | Попыток | verified | Доля verified |
|---|---|---:|---:|---:|---:|
| deepseek | aime | 17 | 272 | 32 | 11.76% |
| deepseek | aimeII | 2 | 32 | 0 | 0.00% |
| deepseek | algebra | 23 | 368 | 214 | 58.15% |
| deepseek | amc12 | 5 | 80 | 16 | 20.00% |
| deepseek | amc12a | 25 | 400 | 104 | 26.00% |
| deepseek | amc12b | 8 | 128 | 29 | 22.66% |
| deepseek | imo | 24 | 384 | 59 | 15.36% |
| deepseek | induction | 6 | 96 | 49 | 51.04% |
| deepseek | mathd_algebra | 82 | 1312 | 919 | 70.05% |
| deepseek | mathd_numbertheory | 62 | 992 | 432 | 43.55% |
| deepseek | numbertheory | 8 | 128 | 45 | 35.16% |
| goedel | aime | 17 | 272 | 40 | 14.71% |
| goedel | aimeII | 2 | 32 | 0 | 0.00% |
| goedel | algebra | 23 | 368 | 223 | 60.60% |
| goedel | amc12 | 5 | 80 | 28 | 35.00% |
| goedel | amc12a | 25 | 400 | 114 | 28.50% |
| goedel | amc12b | 8 | 128 | 33 | 25.78% |
| goedel | imo | 24 | 384 | 57 | 14.84% |
| goedel | induction | 6 | 96 | 49 | 51.04% |
| goedel | mathd_algebra | 82 | 1312 | 924 | 70.43% |
| goedel | mathd_numbertheory | 62 | 992 | 436 | 43.95% |
| goedel | numbertheory | 8 | 128 | 57 | 44.53% |
| kimina | aime | 17 | 272 | 55 | 20.22% |
| kimina | aimeII | 2 | 32 | 1 | 3.12% |
| kimina | algebra | 23 | 368 | 212 | 57.61% |
| kimina | amc12 | 5 | 80 | 20 | 25.00% |
| kimina | amc12a | 25 | 400 | 142 | 35.50% |
| kimina | amc12b | 8 | 128 | 45 | 35.16% |
| kimina | imo | 24 | 384 | 47 | 12.24% |
| kimina | induction | 6 | 96 | 41 | 42.71% |
| kimina | mathd_algebra | 82 | 1312 | 940 | 71.65% |
| kimina | mathd_numbertheory | 62 | 992 | 480 | 48.39% |
| kimina | numbertheory | 8 | 128 | 54 | 42.19% |

Подробности по температуре, роли задачи, ограничениям ресурсов, native-policy-only и изменениям после исправлений — в metrics.json. Примеры с исходными сообщениями Lean — в examples.json.

Ограничения: Incomplete campaign; completed shards are not a random sample. Attempt success rate differs from at-least-one success per task. Unknown-symbol diagnostics do not establish a causal toolchain effect. Native-policy-only counts do not validate axiom provenance or change the frozen policy. Historical prefix reconstruction does not recover an exact capture timestamp.
