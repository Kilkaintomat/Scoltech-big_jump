# TeX-проект статьи: revised_v4

Полный по структуре проект extreme_value_reasoning_failure_revised_v4_latex. Исходные файлы скопированы из найденного архива без редактирования.

- [Главный файл main.tex](main.tex).
- [PDF версии v4](article_v4.pdf).
- [Исходный ZIP для скачивания или импорта в Overleaf](source_archive.zip).
- [Состав проекта и SHA-256](source_manifest.json).

Разделы — sections.tex; приложения — app_proofs.tex и app_rest.tex; библиография — refs.tex. В комплект включены fig_threshold.pdf и локальные стили ICLR.

## Версия

Найденный PDF v4 содержит 24 страниц. Он отличается от скачанного 49433_An_Extreme_Value_Perspec (2).pdf, в котором 20 страниц: различаются абстракт и основной текст. Точный TeX-исходник именно скачанного PDF пока не установлен.

Перенос файлов не обновляет статью по последним экспериментам. [Отчёт с результатами](../../reports/models_projections_latest_20261115_v1/REPORT_RU.md) опубликован отдельно и сохранён без удаления разделов.

## Сборка

Главный документ — main.tex. В установленном окружении pdfLaTeX:

~~~sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
~~~

Все явно подключаемые локальные файлы проверены и присутствуют. Свежая сборка PDF не выполнялась: на проверенном вычислительном узле pdfLaTeX отсутствует. article_v4.pdf — найденный готовый файл, а не результат новой сборки.
