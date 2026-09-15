# Полный аудит сохранённой популяции Lean

Срез: 2026-09-13T21:07:45.136574+00:00

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
| deepseek | 6672 | 3094 | 46.37% |
| goedel | 6672 | 3164 | 47.42% |
| kimina | 6672 | 3357 | 50.31% |

## Сравнение на одинаковых задачах

Общих полностью проверенных задач: 417. На каждую модель и задачу приходится 16 попыток: по 8 при каждой из двух температур.

| Модель | Попыток | verified | Доля | Задач с хотя бы одним verified |
|---|---:|---:|---:|---:|
| deepseek | 6672 | 3094 | 46.37% | 266 / 417 |
| goedel | 6672 | 3164 | 47.42% | 281 / 417 |
| kimina | 6672 | 3357 | 50.31% | 274 / 417 |

### Все категории на одинаковых задачах

| Категория | deepseek | goedel | kimina |
|---|---:|---:|---:|
| context_statement_mismatch | 43 | 106 | 43 |
| generation_truncation | 821 | 1139 | 827 |
| infrastructure_error | 1 | 1 | 5 |
| localized_tactic_failure | 2114 | 1792 | 1652 |
| parse_error | 222 | 247 | 182 |
| sorry_invalid_proof | 4 | 8 | 409 |
| terminal_unsolved_goals | 1 | 0 | 103 |
| timeout_resource | 372 | 215 | 94 |
| verified | 3094 | 3164 | 3357 |

### Разбиение по семейству задач

| Модель | Семейство | Задач | Попыток | verified | Доля verified |
|---|---|---:|---:|---:|---:|
| deepseek | aime | 23 | 368 | 43 | 11.68% |
| deepseek | aimeII | 2 | 32 | 0 | 0.00% |
| deepseek | algebra | 32 | 512 | 258 | 50.39% |
| deepseek | amc12 | 11 | 176 | 74 | 42.05% |
| deepseek | amc12a | 40 | 640 | 181 | 28.28% |
| deepseek | amc12b | 15 | 240 | 96 | 40.00% |
| deepseek | imo | 36 | 576 | 70 | 12.15% |
| deepseek | induction | 14 | 224 | 93 | 41.52% |
| deepseek | mathd_algebra | 125 | 2000 | 1453 | 72.65% |
| deepseek | mathd_numbertheory | 106 | 1696 | 767 | 45.22% |
| deepseek | numbertheory | 13 | 208 | 59 | 28.37% |
| goedel | aime | 23 | 368 | 51 | 13.86% |
| goedel | aimeII | 2 | 32 | 0 | 0.00% |
| goedel | algebra | 32 | 512 | 262 | 51.17% |
| goedel | amc12 | 11 | 176 | 68 | 38.64% |
| goedel | amc12a | 40 | 640 | 188 | 29.38% |
| goedel | amc12b | 15 | 240 | 101 | 42.08% |
| goedel | imo | 36 | 576 | 81 | 14.06% |
| goedel | induction | 14 | 224 | 94 | 41.96% |
| goedel | mathd_algebra | 125 | 2000 | 1468 | 73.40% |
| goedel | mathd_numbertheory | 106 | 1696 | 781 | 46.05% |
| goedel | numbertheory | 13 | 208 | 70 | 33.65% |
| kimina | aime | 23 | 368 | 86 | 23.37% |
| kimina | aimeII | 2 | 32 | 1 | 3.12% |
| kimina | algebra | 32 | 512 | 266 | 51.95% |
| kimina | amc12 | 11 | 176 | 87 | 49.43% |
| kimina | amc12a | 40 | 640 | 228 | 35.62% |
| kimina | amc12b | 15 | 240 | 110 | 45.83% |
| kimina | imo | 36 | 576 | 72 | 12.50% |
| kimina | induction | 14 | 224 | 85 | 37.95% |
| kimina | mathd_algebra | 125 | 2000 | 1474 | 73.70% |
| kimina | mathd_numbertheory | 106 | 1696 | 871 | 51.36% |
| kimina | numbertheory | 13 | 208 | 77 | 37.02% |

Подробности по температуре, роли задачи, ограничениям ресурсов, native-policy-only и изменениям после исправлений — в metrics.json. Примеры с исходными сообщениями Lean — в examples.json.

Ограничения: All saved attempts are accounted for; this finite benchmark does not establish generalisation to other tasks. Attempt success rate differs from at-least-one success per task. Unknown-symbol diagnostics do not establish a causal toolchain effect. Native-policy-only counts do not validate axiom provenance or change the frozen policy. Historical prefix reconstruction does not recover an exact capture timestamp.
