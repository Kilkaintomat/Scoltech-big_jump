# Goedel после удаления длины тактики

Удалена только длина тактики в токенах; тип, позиция и surprisal сохранены. Все варианты переобучены. PST = позиция + surprisal + тип; MD_noN добавляет знаковое и абсолютное соседнее изменение surprisal. W — log1p нормы whitened-приращения; deltaX — исходный 4096-мерный вектор изменения; u — единичное направление whitened-приращения. Удаление явного признака длины не исключает косвенную информацию о ней в типе или скрытых состояниях.

Снимок 2026-11-12T23:04:23.008468+00:00: 176/176 внешних/frozen fits, 48/48 полных ячеек. Частичные фолды не усредняются. [Протокол](no_length_protocol.md), [все метрики](no_length_metrics.csv), [парные сравнения и интервалы](no_length_contrasts.csv), [оставшиеся ячейки](no_length_pending.csv).

## ретроспектива / ProofNet OOF

| Вариант | Hit, % | Δ к своему baseline, п.п. | NLL |
| --- | ---: | ---: | ---: |
| PST | 50.43 | 0.00 | 1.7115 |
| PSTW | 50.93 | 0.50 | 1.6976 |
| PST_deltaX | 51.37 | 0.94 | 1.7566 |
| PST_u | 48.30 | -2.13 | 1.8833 |
| MD_noN | 50.39 | 0.00 | 1.7183 |
| MD_noNW | 51.05 | 0.66 | 1.7038 |
| MD_noN_deltaX | 51.37 | 0.98 | 1.7559 |
| MD_noN_u | 49.05 | -1.34 | 1.8835 |

## ретроспектива / Putnam OOF

| Вариант | Hit, % | Δ к своему baseline, п.п. | NLL |
| --- | ---: | ---: | ---: |
| PST | 34.29 | 0.00 | 2.1164 |
| PSTW | 34.29 | 0.00 | 2.1569 |
| PST_deltaX | 39.05 | 4.76 | 2.4118 |
| PST_u | 23.81 | -10.48 | 2.5660 |
| MD_noN | 32.86 | 0.00 | 2.1338 |
| MD_noNW | 30.00 | -2.86 | 2.2164 |
| MD_noN_deltaX | 39.05 | 6.19 | 2.4089 |
| MD_noN_u | 23.81 | -9.05 | 2.5622 |

## ретроспектива / ProofNet -> Putnam frozen

| Вариант | Hit, % | Δ к своему baseline, п.п. | NLL |
| --- | ---: | ---: | ---: |
| PST | 43.33 | 0.00 | 2.1763 |
| PSTW | 40.00 | -3.33 | 2.2000 |
| PST_deltaX | 33.33 | -10.00 | 2.1276 |
| PST_u | 27.62 | -15.71 | 2.5613 |
| MD_noN | 46.19 | 0.00 | 2.1612 |
| MD_noNW | 45.71 | -0.48 | 2.1841 |
| MD_noN_deltaX | 33.33 | -12.86 | 2.1258 |
| MD_noN_u | 27.62 | -18.57 | 2.5589 |

## streaming / ProofNet OOF

Номинальная калибровка 10%; на ProofNet по verified-траекториям, на Putnam по принятым префиксам. Это обнаружение текущего отказа при заданных архивных границах тактик.

| Вариант | Exact, % | Δ, п.п. | Early, % | Miss, % | Verified FPR, % | BCE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PST | 9.99 | 0.00 | 4.82 | 85.19 | 8.33 | 0.4526 |
| PSTW | 10.55 | 0.56 | 6.20 | 83.25 | 8.33 | 0.4494 |
| PST_deltaX | 18.95 | 8.96 | 2.26 | 78.80 | 12.78 | 0.4175 |
| PST_u | 25.05 | 15.06 | 2.13 | 72.82 | 15.83 | 0.4486 |
| MD_noN | 9.99 | 0.00 | 4.82 | 85.19 | 8.33 | 0.4527 |
| MD_noNW | 11.49 | 1.50 | 5.95 | 82.56 | 7.22 | 0.4492 |
| MD_noN_deltaX | 20.08 | 10.09 | 2.26 | 77.67 | 12.78 | 0.4174 |
| MD_noN_u | 25.05 | 15.06 | 2.13 | 72.82 | 15.83 | 0.4486 |

## streaming / Putnam OOF

Номинальная калибровка 10%; на ProofNet по verified-траекториям, на Putnam по принятым префиксам. Это обнаружение текущего отказа при заданных архивных границах тактик.

