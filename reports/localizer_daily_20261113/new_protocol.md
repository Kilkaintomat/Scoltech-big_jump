# Локализаторы Putnam и стриминговые аналоги полной матрицы

Дата протокола: 13 ноября 2026. Две замороженные LLM: DeepSeek-Prover-V2-7B и Goedel-Prover-V2-8B. Нового обучения LLM и новой генерации нет.

## Серии
1. Retrospective Putnam: nested 5 outer / 3 inner task-group CV на Putnam, все 39 вариантов.
2. Streaming ProofNet: nested 5/3 task-group CV, локализованные отказы и все доступные строго verified.
3. Streaming Putnam: nested 5/3 task-group CV на Putnam, только доступные отказы; принятые шаги до первого отказа дают отрицательные метки.
4. Streaming ProofNet -> Putnam: параметры, lambda и пороги выбираются только на ProofNet; Putnam не участвует в подборе.

## Модели
26 скалярных вариантов: U,P,S,C,PS,PC,SC,PSC,W,PW,SW,CW,PSW,PCW,SCW,PSCW,MD,MDW,N,T,PN,PT,SN,ST,PSN,PST.
P=позиция; S=surprisal текущего фрагмента; N=log1p длины в токенах; T=AST тип; C=N+T; W=log1p нормы whitened приращения; MD=PSC+изменение surprisal и его модуль.
11 векторных: MD+prev,deltaX,state,prev_delta,prev_state,u,ru,z,a,e,ae.
2 гибких: flexible MD, flexible MD+X; GELU hidden width 32/64, linear skip, отдельная линейная ветвь состояния, ensemble трёх seed 2026111201..03.

## Ретроспективная задача
Только локализованные ошибочные доказательства с L>=2. Conditional softmax по всем кандидатам, task-weighted NLL. Типы редкие менее чем в 10 train-группах объединяются в OTHER. Cubic spline: четыре train-weighted квантильных узла 0,1/3,2/3,1; constant extrapolation. Lambda grid 0.0001,0.001,0.01,0.1,1,10; inner task-weighted NLL. U имеет равномерные вероятности и ожидаемый Hit=1/L.

## Стриминговая задача
Решение после завершения текущего фрагмента, без знания конечного L и будущих признаков. Из P удалены t/L и last. Остальные признаки совпадают по смыслу с ретроспективными вариантами. Никакой softmax по полному доказательству: sigmoid score текущего шага. Обучение только на risk set t<=f или всех шагах verified; y=1 только на первом отказе. После отказа шаги не считаются ни правильными, ни отрицательными. Веса 1/(G*n_attempts_in_group*K), где K длина наблюдаемого risk set; длина K используется только в функции потерь, не как признак.
Состояния извлечены causal teacher-forcing. Границы и AST-типы взяты из существующей статической сегментации. Это prefix-causal replay при данных завершённых границах, а не end-to-end онлайн парсер: инвариантность численных признаков к будущему проверяется; incremental AST segmentation отдельно не подтверждается.
Первая тревога: первый score>c. Cutoff берётся по inner-OOF максимумам на verified-траекториях ProofNet при nominal trajectory FPR 5%,10%,20%. Для Putnam нет verified: cutoff отдельно калибруется по максимумам на принятых префиксах длины f (исключая отказ); это pre-error alarm control, не FPR на полностью корректных доказательствах. При f=0 нет принятого префикса. В Putnam FPR по verified будет NA. Test-префиксы и test-f не используются для выбора cutoff.
U в стриминге — обученная константная hazard с intercept, а не равномерный выбор шага.

## Векторы
deltaX=X-Xprev. z=Sigma^(-1/2)(deltaX-mu), калибровка из отдельного исходного calibration split; r=||z||,u=z/r. a=||X-train_mean_X||,e=(X-train_mean_X)/a. Все координаты затем стандартизованы только на train. Нормировка координат не равна делению каждого вектора на его норму. Нулевые направления задаются нулём.

## Гибкие модели
Grid width [32,64], AdamW weight decay [0.0001,0.001,0.01], state ridge [0.001,0.01,0.1] (без состояния 0). lr .001, до 300 эпох, patience 40 по inner validation NLL, три seed. Final epochs — median лучших inner эпох для seed. Среднее вероятностей трёх seed. Для transfer отдельная source-only 3-fold tuning. Для streaming меняется loss на BCE risk set; архитектура сохраняется.

## Проверки и статистика
Препроцессинг, типы, стандартизация, подбор lambda, cutoff и early stopping только на обучающих задачах. Группы задач целиком во фолдах. Сохранение source/input/output SHA, git dirty status, hardware, versions. Проверки: no group overlap, exact candidate coverage, target support, prefix truncation and future perturbation invariance, vector reconstruction, reproduction original offline PSC/PSCW feature matrix.
Метрики offline Hit@1,NLL; streaming risk-set BCE,Brier, first-alarm exact/early/miss и verified-trajectory FPR, с отдельными знаменателями. 10000 paired task bootstrap фиксированных OOF прогнозов; CIs только при >=20 группах. Первичные сравнения PSCW-PSC и MDW-MD; Holm по всей зарегистрированной семье этих сравнений для Hit/exact и NLL отдельно. Остальные варианты исследовательские.
Данные Putnam малы; обучение и оценка на одних задачах запрещены. Ни один запуск не заменяет и не останавливает прежние.
