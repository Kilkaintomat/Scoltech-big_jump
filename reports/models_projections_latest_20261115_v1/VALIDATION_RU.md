# Проверки публикации

Проверен отдельный архив исходного кода опубликованного репозитория; научные файлы работающей серии не изменялись.

- make test: код выхода 2. Ruff пройден: True. Pytest достигнут: False.

  - `src/onebigjump/e1/extraction.py:51: error: Argument 1 to "__call__" of "_Wrapped" has incompatible type "str"; expected "PreTrainedModel"  [arg-type]`

  - `src/onebigjump/readiness/deduction.py:410: error: Argument 1 to "__call__" of "_Wrapped" has incompatible type "str"; expected "PreTrainedModel"  [arg-type]`

- make test-all: код выхода 2. Ruff пройден: True. Pytest достигнут: False.

  - `src/onebigjump/e1/extraction.py:51: error: Argument 1 to "__call__" of "_Wrapped" has incompatible type "str"; expected "PreTrainedModel"  [arg-type]`

  - `src/onebigjump/readiness/deduction.py:410: error: Argument 1 to "__call__" of "_Wrapped" has incompatible type "str"; expected "PreTrainedModel"  [arg-type]`


Ошибки типов обнаружены в исходном опубликованном коде до добавления отчёта, при текущих установленных версиях зависимостей. Эта публикация меняет только отчёт и его приложения. Эти проверки не заявляются успешными; pytest, включая Lean/ML-тесты, не запустился из-за остановки на mypy.


Хеши всех использованных выходов сверены с исходными manifests. Сжатые таблицы прочитаны обратно; проверено соответствие числа строк метрикам. Ни прогнозы, ни интервалы, ни поправка на множественные проверки здесь не пересчитывались.