| Вариант | Exact, % | Δ, п.п. | Early, % | Miss, % | Verified FPR, % | BCE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PST | 10.95 | 0.00 | 4.29 | 84.76 | NA | 0.4739 |
| PSTW | 10.00 | -0.95 | 1.43 | 88.57 | NA | 0.5007 |
| PST_deltaX | 11.43 | 0.48 | 11.90 | 76.67 | NA | 0.5330 |
| PST_u | 1.43 | -9.52 | 5.71 | 92.86 | NA | 0.5976 |
| MD_noN | 6.67 | 0.00 | 5.71 | 87.62 | NA | 0.4775 |
| MD_noNW | 7.14 | 0.48 | 6.67 | 86.19 | NA | 0.5038 |
| MD_noN_deltaX | 11.43 | 4.76 | 11.90 | 76.67 | NA | 0.5330 |
| MD_noN_u | 1.43 | -5.24 | 5.71 | 92.86 | NA | 0.5976 |

## streaming / ProofNet -> Putnam frozen

Номинальная калибровка 10%; на ProofNet по verified-траекториям, на Putnam по принятым префиксам. Это обнаружение текущего отказа при заданных архивных границах тактик.

| Вариант | Exact, % | Δ, п.п. | Early, % | Miss, % | Verified FPR, % | BCE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PST | 5.71 | 0.00 | 1.43 | 92.86 | NA | 0.3402 |
| PSTW | 5.71 | 0.00 | 0.00 | 94.29 | NA | 0.3428 |
| PST_deltaX | 9.52 | 3.81 | 2.86 | 87.62 | NA | 0.4420 |
| PST_u | 7.14 | 1.43 | 2.86 | 90.00 | NA | 0.5078 |
| MD_noN | 5.71 | 0.00 | 1.43 | 92.86 | NA | 0.3382 |
| MD_noNW | 5.71 | 0.00 | 0.00 | 94.29 | NA | 0.3407 |
| MD_noN_deltaX | 9.52 | 3.81 | 2.86 | 87.62 | NA | 0.4413 |
| MD_noN_u | 7.14 | 1.43 | 2.86 | 90.00 | NA | 0.5072 |

## Парные изменения

Δ попадания = новый вариант минус baseline; выигрыш NLL = baseline минус новый вариант. Интервалы: 10000 bootstrap задач при фиксированных моделях; минимум 20 групп. Holm24 применяется к двум основным добавкам W и deltaX, двум baseline и шести условиям отдельно для NLL и попадания; u — дополнительный вариант без этой поправки.

| Условие | Сравнение | Метрика | Δ | 95% CI | Holm24 p |
| --- | --- | --- | ---: | --- | ---: |
| ретроспектива / ProofNet OOF | PSTW-PST | nll | 0.0138 | [-0.0159; 0.0432] | 1.0000 |
| ретроспектива / ProofNet OOF | PSTW-PST | hit | 0.5013 | [-2.3825; 3.6967] | 1.0000 |
| ретроспектива / ProofNet OOF | PST_deltaX-PST | nll | -0.0452 | [-0.1961; 0.1077] | 1.0000 |
| ретроспектива / ProofNet OOF | PST_deltaX-PST | hit | 0.9398 | [-5.4511; 7.4561] | 1.0000 |
| ретроспектива / ProofNet OOF | PST_u-PST | nll | -0.1718 | [-0.3518; 0.0051] | NA |
| ретроспектива / ProofNet OOF | PST_u-PST | hit | -2.1303 | [-9.1479; 4.7619] | NA |
| ретроспектива / ProofNet OOF | MD_noNW-MD_noN | nll | 0.0145 | [-0.0151; 0.0441] | 1.0000 |
| ретроспектива / ProofNet OOF | MD_noNW-MD_noN | hit | 0.6642 | [-2.3308; 3.9850] | 1.0000 |
| ретроспектива / ProofNet OOF | MD_noN_deltaX-MD_noN | nll | -0.0376 | [-0.1922; 0.1185] | 1.0000 |
| ретроспектива / ProofNet OOF | MD_noN_deltaX-MD_noN | hit | 0.9774 | [-5.4762; 7.5066] | 1.0000 |
| ретроспектива / ProofNet OOF | MD_noN_u-MD_noN | nll | -0.1652 | [-0.3472; 0.0156] | NA |
| ретроспектива / ProofNet OOF | MD_noN_u-MD_noN | hit | -1.3409 | [-8.3584; 5.5764] | NA |
| ретроспектива / Putnam OOF | PSTW-PST | nll | -0.0405 | [-0.0724; -0.0141] | 0.1701 |
| ретроспектива / Putnam OOF | PSTW-PST | hit | 0.0000 | [0.0000; 0.0000] | 1.0000 |
| ретроспектива / Putnam OOF | PST_deltaX-PST | nll | -0.2954 | [-0.6734; 0.0753] | 1.0000 |
| ретроспектива / Putnam OOF | PST_deltaX-PST | hit | 4.7619 | [-10.0000; 20.0000] | 1.0000 |
| ретроспектива / Putnam OOF | PST_u-PST | nll | -0.4496 | [-0.7355; -0.1537] | NA |
| ретроспектива / Putnam OOF | PST_u-PST | hit | -10.4762 | [-24.2857; 2.8571] | NA |
| ретроспектива / Putnam OOF | MD_noNW-MD_noN | nll | -0.0826 | [-0.1419; -0.0316] | 0.0897 |
| ретроспектива / Putnam OOF | MD_noNW-MD_noN | hit | -2.8571 | [-8.5714; 0.0000] | 1.0000 |
| ретроспектива / Putnam OOF | MD_noN_deltaX-MD_noN | nll | -0.2751 | [-0.6573; 0.0901] | 1.0000 |
| ретроспектива / Putnam OOF | MD_noN_deltaX-MD_noN | hit | 6.1905 | [-9.0476; 21.9048] | 1.0000 |
| ретроспектива / Putnam OOF | MD_noN_u-MD_noN | nll | -0.4284 | [-0.7040; -0.1506] | NA |
| ретроспектива / Putnam OOF | MD_noN_u-MD_noN | hit | -9.0476 | [-23.3333; 4.7619] | NA |
| ретроспектива / ProofNet -> Putnam frozen | PSTW-PST | nll | -0.0237 | [-0.0759; 0.0258] | 1.0000 |
| ретроспектива / ProofNet -> Putnam frozen | PSTW-PST | hit | -3.3333 | [-12.8571; 4.2857] | 1.0000 |
| ретроспектива / ProofNet -> Putnam frozen | PST_deltaX-PST | nll | 0.0487 | [-0.3045; 0.4231] | 1.0000 |
| ретроспектива / ProofNet -> Putnam frozen | PST_deltaX-PST | hit | -10.0000 | [-28.5714; 8.5714] | 1.0000 |
| ретроспектива / ProofNet -> Putnam frozen | PST_u-PST | nll | -0.3851 | [-0.9613; 0.1665] | NA |
| ретроспектива / ProofNet -> Putnam frozen | PST_u-PST | hit | -15.7143 | [-35.7143; 4.2857] | NA |
| ретроспектива / ProofNet -> Putnam frozen | MD_noNW-MD_noN | nll | -0.0229 | [-0.0755; 0.0268] | 1.0000 |
| ретроспектива / ProofNet -> Putnam frozen | MD_noNW-MD_noN | hit | -0.4762 | [-7.6190; 5.2381] | 1.0000 |
| ретроспектива / ProofNet -> Putnam frozen | MD_noN_deltaX-MD_noN | nll | 0.0354 | [-0.3142; 0.4021] | 1.0000 |
| ретроспектива / ProofNet -> Putnam frozen | MD_noN_deltaX-MD_noN | hit | -12.8571 | [-31.4286; 5.7143] | 1.0000 |
| ретроспектива / ProofNet -> Putnam frozen | MD_noN_u-MD_noN | nll | -0.3977 | [-0.9686; 0.1494] | NA |
| ретроспектива / ProofNet -> Putnam frozen | MD_noN_u-MD_noN | hit | -18.5714 | [-38.5714; 2.8571] | NA |
| streaming / ProofNet OOF | PSTW-PST | nll | 0.0032 | [-0.0065; 0.0122] | 1.0000 |
| streaming / ProofNet OOF | PSTW-PST | exact | 0.5639 | [-2.9449; 4.2607] | 1.0000 |
| streaming / ProofNet OOF | PST_deltaX-PST | nll | 0.0351 | [-0.0162; 0.0863] | 1.0000 |
| streaming / ProofNet OOF | PST_deltaX-PST | exact | 8.9599 | [2.8822; 15.1629] | 0.1288 |
| streaming / ProofNet OOF | PST_u-PST | nll | 0.0039 | [-0.0561; 0.0610] | NA |
| streaming / ProofNet OOF | PST_u-PST | exact | 15.0627 | [8.0827; 22.2431] | NA |
| streaming / ProofNet OOF | MD_noNW-MD_noN | nll | 0.0035 | [-0.0063; 0.0127] | 1.0000 |
| streaming / ProofNet OOF | MD_noNW-MD_noN | exact | 1.5038 | [-2.3183; 5.5138] | 1.0000 |
| streaming / ProofNet OOF | MD_noN_deltaX-MD_noN | nll | 0.0353 | [-0.0158; 0.0863] | 1.0000 |
| streaming / ProofNet OOF | MD_noN_deltaX-MD_noN | exact | 10.0877 | [3.8221; 16.6040] | 0.0528 |
| streaming / ProofNet OOF | MD_noN_u-MD_noN | nll | 0.0041 | [-0.0566; 0.0617] | NA |
| streaming / ProofNet OOF | MD_noN_u-MD_noN | exact | 15.0627 | [8.0827; 22.2431] | NA |
| streaming / Putnam OOF | PSTW-PST | nll | -0.0268 | [-0.0455; -0.0099] | 0.0864 |
| streaming / Putnam OOF | PSTW-PST | exact | -0.9524 | [-2.8571; 0.0000] | 1.0000 |
| streaming / Putnam OOF | PST_deltaX-PST | nll | -0.0592 | [-0.1414; 0.0097] | 1.0000 |
| streaming / Putnam OOF | PST_deltaX-PST | exact | 0.4762 | [-14.2857; 14.7619] | 1.0000 |
| streaming / Putnam OOF | PST_u-PST | nll | -0.1237 | [-0.2288; -0.0335] | NA |
| streaming / Putnam OOF | PST_u-PST | exact | -9.5238 | [-20.4762; 0.0000] | NA |
| streaming / Putnam OOF | MD_noNW-MD_noN | nll | -0.0262 | [-0.0449; -0.0094] | 0.1056 |
| streaming / Putnam OOF | MD_noNW-MD_noN | exact | 0.4762 | [-2.8571; 4.2857] | 1.0000 |
| streaming / Putnam OOF | MD_noN_deltaX-MD_noN | nll | -0.0554 | [-0.1384; 0.0136] | 1.0000 |
| streaming / Putnam OOF | MD_noN_deltaX-MD_noN | exact | 4.7619 | [-8.5714; 18.0952] | 1.0000 |
| streaming / Putnam OOF | MD_noN_u-MD_noN | nll | -0.1200 | [-0.2258; -0.0295] | NA |
| streaming / Putnam OOF | MD_noN_u-MD_noN | exact | -5.2381 | [-14.7619; 1.9048] | NA |
| streaming / ProofNet -> Putnam frozen | PSTW-PST | nll | -0.0026 | [-0.0158; 0.0095] | 1.0000 |
| streaming / ProofNet -> Putnam frozen | PSTW-PST | exact | 0.0000 | [0.0000; 0.0000] | 1.0000 |
| streaming / ProofNet -> Putnam frozen | PST_deltaX-PST | nll | -0.1018 | [-0.2029; -0.0119] | 0.7010 |
| streaming / ProofNet -> Putnam frozen | PST_deltaX-PST | exact | 3.8095 | [-8.5714; 17.1429] | 1.0000 |
| streaming / ProofNet -> Putnam frozen | PST_u-PST | nll | -0.1676 | [-0.2956; -0.0538] | NA |
| streaming / ProofNet -> Putnam frozen | PST_u-PST | exact | 1.4286 | [-10.0000; 12.8571] | NA |
| streaming / ProofNet -> Putnam frozen | MD_noNW-MD_noN | nll | -0.0025 | [-0.0155; 0.0096] | 1.0000 |
| streaming / ProofNet -> Putnam frozen | MD_noNW-MD_noN | exact | 0.0000 | [0.0000; 0.0000] | 1.0000 |
| streaming / ProofNet -> Putnam frozen | MD_noN_deltaX-MD_noN | nll | -0.1030 | [-0.2034; -0.0130] | 0.6939 |
| streaming / ProofNet -> Putnam frozen | MD_noN_deltaX-MD_noN | exact | 3.8095 | [-8.5714; 17.1429] | 1.0000 |
| streaming / ProofNet -> Putnam frozen | MD_noN_u-MD_noN | nll | -0.1690 | [-0.2983; -0.0544] | NA |
| streaming / ProofNet -> Putnam frozen | MD_noN_u-MD_noN | exact | 1.4286 | [-10.0000; 12.8571] | NA |

Входы и признаки прошли проверку независимости от длины тактики при переобучении preprocessing и при предсказании; streaming проверен на усечение и изменение будущего. Исторический PST воспроизведён по сохранённым коэффициентам с максимальным отклонением 6.66e-16.
