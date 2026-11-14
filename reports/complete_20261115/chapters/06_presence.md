# Наличие ошибки и прогноз отказа: DeepSeek и Goedel

Обучались только детекторы. Веса prover-моделей и исходные ответы сохранены. Все числа построены из метрик; эксперименты на ранее исследованных корпусах имеют exploratory статус.

Постановки: offline — ошибка в полном формальном доказательстве; present — ошибка уже содержится в доступном префиксе; future1/3/5 — отказ в следующие тактики при пока принятом префиксе; future_end — отказ до конца продолжения. Отказ Lean не отождествляется с самой ранней математической ошибкой.

Данные включают все доступные корректные попытки, а не только задачи со смешанными исходами. Группы задач разделены в nested5×3 CV. Отдельные refit на полном исходном корпусе дают frozen перенос на другой корпус и Putnam. Putnam без корректных попыток не даёт AUROC или оценки ложных тревог для полного доказательства.

Streaming — causal replay сохранённых состояний на завершённых тактиках. Предикторы не используют конечную длину, будущие шаги, место отказа или ответы Lean. Будущие ошибки предсказываются только до первого отказа; после него метка present поглощающая.

## Основные сравнения

| Модель | Обучение | Проверка | Задача | Метод | AUROC | AP | NLL | Brier | Recall при калибровке FPR10% | FPR по строкам |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| deepseek | ProofNet | ProofNet | offline | Constant | 0.4707 | 0.8342 | 0.4327 | 0.1315 | 0.0000 | 0.0000 |
| deepseek | ProofNet | ProofNet | offline | Length | 0.8152 | 0.9570 | 0.3433 | 0.1061 | 0.5145 | 0.0773 |
| deepseek | ProofNet | ProofNet | offline | Q | 0.6498 | 0.8854 | 0.4261 | 0.1274 | 0.2627 | 0.1346 |
| deepseek | ProofNet | ProofNet | offline | MaxW | 0.6534 | 0.9097 | 0.4147 | 0.1272 | 0.2708 | 0.0892 |
| deepseek | ProofNet | ProofNet | offline | B | 0.8449 | 0.9675 | 0.3223 | 0.1008 | 0.5264 | 0.0716 |
| deepseek | ProofNet | ProofNet | offline | BW | 0.8538 | 0.9689 | 0.3153 | 0.0989 | 0.4932 | 0.0745 |
| deepseek | ProofNet | ProofNet | offline | BH | 0.8445 | 0.9645 | 0.3364 | 0.0982 | 0.6206 | 0.1862 |
| deepseek | ProofNet | ProofNet | offline | BD | 0.8091 | 0.9524 | 0.3562 | 0.1061 | 0.5179 | 0.0937 |
| deepseek | ProofNet | ProofNet | offline | BHD | 0.8449 | 0.9607 | 0.3497 | 0.0983 | 0.6591 | 0.1461 |
| deepseek | ProofNet | miniF2F | offline | Constant | 0.5000 | 0.4797 | 1.0492 | 0.3826 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | offline | Length | 0.8170 | 0.8009 | 0.8932 | 0.3080 | 0.6606 | 0.1742 |
| deepseek | ProofNet | miniF2F | offline | Q | 0.5756 | 0.5704 | 0.9937 | 0.3581 | 0.1413 | 0.0723 |
| deepseek | ProofNet | miniF2F | offline | MaxW | 0.4600 | 0.5060 | 0.9369 | 0.3480 | 0.0767 | 0.0287 |
| deepseek | ProofNet | miniF2F | offline | B | 0.7934 | 0.7636 | 0.9022 | 0.3018 | 0.5612 | 0.1330 |
| deepseek | ProofNet | miniF2F | offline | BW | 0.8244 | 0.7896 | 0.7117 | 0.2342 | 0.5012 | 0.0965 |
| deepseek | ProofNet | miniF2F | offline | BH | 0.8953 | 0.8655 | 0.7246 | 0.2215 | 0.6782 | 0.1095 |
| deepseek | ProofNet | miniF2F | offline | BD | 0.8554 | 0.8359 | 0.8194 | 0.2709 | 0.5903 | 0.1136 |
| deepseek | ProofNet | miniF2F | offline | BHD | 0.8877 | 0.8651 | 0.8198 | 0.2476 | 0.6906 | 0.1457 |
| deepseek | ProofNet | Putnam | offline | Constant | — | — | 0.1691 | 0.0242 | 0.0000 | — |
| deepseek | ProofNet | Putnam | offline | Length | — | — | 0.0910 | 0.0141 | 0.7069 | — |
| deepseek | ProofNet | Putnam | offline | Q | — | — | 0.1726 | 0.0338 | 0.2227 | — |
| deepseek | ProofNet | Putnam | offline | MaxW | — | — | 0.1759 | 0.0282 | 0.2917 | — |
| deepseek | ProofNet | Putnam | offline | B | — | — | 0.0858 | 0.0170 | 0.6911 | — |
| deepseek | ProofNet | Putnam | offline | BW | — | — | 0.0879 | 0.0178 | 0.6997 | — |
| deepseek | ProofNet | Putnam | offline | BH | — | — | 0.0221 | 0.0016 | 0.8693 | — |
| deepseek | ProofNet | Putnam | offline | BD | — | — | 0.0442 | 0.0040 | 0.7931 | — |
| deepseek | ProofNet | Putnam | offline | BHD | — | — | 0.0160 | 0.0008 | 0.8736 | — |
| goedel | ProofNet | ProofNet | offline | Constant | 0.4821 | 0.8480 | 0.4178 | 0.1255 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | offline | Length | 0.8271 | 0.9650 | 0.3398 | 0.1040 | 0.4994 | 0.1287 |
| goedel | ProofNet | ProofNet | offline | Q | 0.6459 | 0.9175 | 0.4035 | 0.1231 | 0.2883 | 0.1259 |
| goedel | ProofNet | ProofNet | offline | MaxW | 0.5570 | 0.8731 | 0.4163 | 0.1250 | 0.0726 | 0.0551 |
| goedel | ProofNet | ProofNet | offline | B | 0.7985 | 0.9497 | 0.3614 | 0.1094 | 0.4627 | 0.0933 |
| goedel | ProofNet | ProofNet | offline | BW | 0.8134 | 0.9598 | 0.3469 | 0.1060 | 0.5109 | 0.0866 |
| goedel | ProofNet | ProofNet | offline | BH | 0.8535 | 0.9691 | 0.3246 | 0.0960 | 0.5733 | 0.0854 |
| goedel | ProofNet | ProofNet | offline | BD | 0.7989 | 0.9513 | 0.3539 | 0.0995 | 0.3067 | 0.0787 |
| goedel | ProofNet | ProofNet | offline | BHD | 0.8394 | 0.9646 | 0.3561 | 0.0997 | 0.5421 | 0.0787 |
| goedel | ProofNet | miniF2F | offline | Constant | 0.5000 | 0.4400 | 1.1434 | 0.4169 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | offline | Length | 0.7958 | 0.7150 | 1.0859 | 0.3681 | 0.6103 | 0.1721 |
| goedel | ProofNet | miniF2F | offline | Q | 0.6718 | 0.5870 | 1.0995 | 0.3951 | 0.2641 | 0.1264 |
| goedel | ProofNet | miniF2F | offline | MaxW | 0.8017 | 0.7325 | 1.0336 | 0.3862 | 0.0506 | 0.0037 |
| goedel | ProofNet | miniF2F | offline | B | 0.7795 | 0.7186 | 1.0465 | 0.3813 | 0.4022 | 0.0925 |
| goedel | ProofNet | miniF2F | offline | BW | 0.8055 | 0.7517 | 0.9534 | 0.3498 | 0.4672 | 0.1044 |
| goedel | ProofNet | miniF2F | offline | BH | 0.8383 | 0.7732 | 0.7886 | 0.2417 | 0.2410 | 0.0341 |
| goedel | ProofNet | miniF2F | offline | BD | 0.7963 | 0.7033 | 0.9975 | 0.2957 | 0.2714 | 0.0754 |
| goedel | ProofNet | miniF2F | offline | BHD | 0.8305 | 0.7648 | 0.8536 | 0.2496 | 0.2015 | 0.0310 |
| goedel | ProofNet | Putnam | offline | Constant | — | — | 0.1591 | 0.0216 | 0.0000 | — |
| goedel | ProofNet | Putnam | offline | Length | — | — | 0.0719 | 0.0067 | 0.6143 | — |
| goedel | ProofNet | Putnam | offline | Q | — | — | 0.1246 | 0.0151 | 0.3524 | — |
| goedel | ProofNet | Putnam | offline | MaxW | — | — | 0.1619 | 0.0224 | 0.1000 | — |
| goedel | ProofNet | Putnam | offline | B | — | — | 0.1025 | 0.0102 | 0.4143 | — |
| goedel | ProofNet | Putnam | offline | BW | — | — | 0.1006 | 0.0102 | 0.6190 | — |
| goedel | ProofNet | Putnam | offline | BH | — | — | 0.0133 | 0.0005 | 0.7667 | — |
| goedel | ProofNet | Putnam | offline | BD | — | — | 0.0297 | 0.0025 | 0.6048 | — |
| goedel | ProofNet | Putnam | offline | BHD | — | — | 0.0102 | 0.0004 | 0.7000 | — |
| deepseek | miniF2F | miniF2F | offline | Constant | 0.4848 | 0.4704 | 0.6925 | 0.2497 | 0.0000 | 0.0000 |
| deepseek | miniF2F | miniF2F | offline | Length | 0.8324 | 0.8074 | 0.5089 | 0.1663 | 0.5473 | 0.1002 |
| deepseek | miniF2F | miniF2F | offline | Q | 0.7459 | 0.7046 | 0.5972 | 0.2047 | 0.3446 | 0.0936 |
| deepseek | miniF2F | miniF2F | offline | MaxW | 0.7973 | 0.7047 | 0.5189 | 0.1736 | 0.3215 | 0.1257 |
| deepseek | miniF2F | miniF2F | offline | B | 0.8394 | 0.7940 | 0.4975 | 0.1605 | 0.4990 | 0.1013 |
| deepseek | miniF2F | miniF2F | offline | BW | 0.8642 | 0.8136 | 0.4743 | 0.1508 | 0.5672 | 0.0966 |
| deepseek | miniF2F | miniF2F | offline | BH | 0.9049 | 0.8798 | 0.4023 | 0.1201 | 0.6738 | 0.0975 |
| deepseek | miniF2F | miniF2F | offline | BD | 0.8851 | 0.8435 | 0.4321 | 0.1332 | 0.6477 | 0.1005 |
| deepseek | miniF2F | miniF2F | offline | BHD | 0.9010 | 0.8667 | 0.4206 | 0.1233 | 0.6957 | 0.1004 |
| deepseek | miniF2F | ProofNet | offline | Constant | 0.5000 | 0.8444 | 0.7220 | 0.2644 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | offline | Length | 0.8186 | 0.9583 | 0.6508 | 0.2293 | 0.4022 | 0.0430 |
| deepseek | miniF2F | ProofNet | offline | Q | 0.6062 | 0.8853 | 0.7350 | 0.2631 | 0.2497 | 0.2026 |
| deepseek | miniF2F | ProofNet | offline | MaxW | 0.4233 | 0.8145 | 0.5195 | 0.1661 | 0.2786 | 0.3653 |
| deepseek | miniF2F | ProofNet | offline | B | 0.7499 | 0.9419 | 0.6408 | 0.2178 | 0.3672 | 0.0573 |
| deepseek | miniF2F | ProofNet | offline | BW | 0.8006 | 0.9583 | 0.4664 | 0.1460 | 0.6915 | 0.2550 |
| deepseek | miniF2F | ProofNet | offline | BH | 0.8886 | 0.9791 | 0.3073 | 0.0994 | 0.7563 | 0.1265 |
| deepseek | miniF2F | ProofNet | offline | BD | 0.8113 | 0.9616 | 0.5089 | 0.1616 | 0.5948 | 0.0866 |
| deepseek | miniF2F | ProofNet | offline | BHD | 0.8631 | 0.9736 | 0.3653 | 0.1175 | 0.7426 | 0.1614 |
| deepseek | miniF2F | Putnam | offline | Constant | — | — | 0.7346 | 0.2707 | 0.0000 | — |
| deepseek | miniF2F | Putnam | offline | Length | — | — | 0.4710 | 0.1546 | 0.5920 | — |
| deepseek | miniF2F | Putnam | offline | Q | — | — | 0.5549 | 0.1852 | 0.3448 | — |
| deepseek | miniF2F | Putnam | offline | MaxW | — | — | 0.3105 | 0.0735 | 0.4195 | — |
| deepseek | miniF2F | Putnam | offline | B | — | — | 0.3650 | 0.1100 | 0.6006 | — |
| deepseek | miniF2F | Putnam | offline | BW | — | — | 0.3086 | 0.0756 | 0.8391 | — |
| deepseek | miniF2F | Putnam | offline | BH | — | — | 0.0579 | 0.0075 | 0.9626 | — |
| deepseek | miniF2F | Putnam | offline | BD | — | — | 0.1712 | 0.0351 | 0.8736 | — |
| deepseek | miniF2F | Putnam | offline | BHD | — | — | 0.0624 | 0.0094 | 0.9684 | — |
| goedel | miniF2F | miniF2F | offline | Constant | 0.4624 | 0.4191 | 0.6874 | 0.2471 | 0.0000 | 0.0000 |
| goedel | miniF2F | miniF2F | offline | Length | 0.8071 | 0.7395 | 0.5328 | 0.1771 | 0.4713 | 0.0967 |
| goedel | miniF2F | miniF2F | offline | Q | 0.6972 | 0.6266 | 0.6274 | 0.2185 | 0.2894 | 0.0851 |
| goedel | miniF2F | miniF2F | offline | MaxW | 0.7956 | 0.7043 | 0.5399 | 0.1812 | 0.4243 | 0.1074 |
| goedel | miniF2F | miniF2F | offline | B | 0.8591 | 0.8199 | 0.4664 | 0.1503 | 0.5737 | 0.0893 |
| goedel | miniF2F | miniF2F | offline | BW | 0.8747 | 0.8370 | 0.4405 | 0.1421 | 0.5824 | 0.0964 |
| goedel | miniF2F | miniF2F | offline | BH | 0.9224 | 0.8950 | 0.3513 | 0.1104 | 0.7278 | 0.0893 |
| goedel | miniF2F | miniF2F | offline | BD | 0.8850 | 0.8471 | 0.4270 | 0.1356 | 0.6310 | 0.0920 |
| goedel | miniF2F | miniF2F | offline | BHD | 0.9144 | 0.8884 | 0.3732 | 0.1181 | 0.6773 | 0.0811 |
| goedel | miniF2F | ProofNet | offline | Constant | 0.5000 | 0.8529 | 0.7855 | 0.2960 | 0.0000 | 0.0000 |
| goedel | miniF2F | ProofNet | offline | Length | 0.7939 | 0.9570 | 0.8865 | 0.2988 | 0.3471 | 0.0512 |
| goedel | miniF2F | ProofNet | offline | Q | 0.6555 | 0.9155 | 0.7410 | 0.2691 | 0.2424 | 0.0826 |
| goedel | miniF2F | ProofNet | offline | MaxW | 0.5720 | 0.8808 | 0.4625 | 0.1444 | 0.7686 | 0.7678 |
| goedel | miniF2F | ProofNet | offline | B | 0.8225 | 0.9626 | 0.8476 | 0.2762 | 0.3669 | 0.0472 |
| goedel | miniF2F | ProofNet | offline | BW | 0.8131 | 0.9611 | 0.5975 | 0.1965 | 0.5185 | 0.0826 |
| goedel | miniF2F | ProofNet | offline | BH | 0.8948 | 0.9790 | 0.3935 | 0.1230 | 0.7196 | 0.1473 |
| goedel | miniF2F | ProofNet | offline | BD | 0.8828 | 0.9780 | 0.4690 | 0.1491 | 0.6230 | 0.0433 |
| goedel | miniF2F | ProofNet | offline | BHD | 0.8913 | 0.9791 | 0.3765 | 0.1197 | 0.7654 | 0.1709 |
| goedel | miniF2F | Putnam | offline | Constant | — | — | 0.8210 | 0.3136 | 0.0000 | — |
| goedel | miniF2F | Putnam | offline | Length | — | — | 0.4706 | 0.1493 | 0.4857 | — |
| goedel | miniF2F | Putnam | offline | Q | — | — | 0.6112 | 0.2110 | 0.3381 | — |
| goedel | miniF2F | Putnam | offline | MaxW | — | — | 0.3119 | 0.0767 | 0.7905 | — |
| goedel | miniF2F | Putnam | offline | B | — | — | 0.3715 | 0.1103 | 0.6381 | — |
| goedel | miniF2F | Putnam | offline | BW | — | — | 0.2428 | 0.0581 | 0.7857 | — |
| goedel | miniF2F | Putnam | offline | BH | — | — | 0.0997 | 0.0145 | 0.9905 | — |
| goedel | miniF2F | Putnam | offline | BD | — | — | 0.2207 | 0.0490 | 0.8619 | — |
| goedel | miniF2F | Putnam | offline | BHD | — | — | 0.0987 | 0.0144 | 0.9905 | — |
| deepseek | ProofNet | ProofNet | present | Constant | 0.4906 | 0.6121 | 0.6654 | 0.2363 | 0.0000 | 0.0000 |
| deepseek | ProofNet | ProofNet | present | Length | 0.8152 | 0.8704 | 0.5072 | 0.1680 | 0.2571 | 0.0321 |
| deepseek | ProofNet | ProofNet | present | Q | 0.7644 | 0.8180 | 0.5388 | 0.1816 | 0.1661 | 0.0262 |
| deepseek | ProofNet | ProofNet | present | MaxW | 0.6810 | 0.7461 | 0.6256 | 0.2159 | 0.2243 | 0.0812 |
| deepseek | ProofNet | ProofNet | present | B | 0.8379 | 0.8846 | 0.4745 | 0.1566 | 0.3160 | 0.0295 |
| deepseek | ProofNet | ProofNet | present | BW | 0.8390 | 0.8821 | 0.4720 | 0.1553 | 0.3373 | 0.0373 |
| deepseek | ProofNet | ProofNet | present | BH | 0.8730 | 0.8994 | 0.4249 | 0.1358 | 0.2351 | 0.0166 |
| deepseek | ProofNet | ProofNet | present | BD | 0.8397 | 0.8649 | 0.4725 | 0.1536 | 0.1709 | 0.0262 |
| deepseek | ProofNet | ProofNet | present | BHD | 0.8704 | 0.8959 | 0.4295 | 0.1377 | 0.2461 | 0.0222 |
| deepseek | ProofNet | miniF2F | present | Constant | 0.5000 | 0.2706 | 0.8312 | 0.3176 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | present | Length | 0.8167 | 0.6467 | 0.7144 | 0.2486 | 0.3100 | 0.0346 |
| deepseek | ProofNet | miniF2F | present | Q | 0.7036 | 0.4721 | 0.7036 | 0.2540 | 0.1446 | 0.0301 |
| deepseek | ProofNet | miniF2F | present | MaxW | 0.3483 | 0.1990 | 0.9574 | 0.3582 | 0.0729 | 0.2871 |
| deepseek | ProofNet | miniF2F | present | B | 0.8079 | 0.6259 | 0.6429 | 0.2252 | 0.3241 | 0.0478 |
| deepseek | ProofNet | miniF2F | present | BW | 0.7138 | 0.5131 | 0.7979 | 0.2876 | 0.2860 | 0.0713 |
| deepseek | ProofNet | miniF2F | present | BH | 0.8479 | 0.6564 | 0.5880 | 0.2012 | 0.1553 | 0.0148 |
| deepseek | ProofNet | miniF2F | present | BD | 0.8330 | 0.6499 | 0.5203 | 0.1731 | 0.1363 | 0.0095 |
| deepseek | ProofNet | miniF2F | present | BHD | 0.8572 | 0.6879 | 0.5389 | 0.1838 | 0.1372 | 0.0071 |
| deepseek | ProofNet | Putnam | present | Constant | 0.5000 | 0.6289 | 0.6598 | 0.2335 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | present | Length | 0.8584 | 0.9137 | 0.4663 | 0.1546 | 0.3640 | 0.0214 |
| deepseek | ProofNet | Putnam | present | Q | 0.7812 | 0.8567 | 0.5212 | 0.1772 | 0.2218 | 0.0175 |
| deepseek | ProofNet | Putnam | present | MaxW | 0.7054 | 0.8020 | 0.6043 | 0.2085 | 0.2197 | 0.0410 |
| deepseek | ProofNet | Putnam | present | B | 0.8756 | 0.9265 | 0.4352 | 0.1432 | 0.4822 | 0.0317 |
| deepseek | ProofNet | Putnam | present | BW | 0.8765 | 0.9242 | 0.4297 | 0.1405 | 0.4657 | 0.0281 |
| deepseek | ProofNet | Putnam | present | BH | 0.9154 | 0.9505 | 0.3711 | 0.1183 | 0.2741 | 0.0000 |
| deepseek | ProofNet | Putnam | present | BD | 0.8978 | 0.9367 | 0.4022 | 0.1254 | 0.2410 | 0.0034 |
| deepseek | ProofNet | Putnam | present | BHD | 0.9191 | 0.9528 | 0.3669 | 0.1169 | 0.2708 | 0.0023 |
| goedel | ProofNet | ProofNet | present | Constant | 0.4525 | 0.6480 | 0.6341 | 0.2210 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | present | Length | 0.8216 | 0.9015 | 0.4865 | 0.1584 | 0.3115 | 0.0283 |
| goedel | ProofNet | ProofNet | present | Q | 0.7319 | 0.8409 | 0.5381 | 0.1821 | 0.1701 | 0.0293 |
| goedel | ProofNet | ProofNet | present | MaxW | 0.5924 | 0.7458 | 0.6191 | 0.2145 | 0.1296 | 0.0562 |
| goedel | ProofNet | ProofNet | present | B | 0.8328 | 0.9076 | 0.4595 | 0.1514 | 0.2948 | 0.0291 |
| goedel | ProofNet | ProofNet | present | BW | 0.8384 | 0.9063 | 0.4522 | 0.1480 | 0.3415 | 0.0239 |
| goedel | ProofNet | ProofNet | present | BH | 0.8669 | 0.9158 | 0.4129 | 0.1299 | 0.1934 | 0.0125 |
| goedel | ProofNet | ProofNet | present | BD | 0.8604 | 0.9178 | 0.4297 | 0.1383 | 0.1884 | 0.0116 |
| goedel | ProofNet | ProofNet | present | BHD | 0.8723 | 0.9217 | 0.4117 | 0.1309 | 0.2168 | 0.0137 |
| goedel | ProofNet | miniF2F | present | Constant | 0.5000 | 0.2517 | 0.9353 | 0.3655 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | present | Length | 0.7988 | 0.5619 | 0.8519 | 0.3067 | 0.3693 | 0.0706 |
| goedel | ProofNet | miniF2F | present | Q | 0.7367 | 0.4697 | 0.8384 | 0.3032 | 0.1671 | 0.0428 |
| goedel | ProofNet | miniF2F | present | MaxW | 0.7266 | 0.4590 | 0.5947 | 0.2122 | 0.0351 | 0.0046 |
| goedel | ProofNet | miniF2F | present | B | 0.7989 | 0.5644 | 0.7677 | 0.2717 | 0.2544 | 0.0392 |
| goedel | ProofNet | miniF2F | present | BW | 0.8336 | 0.6111 | 0.5131 | 0.1716 | 0.1522 | 0.0175 |
| goedel | ProofNet | miniF2F | present | BH | 0.8085 | 0.5852 | 0.5268 | 0.1788 | 0.0563 | 0.0031 |
| goedel | ProofNet | miniF2F | present | BD | 0.8262 | 0.6017 | 0.6294 | 0.2244 | 0.1228 | 0.0145 |
| goedel | ProofNet | miniF2F | present | BHD | 0.8217 | 0.6067 | 0.5025 | 0.1716 | 0.1317 | 0.0098 |
| goedel | ProofNet | Putnam | present | Constant | 0.5000 | 0.6145 | 0.6742 | 0.2403 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | present | Length | 0.7949 | 0.8477 | 0.5564 | 0.1863 | 0.3809 | 0.0973 |
| goedel | ProofNet | Putnam | present | Q | 0.7579 | 0.7870 | 0.5868 | 0.1953 | 0.1718 | 0.0693 |
| goedel | ProofNet | Putnam | present | MaxW | 0.6206 | 0.7254 | 0.6506 | 0.2296 | 0.0904 | 0.0242 |
| goedel | ProofNet | Putnam | present | B | 0.8110 | 0.8204 | 0.5327 | 0.1674 | 0.3537 | 0.1195 |
| goedel | ProofNet | Putnam | present | BW | 0.8211 | 0.8357 | 0.5087 | 0.1590 | 0.2897 | 0.0846 |
| goedel | ProofNet | Putnam | present | BH | 0.9033 | 0.9370 | 0.4091 | 0.1339 | 0.2114 | 0.0015 |
| goedel | ProofNet | Putnam | present | BD | 0.8220 | 0.8489 | 0.5079 | 0.1676 | 0.2439 | 0.0508 |
| goedel | ProofNet | Putnam | present | BHD | 0.9035 | 0.9397 | 0.4135 | 0.1367 | 0.4538 | 0.0166 |
| deepseek | miniF2F | miniF2F | present | Constant | 0.4818 | 0.2624 | 0.5841 | 0.1975 | 0.0000 | 0.0000 |
| deepseek | miniF2F | miniF2F | present | Length | 0.8254 | 0.6694 | 0.4366 | 0.1391 | 0.1501 | 0.0083 |
| deepseek | miniF2F | miniF2F | present | Q | 0.7500 | 0.5015 | 0.5065 | 0.1678 | 0.1277 | 0.0267 |
| deepseek | miniF2F | miniF2F | present | MaxW | 0.7598 | 0.4698 | 0.4880 | 0.1637 | 0.1638 | 0.0681 |
| deepseek | miniF2F | miniF2F | present | B | 0.8239 | 0.6624 | 0.4388 | 0.1402 | 0.1301 | 0.0081 |
| deepseek | miniF2F | miniF2F | present | BW | 0.8481 | 0.6746 | 0.4162 | 0.1336 | 0.1347 | 0.0099 |
| deepseek | miniF2F | miniF2F | present | BH | 0.9049 | 0.7681 | 0.3452 | 0.1075 | 0.1860 | 0.0111 |
| deepseek | miniF2F | miniF2F | present | BD | 0.8827 | 0.7067 | 0.3881 | 0.1190 | 0.0903 | 0.0093 |
| deepseek | miniF2F | miniF2F | present | BHD | 0.9026 | 0.7685 | 0.3475 | 0.1067 | 0.1860 | 0.0098 |
| deepseek | miniF2F | ProofNet | present | Constant | 0.5000 | 0.6174 | 0.9277 | 0.3565 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | present | Length | 0.8125 | 0.8650 | 0.7928 | 0.2808 | 0.1062 | 0.0079 |
| deepseek | miniF2F | ProofNet | present | Q | 0.7382 | 0.8164 | 0.8249 | 0.3019 | 0.0766 | 0.0034 |
| deepseek | miniF2F | ProofNet | present | MaxW | 0.5537 | 0.6451 | 0.7371 | 0.2637 | 0.5797 | 0.5069 |
| deepseek | miniF2F | ProofNet | present | B | 0.8200 | 0.8691 | 0.7644 | 0.2709 | 0.0740 | 0.0044 |
| deepseek | miniF2F | ProofNet | present | BW | 0.8075 | 0.8592 | 0.6311 | 0.2210 | 0.1299 | 0.0120 |
| deepseek | miniF2F | ProofNet | present | BH | 0.8590 | 0.9057 | 0.5152 | 0.1662 | 0.3725 | 0.0324 |
| deepseek | miniF2F | ProofNet | present | BD | 0.8215 | 0.8682 | 0.6633 | 0.2193 | 0.1027 | 0.0077 |
| deepseek | miniF2F | ProofNet | present | BHD | 0.8457 | 0.8963 | 0.6113 | 0.1855 | 0.3912 | 0.0344 |
| deepseek | miniF2F | Putnam | present | Constant | 0.5000 | 0.6289 | 0.9391 | 0.3618 | 0.0000 | 0.0000 |
| deepseek | miniF2F | Putnam | present | Length | 0.8620 | 0.9157 | 0.6174 | 0.2114 | 0.2075 | 0.0028 |
| deepseek | miniF2F | Putnam | present | Q | 0.7507 | 0.8307 | 0.7519 | 0.2749 | 0.1344 | 0.0133 |
| deepseek | miniF2F | Putnam | present | MaxW | 0.5462 | 0.6329 | 0.6914 | 0.2483 | 0.6209 | 0.5533 |
| deepseek | miniF2F | Putnam | present | B | 0.8691 | 0.9207 | 0.6009 | 0.2047 | 0.1505 | 0.0007 |
| deepseek | miniF2F | Putnam | present | BW | 0.8735 | 0.9207 | 0.5123 | 0.1694 | 0.2369 | 0.0130 |
| deepseek | miniF2F | Putnam | present | BH | 0.9142 | 0.9453 | 0.3615 | 0.1141 | 0.5028 | 0.0255 |
| deepseek | miniF2F | Putnam | present | BD | 0.8911 | 0.9273 | 0.4513 | 0.1442 | 0.2018 | 0.0058 |
| deepseek | miniF2F | Putnam | present | BHD | 0.9065 | 0.9417 | 0.3825 | 0.1202 | 0.5556 | 0.0438 |
| goedel | miniF2F | miniF2F | present | Constant | 0.4534 | 0.2332 | 0.5659 | 0.1890 | 0.0000 | 0.0000 |
| goedel | miniF2F | miniF2F | present | Length | 0.8039 | 0.5898 | 0.4451 | 0.1442 | 0.1019 | 0.0107 |
| goedel | miniF2F | miniF2F | present | Q | 0.7312 | 0.4396 | 0.5005 | 0.1666 | 0.0927 | 0.0271 |
| goedel | miniF2F | miniF2F | present | MaxW | 0.7831 | 0.5187 | 0.4661 | 0.1527 | 0.2705 | 0.0607 |
| goedel | miniF2F | miniF2F | present | B | 0.8098 | 0.5899 | 0.4413 | 0.1430 | 0.0875 | 0.0096 |
| goedel | miniF2F | miniF2F | present | BW | 0.8361 | 0.6329 | 0.4167 | 0.1349 | 0.1573 | 0.0134 |
| goedel | miniF2F | miniF2F | present | BH | 0.8860 | 0.7094 | 0.3611 | 0.1160 | 0.1551 | 0.0085 |
| goedel | miniF2F | miniF2F | present | BD | 0.8510 | 0.6395 | 0.4089 | 0.1304 | 0.0723 | 0.0044 |
| goedel | miniF2F | miniF2F | present | BHD | 0.8846 | 0.7221 | 0.3618 | 0.1146 | 0.1595 | 0.0091 |
| goedel | miniF2F | ProofNet | present | Constant | 0.5000 | 0.6726 | 1.0227 | 0.3973 | 0.0000 | 0.0000 |
| goedel | miniF2F | ProofNet | present | Length | 0.7955 | 0.8858 | 0.9789 | 0.3345 | 0.0796 | 0.0009 |
| goedel | miniF2F | ProofNet | present | Q | 0.7369 | 0.8467 | 0.9343 | 0.3422 | 0.0733 | 0.0031 |
| goedel | miniF2F | ProofNet | present | MaxW | 0.6200 | 0.7745 | 0.6759 | 0.2398 | 0.6583 | 0.5041 |
| goedel | miniF2F | ProofNet | present | B | 0.8100 | 0.8955 | 0.8689 | 0.2976 | 0.0809 | 0.0006 |
| goedel | miniF2F | ProofNet | present | BW | 0.8192 | 0.8993 | 0.6395 | 0.2232 | 0.2079 | 0.0106 |
| goedel | miniF2F | ProofNet | present | BH | 0.8796 | 0.9278 | 0.5702 | 0.1966 | 0.1347 | 0.0066 |
| goedel | miniF2F | ProofNet | present | BD | 0.8414 | 0.9011 | 0.6034 | 0.1994 | 0.1441 | 0.0165 |
| goedel | miniF2F | ProofNet | present | BHD | 0.8501 | 0.9158 | 0.6488 | 0.2131 | 0.1970 | 0.0097 |
| goedel | miniF2F | Putnam | present | Constant | 0.5000 | 0.6145 | 0.9594 | 0.3685 | 0.0000 | 0.0000 |
| goedel | miniF2F | Putnam | present | Length | 0.7503 | 0.7950 | 0.7771 | 0.2745 | 0.0373 | 0.0025 |
| goedel | miniF2F | Putnam | present | Q | 0.7334 | 0.7855 | 0.7855 | 0.2920 | 0.0498 | 0.0058 |
| goedel | miniF2F | Putnam | present | MaxW | 0.6320 | 0.7320 | 0.6798 | 0.2415 | 0.6549 | 0.4578 |
| goedel | miniF2F | Putnam | present | B | 0.7626 | 0.7844 | 0.6777 | 0.2406 | 0.0759 | 0.0204 |
| goedel | miniF2F | Putnam | present | BW | 0.7870 | 0.8294 | 0.5643 | 0.1936 | 0.2331 | 0.0540 |
| goedel | miniF2F | Putnam | present | BH | 0.8696 | 0.9133 | 0.4683 | 0.1511 | 0.2986 | 0.0074 |
| goedel | miniF2F | Putnam | present | BD | 0.8154 | 0.8617 | 0.5412 | 0.1820 | 0.1481 | 0.0188 |
| goedel | miniF2F | Putnam | present | BHD | 0.8737 | 0.9179 | 0.4637 | 0.1473 | 0.3975 | 0.0140 |
| deepseek | ProofNet | ProofNet | future1 | Constant | 0.4636 | 0.3064 | 0.6310 | 0.2195 | 0.0000 | 0.0000 |
| deepseek | ProofNet | ProofNet | future1 | Length | 0.6279 | 0.4057 | 0.6036 | 0.2078 | 0.4271 | 0.2184 |
| deepseek | ProofNet | ProofNet | future1 | Q | 0.6131 | 0.3990 | 0.6101 | 0.2104 | 0.0000 | 0.0003 |
| deepseek | ProofNet | ProofNet | future1 | MaxW | 0.6206 | 0.4033 | 0.6066 | 0.2089 | 0.4271 | 0.2184 |
| deepseek | ProofNet | ProofNet | future1 | B | 0.6242 | 0.4064 | 0.6056 | 0.2085 | 0.4271 | 0.2184 |
| deepseek | ProofNet | ProofNet | future1 | BW | 0.6170 | 0.4021 | 0.6073 | 0.2090 | 0.3133 | 0.1710 |
| deepseek | ProofNet | ProofNet | future1 | BH | 0.7150 | 0.5440 | 0.5710 | 0.1920 | 0.3713 | 0.1193 |
| deepseek | ProofNet | ProofNet | future1 | BD | 0.6477 | 0.4345 | 0.6077 | 0.2068 | 0.0516 | 0.0210 |
| deepseek | ProofNet | ProofNet | future1 | BHD | 0.7123 | 0.5405 | 0.5880 | 0.1946 | 0.3954 | 0.1143 |
| deepseek | ProofNet | miniF2F | future1 | Constant | 0.5000 | 0.1111 | 0.4733 | 0.1441 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future1 | Length | 0.5736 | 0.1398 | 0.4432 | 0.1349 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future1 | Q | 0.5719 | 0.1390 | 0.4468 | 0.1359 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future1 | MaxW | 0.5119 | 0.1268 | 0.4996 | 0.1575 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future1 | B | 0.5728 | 0.1402 | 0.4480 | 0.1360 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future1 | BW | 0.5467 | 0.1340 | 0.4561 | 0.1395 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future1 | BH | 0.6931 | 0.2037 | 0.3419 | 0.1004 | 0.0361 | 0.0175 |
| deepseek | ProofNet | miniF2F | future1 | BD | 0.6130 | 0.1597 | 0.4014 | 0.1226 | 0.0189 | 0.0065 |
| deepseek | ProofNet | miniF2F | future1 | BHD | 0.6634 | 0.1937 | 0.3447 | 0.1006 | 0.0304 | 0.0159 |
| deepseek | ProofNet | Putnam | future1 | Constant | 0.5000 | 0.2524 | 0.5772 | 0.1938 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | future1 | Length | 0.6063 | 0.3302 | 0.5561 | 0.1857 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | future1 | Q | 0.5735 | 0.3152 | 0.5639 | 0.1887 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | future1 | MaxW | 0.5667 | 0.3143 | 0.5623 | 0.1878 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | future1 | B | 0.5834 | 0.3195 | 0.5621 | 0.1878 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | future1 | BW | 0.5838 | 0.3196 | 0.5621 | 0.1879 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | future1 | BH | 0.6796 | 0.4326 | 0.5263 | 0.1741 | 0.1266 | 0.0325 |
| deepseek | ProofNet | Putnam | future1 | BD | 0.6068 | 0.3456 | 0.5705 | 0.1884 | 0.0228 | 0.0035 |
| deepseek | ProofNet | Putnam | future1 | BHD | 0.6618 | 0.4043 | 0.5461 | 0.1787 | 0.1139 | 0.0312 |
| goedel | ProofNet | ProofNet | future1 | Constant | 0.4360 | 0.3590 | 0.6730 | 0.2399 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | future1 | Length | 0.6601 | 0.5043 | 0.6190 | 0.2147 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | future1 | Q | 0.6125 | 0.4753 | 0.6529 | 0.2277 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | future1 | MaxW | 0.6399 | 0.4962 | 0.6233 | 0.2162 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | future1 | B | 0.6439 | 0.4987 | 0.6269 | 0.2176 | 0.1389 | 0.0609 |
| goedel | ProofNet | ProofNet | future1 | BW | 0.6432 | 0.4979 | 0.6238 | 0.2164 | 0.1389 | 0.0609 |
| goedel | ProofNet | ProofNet | future1 | BH | 0.7411 | 0.6368 | 0.6011 | 0.2015 | 0.3535 | 0.0799 |
| goedel | ProofNet | ProofNet | future1 | BD | 0.6486 | 0.4920 | 0.6767 | 0.2255 | 0.0163 | 0.0255 |
| goedel | ProofNet | ProofNet | future1 | BHD | 0.7394 | 0.6329 | 0.6355 | 0.2058 | 0.3597 | 0.0977 |
| goedel | ProofNet | miniF2F | future1 | Constant | 0.5000 | 0.0949 | 0.5389 | 0.1740 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future1 | Length | 0.5496 | 0.1185 | 0.4657 | 0.1463 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future1 | Q | 0.5802 | 0.1277 | 0.4816 | 0.1495 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future1 | MaxW | 0.6266 | 0.1357 | 0.4432 | 0.1383 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future1 | B | 0.5684 | 0.1226 | 0.4696 | 0.1461 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future1 | BW | 0.5552 | 0.1197 | 0.4819 | 0.1514 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future1 | BH | 0.6951 | 0.1996 | 0.3086 | 0.0881 | 0.0413 | 0.0015 |
| goedel | ProofNet | miniF2F | future1 | BD | 0.6168 | 0.1352 | 0.4086 | 0.1281 | 0.0036 | 0.0013 |
| goedel | ProofNet | miniF2F | future1 | BHD | 0.6639 | 0.1778 | 0.3123 | 0.0882 | 0.0090 | 0.0017 |
| goedel | ProofNet | Putnam | future1 | Constant | 0.5000 | 0.2618 | 0.6123 | 0.2101 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future1 | Length | 0.6536 | 0.3799 | 0.5577 | 0.1875 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future1 | Q | 0.5735 | 0.3399 | 0.5856 | 0.1982 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future1 | MaxW | 0.5944 | 0.3554 | 0.5686 | 0.1912 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future1 | B | 0.6250 | 0.3644 | 0.5686 | 0.1911 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future1 | BW | 0.6269 | 0.3661 | 0.5658 | 0.1900 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future1 | BH | 0.6487 | 0.4446 | 0.5732 | 0.1903 | 0.1091 | 0.0605 |
| goedel | ProofNet | Putnam | future1 | BD | 0.6297 | 0.3854 | 0.5883 | 0.1934 | 0.0182 | 0.0000 |
| goedel | ProofNet | Putnam | future1 | BHD | 0.6613 | 0.4525 | 0.5824 | 0.1873 | 0.1273 | 0.0538 |
| deepseek | miniF2F | miniF2F | future1 | Constant | 0.4352 | 0.0980 | 0.3505 | 0.0991 | 0.0000 | 0.0000 |
| deepseek | miniF2F | miniF2F | future1 | Length | 0.5829 | 0.1324 | 0.3455 | 0.0984 | 0.0881 | 0.0758 |
| deepseek | miniF2F | miniF2F | future1 | Q | 0.5313 | 0.1186 | 0.3510 | 0.0992 | 0.0993 | 0.1306 |
| deepseek | miniF2F | miniF2F | future1 | MaxW | 0.5468 | 0.1193 | 0.3488 | 0.0991 | 0.0544 | 0.0835 |
| deepseek | miniF2F | miniF2F | future1 | B | 0.5898 | 0.1375 | 0.3451 | 0.0983 | 0.0710 | 0.0686 |
| deepseek | miniF2F | miniF2F | future1 | BW | 0.6230 | 0.1563 | 0.3383 | 0.0971 | 0.1461 | 0.0959 |
| deepseek | miniF2F | miniF2F | future1 | BH | 0.7785 | 0.2741 | 0.3034 | 0.0903 | 0.4125 | 0.1105 |
| deepseek | miniF2F | miniF2F | future1 | BD | 0.6802 | 0.2097 | 0.3268 | 0.0947 | 0.1733 | 0.0493 |
| deepseek | miniF2F | miniF2F | future1 | BHD | 0.7612 | 0.2657 | 0.3121 | 0.0918 | 0.3943 | 0.1138 |
| deepseek | miniF2F | ProofNet | future1 | Constant | 0.5000 | 0.3241 | 0.7917 | 0.2644 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | future1 | Length | 0.5958 | 0.3970 | 0.7537 | 0.2535 | 0.0410 | 0.0370 |
| deepseek | miniF2F | ProofNet | future1 | Q | 0.6263 | 0.4229 | 0.7708 | 0.2597 | 0.5424 | 0.3253 |
| deepseek | miniF2F | ProofNet | future1 | MaxW | 0.6322 | 0.4266 | 0.7361 | 0.2515 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | future1 | B | 0.6139 | 0.4101 | 0.7536 | 0.2544 | 0.0252 | 0.0275 |
| deepseek | miniF2F | ProofNet | future1 | BW | 0.5460 | 0.3505 | 0.7220 | 0.2479 | 0.1454 | 0.1651 |
| deepseek | miniF2F | ProofNet | future1 | BH | 0.6245 | 0.4202 | 0.7481 | 0.2468 | 0.2984 | 0.2229 |
| deepseek | miniF2F | ProofNet | future1 | BD | 0.6249 | 0.4296 | 0.7661 | 0.2509 | 0.1183 | 0.0844 |
| deepseek | miniF2F | ProofNet | future1 | BHD | 0.6319 | 0.4283 | 0.7810 | 0.2493 | 0.3546 | 0.2357 |
| deepseek | miniF2F | Putnam | future1 | Constant | 0.5000 | 0.2524 | 0.6426 | 0.2086 | 0.0000 | 0.0000 |
| deepseek | miniF2F | Putnam | future1 | Length | 0.5710 | 0.3054 | 0.6443 | 0.2065 | 0.0171 | 0.0386 |
| deepseek | miniF2F | Putnam | future1 | Q | 0.5574 | 0.3083 | 0.6381 | 0.2074 | 0.3758 | 0.2476 |
| deepseek | miniF2F | Putnam | future1 | MaxW | 0.5873 | 0.3237 | 0.6131 | 0.2018 | 0.0000 | 0.0000 |
| deepseek | miniF2F | Putnam | future1 | B | 0.5681 | 0.3092 | 0.6358 | 0.2056 | 0.0000 | 0.0307 |
| deepseek | miniF2F | Putnam | future1 | BW | 0.5644 | 0.2936 | 0.6081 | 0.2004 | 0.0987 | 0.0983 |
| deepseek | miniF2F | Putnam | future1 | BH | 0.6486 | 0.4125 | 0.5662 | 0.1844 | 0.5941 | 0.3936 |
| deepseek | miniF2F | Putnam | future1 | BD | 0.6025 | 0.3089 | 0.6155 | 0.2015 | 0.1874 | 0.1411 |
| deepseek | miniF2F | Putnam | future1 | BHD | 0.6410 | 0.3824 | 0.5779 | 0.1873 | 0.5782 | 0.3993 |
| goedel | miniF2F | miniF2F | future1 | Constant | 0.3939 | 0.0784 | 0.3181 | 0.0866 | 0.0000 | 0.0000 |
| goedel | miniF2F | miniF2F | future1 | Length | 0.6210 | 0.1424 | 0.3100 | 0.0848 | 0.1077 | 0.0418 |
| goedel | miniF2F | miniF2F | future1 | Q | 0.5866 | 0.1149 | 0.3134 | 0.0862 | 0.0357 | 0.0261 |
| goedel | miniF2F | miniF2F | future1 | MaxW | 0.5430 | 0.1057 | 0.3123 | 0.0859 | 0.1423 | 0.1009 |
| goedel | miniF2F | miniF2F | future1 | B | 0.6461 | 0.1567 | 0.3022 | 0.0840 | 0.1185 | 0.0429 |
| goedel | miniF2F | miniF2F | future1 | BW | 0.6763 | 0.1800 | 0.2941 | 0.0826 | 0.1351 | 0.0522 |
| goedel | miniF2F | miniF2F | future1 | BH | 0.8232 | 0.3121 | 0.2556 | 0.0752 | 0.5121 | 0.1159 |
| goedel | miniF2F | miniF2F | future1 | BD | 0.7009 | 0.2088 | 0.2887 | 0.0811 | 0.1642 | 0.0464 |
| goedel | miniF2F | miniF2F | future1 | BHD | 0.8014 | 0.3088 | 0.2633 | 0.0761 | 0.5241 | 0.1117 |
| goedel | miniF2F | ProofNet | future1 | Constant | 0.5000 | 0.3917 | 0.9830 | 0.3263 | 0.0000 | 0.0000 |
| goedel | miniF2F | ProofNet | future1 | Length | 0.5948 | 0.4666 | 0.9164 | 0.3073 | 0.0500 | 0.1129 |
| goedel | miniF2F | ProofNet | future1 | Q | 0.6024 | 0.4771 | 0.9006 | 0.3072 | 0.0649 | 0.0996 |
| goedel | miniF2F | ProofNet | future1 | MaxW | 0.6772 | 0.5358 | 0.8764 | 0.3036 | 0.6315 | 0.3010 |
| goedel | miniF2F | ProofNet | future1 | B | 0.5956 | 0.4685 | 0.9243 | 0.3080 | 0.0660 | 0.1164 |
| goedel | miniF2F | ProofNet | future1 | BW | 0.5563 | 0.4393 | 0.8996 | 0.3058 | 0.1121 | 0.2057 |
| goedel | miniF2F | ProofNet | future1 | BH | 0.6859 | 0.5468 | 0.7504 | 0.2597 | 0.6891 | 0.3883 |
| goedel | miniF2F | ProofNet | future1 | BD | 0.6345 | 0.4884 | 0.9072 | 0.3075 | 0.1100 | 0.1327 |
| goedel | miniF2F | ProofNet | future1 | BHD | 0.6805 | 0.5359 | 0.7739 | 0.2632 | 0.7195 | 0.4118 |
| goedel | miniF2F | Putnam | future1 | Constant | 0.5000 | 0.2618 | 0.6901 | 0.2211 | 0.0000 | 0.0000 |
| goedel | miniF2F | Putnam | future1 | Length | 0.5668 | 0.3266 | 0.6995 | 0.2183 | 0.0182 | 0.0712 |
| goedel | miniF2F | Putnam | future1 | Q | 0.5357 | 0.2941 | 0.6808 | 0.2179 | 0.0618 | 0.1244 |
| goedel | miniF2F | Putnam | future1 | MaxW | 0.5936 | 0.3564 | 0.6504 | 0.2123 | 0.4365 | 0.1999 |
| goedel | miniF2F | Putnam | future1 | B | 0.5406 | 0.3161 | 0.7123 | 0.2200 | 0.0618 | 0.1155 |
| goedel | miniF2F | Putnam | future1 | BW | 0.4966 | 0.2833 | 0.7105 | 0.2240 | 0.0740 | 0.1842 |
| goedel | miniF2F | Putnam | future1 | BH | 0.6693 | 0.5226 | 0.5440 | 0.1768 | 0.5700 | 0.3839 |
| goedel | miniF2F | Putnam | future1 | BD | 0.6109 | 0.3558 | 0.6599 | 0.2112 | 0.1392 | 0.1374 |
| goedel | miniF2F | Putnam | future1 | BHD | 0.6723 | 0.5063 | 0.5552 | 0.1781 | 0.5892 | 0.3769 |
| deepseek | ProofNet | ProofNet | future3 | Constant | 0.4779 | 0.5601 | 0.6825 | 0.2447 | 0.0000 | 0.0000 |
| deepseek | ProofNet | ProofNet | future3 | Length | 0.6219 | 0.6599 | 0.6566 | 0.2321 | 0.2495 | 0.1494 |
| deepseek | ProofNet | ProofNet | future3 | Q | 0.6140 | 0.6546 | 0.6601 | 0.2338 | 0.2524 | 0.1528 |
| deepseek | ProofNet | ProofNet | future3 | MaxW | 0.6002 | 0.6505 | 0.6621 | 0.2349 | 0.2495 | 0.1494 |
| deepseek | ProofNet | ProofNet | future3 | B | 0.6168 | 0.6571 | 0.6596 | 0.2336 | 0.2495 | 0.1494 |
| deepseek | ProofNet | ProofNet | future3 | BW | 0.6137 | 0.6560 | 0.6589 | 0.2333 | 0.2495 | 0.1494 |
| deepseek | ProofNet | ProofNet | future3 | BH | 0.6864 | 0.7205 | 0.6392 | 0.2222 | 0.2080 | 0.0801 |
| deepseek | ProofNet | ProofNet | future3 | BD | 0.6418 | 0.6752 | 0.6573 | 0.2312 | 0.0727 | 0.0394 |
| deepseek | ProofNet | ProofNet | future3 | BHD | 0.6841 | 0.7175 | 0.6515 | 0.2260 | 0.2218 | 0.0854 |
| deepseek | ProofNet | miniF2F | future3 | Constant | 0.5000 | 0.2405 | 0.7824 | 0.2943 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future3 | Length | 0.5479 | 0.2731 | 0.7466 | 0.2746 | 0.2894 | 0.2092 |
| deepseek | ProofNet | miniF2F | future3 | Q | 0.5459 | 0.2752 | 0.7384 | 0.2706 | 0.2953 | 0.2112 |
| deepseek | ProofNet | miniF2F | future3 | MaxW | 0.4814 | 0.2499 | 0.8204 | 0.3111 | 0.2894 | 0.2092 |
| deepseek | ProofNet | miniF2F | future3 | B | 0.5400 | 0.2715 | 0.7431 | 0.2729 | 0.2894 | 0.2092 |
| deepseek | ProofNet | miniF2F | future3 | BW | 0.5248 | 0.2651 | 0.7585 | 0.2807 | 0.2894 | 0.2092 |
| deepseek | ProofNet | miniF2F | future3 | BH | 0.7042 | 0.3947 | 0.5771 | 0.1980 | 0.0331 | 0.0089 |
| deepseek | ProofNet | miniF2F | future3 | BD | 0.6297 | 0.3215 | 0.6408 | 0.2282 | 0.0246 | 0.0048 |
| deepseek | ProofNet | miniF2F | future3 | BHD | 0.6882 | 0.3882 | 0.5637 | 0.1928 | 0.0350 | 0.0115 |
| deepseek | ProofNet | Putnam | future3 | Constant | 0.5000 | 0.5372 | 0.6932 | 0.2500 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | future3 | Length | 0.6049 | 0.6222 | 0.6756 | 0.2412 | 0.3093 | 0.1862 |
| deepseek | ProofNet | Putnam | future3 | Q | 0.5689 | 0.5990 | 0.6920 | 0.2491 | 0.3115 | 0.2047 |
| deepseek | ProofNet | Putnam | future3 | MaxW | 0.5746 | 0.6048 | 0.6813 | 0.2441 | 0.3093 | 0.1862 |
| deepseek | ProofNet | Putnam | future3 | B | 0.5942 | 0.6145 | 0.6779 | 0.2424 | 0.3093 | 0.1862 |
| deepseek | ProofNet | Putnam | future3 | BW | 0.5958 | 0.6146 | 0.6776 | 0.2423 | 0.3093 | 0.1862 |
| deepseek | ProofNet | Putnam | future3 | BH | 0.5771 | 0.6169 | 0.7030 | 0.2529 | 0.0794 | 0.0358 |
| deepseek | ProofNet | Putnam | future3 | BD | 0.5745 | 0.6095 | 0.7011 | 0.2520 | 0.0522 | 0.0378 |
| deepseek | ProofNet | Putnam | future3 | BHD | 0.5711 | 0.6191 | 0.7196 | 0.2583 | 0.0863 | 0.0427 |
| goedel | ProofNet | ProofNet | future3 | Constant | 0.4216 | 0.5845 | 0.6652 | 0.2360 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | future3 | Length | 0.6366 | 0.7150 | 0.6280 | 0.2188 | 0.0911 | 0.0705 |
| goedel | ProofNet | ProofNet | future3 | Q | 0.6208 | 0.7027 | 0.6332 | 0.2211 | 0.0009 | 0.0000 |
| goedel | ProofNet | ProofNet | future3 | MaxW | 0.6355 | 0.7140 | 0.6307 | 0.2200 | 0.0911 | 0.0705 |
| goedel | ProofNet | ProofNet | future3 | B | 0.6369 | 0.7177 | 0.6257 | 0.2178 | 0.0911 | 0.0705 |
| goedel | ProofNet | ProofNet | future3 | BW | 0.6374 | 0.7119 | 0.6269 | 0.2182 | 0.0920 | 0.0740 |
| goedel | ProofNet | ProofNet | future3 | BH | 0.7315 | 0.7879 | 0.5869 | 0.1995 | 0.2837 | 0.0742 |
| goedel | ProofNet | ProofNet | future3 | BD | 0.6541 | 0.7120 | 0.6338 | 0.2178 | 0.0632 | 0.0507 |
| goedel | ProofNet | ProofNet | future3 | BHD | 0.7216 | 0.7829 | 0.6094 | 0.2073 | 0.2360 | 0.0702 |
| goedel | ProofNet | miniF2F | future3 | Constant | 0.5000 | 0.2070 | 0.8824 | 0.3423 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future3 | Length | 0.5576 | 0.2422 | 0.7830 | 0.2899 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future3 | Q | 0.5918 | 0.2616 | 0.7802 | 0.2896 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future3 | MaxW | 0.5834 | 0.2550 | 0.8425 | 0.3188 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future3 | B | 0.5653 | 0.2463 | 0.7942 | 0.2963 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future3 | BW | 0.5441 | 0.2389 | 0.8391 | 0.3175 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future3 | BH | 0.6866 | 0.3292 | 0.5123 | 0.1711 | 0.0186 | 0.0069 |
| goedel | ProofNet | miniF2F | future3 | BD | 0.6370 | 0.2816 | 0.6340 | 0.2247 | 0.0157 | 0.0038 |
| goedel | ProofNet | miniF2F | future3 | BHD | 0.6736 | 0.3248 | 0.5155 | 0.1701 | 0.0162 | 0.0054 |
| goedel | ProofNet | Putnam | future3 | Constant | 0.5000 | 0.5450 | 0.7039 | 0.2550 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future3 | Length | 0.6045 | 0.6122 | 0.6759 | 0.2405 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future3 | Q | 0.5953 | 0.6128 | 0.6856 | 0.2455 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future3 | MaxW | 0.5460 | 0.5906 | 0.7030 | 0.2536 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future3 | B | 0.6099 | 0.6150 | 0.6824 | 0.2439 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future3 | BW | 0.6031 | 0.6120 | 0.6835 | 0.2443 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future3 | BH | 0.5897 | 0.6522 | 0.7312 | 0.2605 | 0.0629 | 0.0240 |
| goedel | ProofNet | Putnam | future3 | BD | 0.5218 | 0.5716 | 0.7850 | 0.2802 | 0.0105 | 0.0561 |
| goedel | ProofNet | Putnam | future3 | BHD | 0.5803 | 0.6430 | 0.7758 | 0.2718 | 0.0717 | 0.0347 |
| deepseek | miniF2F | miniF2F | future3 | Constant | 0.4546 | 0.2220 | 0.5530 | 0.1832 | 0.0000 | 0.0000 |
| deepseek | miniF2F | miniF2F | future3 | Length | 0.6013 | 0.3138 | 0.5398 | 0.1784 | 0.1371 | 0.0600 |
| deepseek | miniF2F | miniF2F | future3 | Q | 0.5663 | 0.2680 | 0.5491 | 0.1817 | 0.1369 | 0.1001 |
| deepseek | miniF2F | miniF2F | future3 | MaxW | 0.5743 | 0.2645 | 0.5386 | 0.1788 | 0.0818 | 0.0852 |
| deepseek | miniF2F | miniF2F | future3 | B | 0.5967 | 0.2999 | 0.5414 | 0.1792 | 0.1298 | 0.0696 |
| deepseek | miniF2F | miniF2F | future3 | BW | 0.6470 | 0.3442 | 0.5226 | 0.1732 | 0.1855 | 0.0817 |
| deepseek | miniF2F | miniF2F | future3 | BH | 0.8122 | 0.5733 | 0.4312 | 0.1403 | 0.4532 | 0.1080 |
| deepseek | miniF2F | miniF2F | future3 | BD | 0.7215 | 0.4511 | 0.4826 | 0.1598 | 0.2576 | 0.0739 |
| deepseek | miniF2F | miniF2F | future3 | BHD | 0.8048 | 0.5621 | 0.4368 | 0.1423 | 0.4367 | 0.1088 |
| deepseek | miniF2F | ProofNet | future3 | Constant | 0.5000 | 0.5746 | 0.9358 | 0.3560 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | future3 | Length | 0.5610 | 0.6200 | 0.9086 | 0.3399 | 0.0667 | 0.0924 |
| deepseek | miniF2F | ProofNet | future3 | Q | 0.6057 | 0.6620 | 0.9038 | 0.3417 | 0.4845 | 0.2888 |
| deepseek | miniF2F | ProofNet | future3 | MaxW | 0.6111 | 0.6647 | 0.8619 | 0.3270 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | future3 | B | 0.5720 | 0.6315 | 0.9025 | 0.3400 | 0.0412 | 0.0486 |
| deepseek | miniF2F | ProofNet | future3 | BW | 0.5148 | 0.5917 | 0.8377 | 0.3146 | 0.2449 | 0.2886 |
| deepseek | miniF2F | ProofNet | future3 | BH | 0.6352 | 0.6679 | 0.8368 | 0.3019 | 0.3864 | 0.2495 |
| deepseek | miniF2F | ProofNet | future3 | BD | 0.6090 | 0.6460 | 0.8770 | 0.3234 | 0.2109 | 0.1760 |
| deepseek | miniF2F | ProofNet | future3 | BHD | 0.6304 | 0.6625 | 0.8692 | 0.3077 | 0.3784 | 0.2471 |
| deepseek | miniF2F | Putnam | future3 | Constant | 0.5000 | 0.5372 | 0.8928 | 0.3366 | 0.0000 | 0.0000 |
| deepseek | miniF2F | Putnam | future3 | Length | 0.5450 | 0.5712 | 0.9310 | 0.3426 | 0.0476 | 0.0667 |
| deepseek | miniF2F | Putnam | future3 | Q | 0.5331 | 0.5773 | 0.8920 | 0.3342 | 0.3218 | 0.2520 |
| deepseek | miniF2F | Putnam | future3 | MaxW | 0.5869 | 0.6138 | 0.8320 | 0.3128 | 0.0000 | 0.0000 |
| deepseek | miniF2F | Putnam | future3 | B | 0.5167 | 0.5558 | 0.9070 | 0.3380 | 0.0174 | 0.0450 |
| deepseek | miniF2F | Putnam | future3 | BW | 0.5256 | 0.5510 | 0.8433 | 0.3137 | 0.1892 | 0.1953 |
| deepseek | miniF2F | Putnam | future3 | BH | 0.6114 | 0.6343 | 0.7621 | 0.2694 | 0.5722 | 0.4069 |
| deepseek | miniF2F | Putnam | future3 | BD | 0.5633 | 0.5955 | 0.8306 | 0.3039 | 0.3046 | 0.2545 |
| deepseek | miniF2F | Putnam | future3 | BHD | 0.6103 | 0.6349 | 0.7816 | 0.2707 | 0.5973 | 0.4141 |
| goedel | miniF2F | miniF2F | future3 | Constant | 0.4108 | 0.1790 | 0.5154 | 0.1659 | 0.0000 | 0.0000 |
| goedel | miniF2F | miniF2F | future3 | Length | 0.6171 | 0.2991 | 0.4970 | 0.1597 | 0.1732 | 0.0580 |
| goedel | miniF2F | miniF2F | future3 | Q | 0.5476 | 0.2276 | 0.5141 | 0.1659 | 0.0339 | 0.0265 |
| goedel | miniF2F | miniF2F | future3 | MaxW | 0.5393 | 0.2156 | 0.5102 | 0.1648 | 0.1068 | 0.1043 |
| goedel | miniF2F | miniF2F | future3 | B | 0.6255 | 0.2979 | 0.4951 | 0.1594 | 0.1891 | 0.0634 |
| goedel | miniF2F | miniF2F | future3 | BW | 0.6536 | 0.3011 | 0.4856 | 0.1579 | 0.1737 | 0.0754 |
| goedel | miniF2F | miniF2F | future3 | BH | 0.8026 | 0.4685 | 0.4125 | 0.1353 | 0.3844 | 0.1029 |
| goedel | miniF2F | miniF2F | future3 | BD | 0.7149 | 0.3956 | 0.4530 | 0.1470 | 0.2401 | 0.0654 |
| goedel | miniF2F | miniF2F | future3 | BHD | 0.8001 | 0.4732 | 0.4150 | 0.1364 | 0.3891 | 0.1030 |
| goedel | miniF2F | ProofNet | future3 | Constant | 0.5000 | 0.6291 | 1.0769 | 0.4115 | 0.0000 | 0.0000 |
| goedel | miniF2F | ProofNet | future3 | Length | 0.5785 | 0.6769 | 1.0282 | 0.3814 | 0.1214 | 0.1567 |
| goedel | miniF2F | ProofNet | future3 | Q | 0.6089 | 0.7068 | 0.9902 | 0.3766 | 0.0916 | 0.0914 |
| goedel | miniF2F | ProofNet | future3 | MaxW | 0.6521 | 0.7351 | 0.9603 | 0.3692 | 0.5256 | 0.2690 |
| goedel | miniF2F | ProofNet | future3 | B | 0.5886 | 0.6809 | 1.0286 | 0.3796 | 0.1404 | 0.1562 |
| goedel | miniF2F | ProofNet | future3 | BW | 0.5517 | 0.6602 | 0.9353 | 0.3528 | 0.2354 | 0.2913 |
| goedel | miniF2F | ProofNet | future3 | BH | 0.6949 | 0.7708 | 0.7045 | 0.2502 | 0.7159 | 0.4056 |
| goedel | miniF2F | ProofNet | future3 | BD | 0.6429 | 0.7200 | 0.9069 | 0.3439 | 0.2742 | 0.2291 |
| goedel | miniF2F | ProofNet | future3 | BHD | 0.6949 | 0.7703 | 0.7164 | 0.2534 | 0.7114 | 0.3968 |
| goedel | miniF2F | Putnam | future3 | Constant | 0.5000 | 0.5450 | 0.9640 | 0.3622 | 0.0000 | 0.0000 |
| goedel | miniF2F | Putnam | future3 | Length | 0.5150 | 0.5658 | 1.0076 | 0.3657 | 0.0709 | 0.1021 |
| goedel | miniF2F | Putnam | future3 | Q | 0.5727 | 0.6285 | 0.9245 | 0.3430 | 0.1732 | 0.0804 |
| goedel | miniF2F | Putnam | future3 | MaxW | 0.5483 | 0.5917 | 0.8996 | 0.3389 | 0.3044 | 0.2109 |
| goedel | miniF2F | Putnam | future3 | B | 0.5383 | 0.5924 | 1.0079 | 0.3591 | 0.1510 | 0.0962 |
| goedel | miniF2F | Putnam | future3 | BW | 0.5034 | 0.5637 | 0.9203 | 0.3377 | 0.2243 | 0.2484 |
| goedel | miniF2F | Putnam | future3 | BH | 0.5827 | 0.6446 | 0.7511 | 0.2726 | 0.5734 | 0.4539 |
| goedel | miniF2F | Putnam | future3 | BD | 0.5668 | 0.6126 | 0.8514 | 0.3141 | 0.3495 | 0.3154 |
| goedel | miniF2F | Putnam | future3 | BHD | 0.5865 | 0.6502 | 0.7624 | 0.2760 | 0.5736 | 0.4247 |
| deepseek | ProofNet | ProofNet | future5 | Constant | 0.4822 | 0.6788 | 0.6204 | 0.2145 | 0.0000 | 0.0000 |
| deepseek | ProofNet | ProofNet | future5 | Length | 0.6126 | 0.7594 | 0.6008 | 0.2063 | 0.1738 | 0.0961 |
| deepseek | ProofNet | ProofNet | future5 | Q | 0.6069 | 0.7561 | 0.6036 | 0.2074 | 0.0000 | 0.0003 |
| deepseek | ProofNet | ProofNet | future5 | MaxW | 0.5791 | 0.7468 | 0.6038 | 0.2077 | 0.1738 | 0.0961 |
| deepseek | ProofNet | ProofNet | future5 | B | 0.6128 | 0.7612 | 0.6010 | 0.2063 | 0.1738 | 0.0961 |
| deepseek | ProofNet | ProofNet | future5 | BW | 0.6071 | 0.7572 | 0.6019 | 0.2068 | 0.1738 | 0.0961 |
| deepseek | ProofNet | ProofNet | future5 | BH | 0.6913 | 0.7978 | 0.5745 | 0.1926 | 0.1951 | 0.0854 |
| deepseek | ProofNet | ProofNet | future5 | BD | 0.6563 | 0.7762 | 0.5850 | 0.1983 | 0.0895 | 0.0526 |
| deepseek | ProofNet | ProofNet | future5 | BHD | 0.6893 | 0.7977 | 0.5830 | 0.1954 | 0.1832 | 0.0947 |
| deepseek | ProofNet | miniF2F | future5 | Constant | 0.5000 | 0.3140 | 0.9177 | 0.3558 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future5 | Length | 0.5257 | 0.3367 | 0.8850 | 0.3365 | 0.2696 | 0.2097 |
| deepseek | ProofNet | miniF2F | future5 | Q | 0.5348 | 0.3441 | 0.8796 | 0.3349 | 0.2696 | 0.2097 |
| deepseek | ProofNet | miniF2F | future5 | MaxW | 0.4557 | 0.3101 | 0.9383 | 0.3617 | 0.2696 | 0.2097 |
| deepseek | ProofNet | miniF2F | future5 | B | 0.5225 | 0.3383 | 0.8862 | 0.3385 | 0.2696 | 0.2097 |
| deepseek | ProofNet | miniF2F | future5 | BW | 0.5085 | 0.3317 | 0.8898 | 0.3396 | 0.2696 | 0.2097 |
| deepseek | ProofNet | miniF2F | future5 | BH | 0.7385 | 0.4907 | 0.6576 | 0.2321 | 0.0244 | 0.0093 |
| deepseek | ProofNet | miniF2F | future5 | BD | 0.6485 | 0.3974 | 0.7388 | 0.2694 | 0.0272 | 0.0112 |
| deepseek | ProofNet | miniF2F | future5 | BHD | 0.7224 | 0.4820 | 0.6449 | 0.2282 | 0.0254 | 0.0090 |
| deepseek | ProofNet | Putnam | future5 | Constant | 0.5000 | 0.6891 | 0.6198 | 0.2142 | 0.0000 | 0.0000 |
| deepseek | ProofNet | Putnam | future5 | Length | 0.5951 | 0.7573 | 0.6101 | 0.2104 | 0.2921 | 0.1642 |
| deepseek | ProofNet | Putnam | future5 | Q | 0.5755 | 0.7435 | 0.6139 | 0.2119 | 0.2935 | 0.1812 |
| deepseek | ProofNet | Putnam | future5 | MaxW | 0.5652 | 0.7431 | 0.6112 | 0.2108 | 0.2921 | 0.1642 |
| deepseek | ProofNet | Putnam | future5 | B | 0.6008 | 0.7559 | 0.6089 | 0.2097 | 0.2921 | 0.1642 |
| deepseek | ProofNet | Putnam | future5 | BW | 0.5979 | 0.7563 | 0.6090 | 0.2098 | 0.2921 | 0.1642 |
| deepseek | ProofNet | Putnam | future5 | BH | 0.5528 | 0.7369 | 0.6513 | 0.2277 | 0.0685 | 0.0568 |
| deepseek | ProofNet | Putnam | future5 | BD | 0.5790 | 0.7546 | 0.6295 | 0.2194 | 0.0701 | 0.0358 |
| deepseek | ProofNet | Putnam | future5 | BHD | 0.5601 | 0.7414 | 0.6563 | 0.2293 | 0.0749 | 0.0560 |
| goedel | ProofNet | ProofNet | future5 | Constant | 0.4243 | 0.6896 | 0.5897 | 0.1997 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | future5 | Length | 0.6323 | 0.7969 | 0.5586 | 0.1872 | 0.0848 | 0.0694 |
| goedel | ProofNet | ProofNet | future5 | Q | 0.6300 | 0.7923 | 0.5584 | 0.1867 | 0.0008 | 0.0047 |
| goedel | ProofNet | ProofNet | future5 | MaxW | 0.6331 | 0.8004 | 0.5586 | 0.1877 | 0.0848 | 0.0694 |
| goedel | ProofNet | ProofNet | future5 | B | 0.6329 | 0.7960 | 0.5568 | 0.1863 | 0.0922 | 0.0619 |
| goedel | ProofNet | ProofNet | future5 | BW | 0.6437 | 0.8002 | 0.5536 | 0.1852 | 0.0856 | 0.0716 |
| goedel | ProofNet | ProofNet | future5 | BH | 0.7575 | 0.8660 | 0.4997 | 0.1622 | 0.2985 | 0.0852 |
| goedel | ProofNet | ProofNet | future5 | BD | 0.6904 | 0.8137 | 0.5289 | 0.1724 | 0.0979 | 0.0588 |
| goedel | ProofNet | ProofNet | future5 | BHD | 0.7520 | 0.8563 | 0.5134 | 0.1660 | 0.2627 | 0.0863 |
| goedel | ProofNet | miniF2F | future5 | Constant | 0.5000 | 0.2710 | 1.0374 | 0.4073 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future5 | Length | 0.5507 | 0.3070 | 0.9289 | 0.3513 | 0.2661 | 0.1860 |
| goedel | ProofNet | miniF2F | future5 | Q | 0.5714 | 0.3230 | 0.9273 | 0.3532 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future5 | MaxW | 0.5856 | 0.3238 | 0.9742 | 0.3723 | 0.2661 | 0.1860 |
| goedel | ProofNet | miniF2F | future5 | B | 0.5582 | 0.3134 | 0.9422 | 0.3604 | 0.2661 | 0.1860 |
| goedel | ProofNet | miniF2F | future5 | BW | 0.5343 | 0.3021 | 0.9837 | 0.3776 | 0.2661 | 0.1860 |
| goedel | ProofNet | miniF2F | future5 | BH | 0.7246 | 0.4611 | 0.5828 | 0.2016 | 0.0412 | 0.0081 |
| goedel | ProofNet | miniF2F | future5 | BD | 0.6373 | 0.3517 | 0.7368 | 0.2647 | 0.0088 | 0.0047 |
| goedel | ProofNet | miniF2F | future5 | BHD | 0.7155 | 0.4724 | 0.5735 | 0.1966 | 0.0323 | 0.0066 |
| goedel | ProofNet | Putnam | future5 | Constant | 0.5000 | 0.7154 | 0.5977 | 0.2038 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future5 | Length | 0.6591 | 0.7925 | 0.5686 | 0.1901 | 0.2938 | 0.1815 |
| goedel | ProofNet | Putnam | future5 | Q | 0.6408 | 0.7898 | 0.5807 | 0.1966 | 0.0000 | 0.0000 |
| goedel | ProofNet | Putnam | future5 | MaxW | 0.5862 | 0.7718 | 0.5950 | 0.2030 | 0.2938 | 0.1815 |
| goedel | ProofNet | Putnam | future5 | B | 0.6640 | 0.7949 | 0.5775 | 0.1948 | 0.2938 | 0.1815 |
| goedel | ProofNet | Putnam | future5 | BW | 0.6589 | 0.7937 | 0.5773 | 0.1947 | 0.2938 | 0.1815 |
| goedel | ProofNet | Putnam | future5 | BH | 0.6081 | 0.7774 | 0.6444 | 0.2186 | 0.1985 | 0.1300 |
| goedel | ProofNet | Putnam | future5 | BD | 0.5804 | 0.7700 | 0.6396 | 0.2197 | 0.0579 | 0.0364 |
| goedel | ProofNet | Putnam | future5 | BHD | 0.6048 | 0.7732 | 0.6662 | 0.2251 | 0.2211 | 0.1409 |
| deepseek | miniF2F | miniF2F | future5 | Constant | 0.4708 | 0.2997 | 0.6229 | 0.2157 | 0.0000 | 0.0000 |
| deepseek | miniF2F | miniF2F | future5 | Length | 0.5952 | 0.3866 | 0.6106 | 0.2106 | 0.1318 | 0.0595 |
| deepseek | miniF2F | miniF2F | future5 | Q | 0.5713 | 0.3550 | 0.6174 | 0.2132 | 0.0431 | 0.0310 |
| deepseek | miniF2F | miniF2F | future5 | MaxW | 0.5872 | 0.3611 | 0.6008 | 0.2077 | 0.0469 | 0.0295 |
| deepseek | miniF2F | miniF2F | future5 | B | 0.5922 | 0.3900 | 0.6071 | 0.2094 | 0.1295 | 0.0709 |
| deepseek | miniF2F | miniF2F | future5 | BW | 0.6516 | 0.4206 | 0.5845 | 0.2014 | 0.2013 | 0.1046 |
| deepseek | miniF2F | miniF2F | future5 | BH | 0.8237 | 0.6547 | 0.4678 | 0.1555 | 0.4778 | 0.1071 |
| deepseek | miniF2F | miniF2F | future5 | BD | 0.7423 | 0.5544 | 0.5258 | 0.1796 | 0.3149 | 0.0957 |
| deepseek | miniF2F | miniF2F | future5 | BHD | 0.8232 | 0.6563 | 0.4678 | 0.1557 | 0.4580 | 0.1064 |
| deepseek | miniF2F | ProofNet | future5 | Constant | 0.5000 | 0.6887 | 0.9151 | 0.3548 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | future5 | Length | 0.5419 | 0.7160 | 0.8959 | 0.3413 | 0.0886 | 0.1296 |
| deepseek | miniF2F | ProofNet | future5 | Q | 0.5909 | 0.7505 | 0.8963 | 0.3445 | 0.0167 | 0.0223 |
| deepseek | miniF2F | ProofNet | future5 | MaxW | 0.4705 | 0.6867 | 0.8275 | 0.3153 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | future5 | B | 0.5534 | 0.7197 | 0.8963 | 0.3435 | 0.0603 | 0.0935 |
| deepseek | miniF2F | ProofNet | future5 | BW | 0.4730 | 0.6762 | 0.8026 | 0.3022 | 0.2761 | 0.3505 |
| deepseek | miniF2F | ProofNet | future5 | BH | 0.6714 | 0.7874 | 0.7601 | 0.2725 | 0.4117 | 0.2359 |
| deepseek | miniF2F | ProofNet | future5 | BD | 0.6295 | 0.7573 | 0.8211 | 0.3070 | 0.2946 | 0.2252 |
| deepseek | miniF2F | ProofNet | future5 | BHD | 0.6657 | 0.7827 | 0.7833 | 0.2785 | 0.4036 | 0.2450 |
| deepseek | miniF2F | Putnam | future5 | Constant | 0.5000 | 0.6891 | 0.9154 | 0.3549 | 0.0000 | 0.0000 |
| deepseek | miniF2F | Putnam | future5 | Length | 0.5261 | 0.7048 | 0.9621 | 0.3654 | 0.0685 | 0.1109 |
| deepseek | miniF2F | Putnam | future5 | Q | 0.4931 | 0.7032 | 0.9272 | 0.3577 | 0.0179 | 0.0347 |
| deepseek | miniF2F | Putnam | future5 | MaxW | 0.4638 | 0.6832 | 0.8237 | 0.3136 | 0.0000 | 0.0000 |
| deepseek | miniF2F | Putnam | future5 | B | 0.4719 | 0.6752 | 0.9469 | 0.3637 | 0.0471 | 0.1045 |
| deepseek | miniF2F | Putnam | future5 | BW | 0.4710 | 0.6699 | 0.8351 | 0.3155 | 0.2335 | 0.2926 |
| deepseek | miniF2F | Putnam | future5 | BH | 0.5905 | 0.7524 | 0.7149 | 0.2553 | 0.5587 | 0.4501 |
| deepseek | miniF2F | Putnam | future5 | BD | 0.5275 | 0.7213 | 0.7952 | 0.2967 | 0.4181 | 0.4233 |
| deepseek | miniF2F | Putnam | future5 | BHD | 0.5949 | 0.7526 | 0.7163 | 0.2532 | 0.5656 | 0.4646 |
| goedel | miniF2F | miniF2F | future5 | Constant | 0.4357 | 0.2442 | 0.5874 | 0.1988 | 0.0000 | 0.0000 |
| goedel | miniF2F | miniF2F | future5 | Length | 0.6178 | 0.3894 | 0.5666 | 0.1901 | 0.1941 | 0.0726 |
| goedel | miniF2F | miniF2F | future5 | Q | 0.5434 | 0.2928 | 0.5870 | 0.1989 | 0.0421 | 0.0298 |
| goedel | miniF2F | miniF2F | future5 | MaxW | 0.5569 | 0.2885 | 0.5784 | 0.1959 | 0.0168 | 0.0277 |
| goedel | miniF2F | miniF2F | future5 | B | 0.6150 | 0.3580 | 0.5674 | 0.1914 | 0.1682 | 0.0775 |
| goedel | miniF2F | miniF2F | future5 | BW | 0.6613 | 0.3887 | 0.5484 | 0.1857 | 0.2072 | 0.0887 |
| goedel | miniF2F | miniF2F | future5 | BH | 0.8284 | 0.5882 | 0.4414 | 0.1483 | 0.4062 | 0.1060 |
| goedel | miniF2F | miniF2F | future5 | BD | 0.7381 | 0.4985 | 0.5018 | 0.1691 | 0.3003 | 0.0791 |
| goedel | miniF2F | miniF2F | future5 | BHD | 0.8270 | 0.5863 | 0.4435 | 0.1498 | 0.3964 | 0.1081 |
| goedel | miniF2F | ProofNet | future5 | Constant | 0.5000 | 0.7290 | 1.0375 | 0.4073 | 0.0000 | 0.0000 |
| goedel | miniF2F | ProofNet | future5 | Length | 0.5767 | 0.7647 | 0.9931 | 0.3758 | 0.1300 | 0.1684 |
| goedel | miniF2F | ProofNet | future5 | Q | 0.6272 | 0.8058 | 0.9609 | 0.3732 | 0.0649 | 0.0408 |
| goedel | miniF2F | ProofNet | future5 | MaxW | 0.6375 | 0.8121 | 0.9086 | 0.3529 | 0.0000 | 0.0000 |
| goedel | miniF2F | ProofNet | future5 | B | 0.5838 | 0.7712 | 0.9741 | 0.3689 | 0.1607 | 0.1890 |
| goedel | miniF2F | ProofNet | future5 | BW | 0.5362 | 0.7495 | 0.8713 | 0.3310 | 0.2780 | 0.3297 |
| goedel | miniF2F | ProofNet | future5 | BH | 0.7231 | 0.8593 | 0.6485 | 0.2264 | 0.6318 | 0.3237 |
| goedel | miniF2F | ProofNet | future5 | BD | 0.6764 | 0.8168 | 0.8518 | 0.3242 | 0.3056 | 0.2089 |
| goedel | miniF2F | ProofNet | future5 | BHD | 0.7273 | 0.8612 | 0.6664 | 0.2318 | 0.6315 | 0.3029 |
| goedel | miniF2F | Putnam | future5 | Constant | 0.5000 | 0.7154 | 1.0240 | 0.4011 | 0.0000 | 0.0000 |
| goedel | miniF2F | Putnam | future5 | Length | 0.5434 | 0.7484 | 1.0641 | 0.4024 | 0.0984 | 0.1068 |
| goedel | miniF2F | Putnam | future5 | Q | 0.5316 | 0.7530 | 0.9911 | 0.3845 | 0.0829 | 0.0607 |
| goedel | miniF2F | Putnam | future5 | MaxW | 0.5388 | 0.7553 | 0.9176 | 0.3561 | 0.0000 | 0.0000 |
| goedel | miniF2F | Putnam | future5 | B | 0.5272 | 0.7497 | 1.0603 | 0.3989 | 0.1333 | 0.1038 |
| goedel | miniF2F | Putnam | future5 | BW | 0.5106 | 0.7391 | 0.9044 | 0.3421 | 0.2611 | 0.2662 |
| goedel | miniF2F | Putnam | future5 | BH | 0.5716 | 0.7689 | 0.7422 | 0.2684 | 0.5342 | 0.4184 |
| goedel | miniF2F | Putnam | future5 | BD | 0.5817 | 0.7740 | 0.8639 | 0.3267 | 0.3832 | 0.3251 |
| goedel | miniF2F | Putnam | future5 | BHD | 0.5698 | 0.7760 | 0.7681 | 0.2770 | 0.5323 | 0.4176 |
| deepseek | ProofNet | ProofNet | future_end | Constant | 0.4707 | 0.8342 | 0.4327 | 0.1315 | 0.0000 | 0.0000 |
| deepseek | ProofNet | ProofNet | future_end | Length | 0.5655 | 0.8756 | 0.4257 | 0.1296 | 0.1600 | 0.1067 |
| deepseek | ProofNet | ProofNet | future_end | Q | 0.5383 | 0.8669 | 0.4323 | 0.1316 | 0.1651 | 0.0794 |
| deepseek | ProofNet | ProofNet | future_end | MaxW | 0.5552 | 0.8696 | 0.4270 | 0.1301 | 0.1584 | 0.0825 |
| deepseek | ProofNet | ProofNet | future_end | B | 0.5601 | 0.8735 | 0.4299 | 0.1310 | 0.0937 | 0.0533 |
| deepseek | ProofNet | ProofNet | future_end | BW | 0.5292 | 0.8640 | 0.4288 | 0.1307 | 0.1584 | 0.0825 |
| deepseek | ProofNet | ProofNet | future_end | BH | 0.8726 | 0.9695 | 0.2942 | 0.0889 | 0.5517 | 0.0871 |
| deepseek | ProofNet | ProofNet | future_end | BD | 0.7899 | 0.9417 | 0.3505 | 0.1008 | 0.2944 | 0.0540 |
| deepseek | ProofNet | ProofNet | future_end | BHD | 0.8783 | 0.9703 | 0.2875 | 0.0868 | 0.5758 | 0.0850 |
| deepseek | ProofNet | miniF2F | future_end | Constant | 0.5000 | 0.4797 | 1.0492 | 0.3826 | 0.0000 | 0.0000 |
| deepseek | ProofNet | miniF2F | future_end | Length | 0.5220 | 0.4888 | 1.0315 | 0.3726 | 0.2324 | 0.2283 |
| deepseek | ProofNet | miniF2F | future_end | Q | 0.5286 | 0.4963 | 1.0227 | 0.3726 | 0.2316 | 0.2256 |
| deepseek | ProofNet | miniF2F | future_end | MaxW | 0.3868 | 0.4327 | 1.0694 | 0.3862 | 0.2316 | 0.2256 |
| deepseek | ProofNet | miniF2F | future_end | B | 0.5319 | 0.4972 | 1.0157 | 0.3657 | 0.0133 | 0.0099 |
| deepseek | ProofNet | miniF2F | future_end | BW | 0.4328 | 0.4532 | 1.0416 | 0.3785 | 0.2316 | 0.2256 |
| deepseek | ProofNet | miniF2F | future_end | BH | 0.8698 | 0.8296 | 0.7869 | 0.2546 | 0.6900 | 0.1418 |
| deepseek | ProofNet | miniF2F | future_end | BD | 0.7571 | 0.6981 | 0.8266 | 0.2818 | 0.3257 | 0.0816 |
| deepseek | ProofNet | miniF2F | future_end | BHD | 0.8728 | 0.8329 | 0.7831 | 0.2503 | 0.7083 | 0.1490 |
| deepseek | ProofNet | Putnam | future_end | Constant | — | — | 0.1691 | 0.0242 | 0.0000 | — |
| deepseek | ProofNet | Putnam | future_end | Length | — | — | 0.1853 | 0.0311 | 0.2636 | — |
| deepseek | ProofNet | Putnam | future_end | Q | — | — | 0.1807 | 0.0284 | 0.2586 | — |
| deepseek | ProofNet | Putnam | future_end | MaxW | — | — | 0.1794 | 0.0278 | 0.2524 | — |
| deepseek | ProofNet | Putnam | future_end | B | — | — | 0.1900 | 0.0344 | 0.0250 | — |
| deepseek | ProofNet | Putnam | future_end | BW | — | — | 0.1801 | 0.0281 | 0.2524 | — |
| deepseek | ProofNet | Putnam | future_end | BH | — | — | 0.0525 | 0.0068 | 0.8119 | — |
| deepseek | ProofNet | Putnam | future_end | BD | — | — | 0.1115 | 0.0148 | 0.4066 | — |
| deepseek | ProofNet | Putnam | future_end | BHD | — | — | 0.0458 | 0.0055 | 0.8403 | — |
| goedel | ProofNet | ProofNet | future_end | Constant | 0.4821 | 0.8480 | 0.4178 | 0.1255 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | future_end | Length | 0.5502 | 0.8796 | 0.4129 | 0.1245 | 0.1853 | 0.1143 |
| goedel | ProofNet | ProofNet | future_end | Q | 0.5621 | 0.8820 | 0.4147 | 0.1250 | 0.0000 | 0.0000 |
| goedel | ProofNet | ProofNet | future_end | MaxW | 0.6050 | 0.8876 | 0.4074 | 0.1230 | 0.1853 | 0.1143 |
| goedel | ProofNet | ProofNet | future_end | B | 0.5432 | 0.8754 | 0.4156 | 0.1254 | 0.1853 | 0.1143 |
| goedel | ProofNet | ProofNet | future_end | BW | 0.5566 | 0.8779 | 0.4122 | 0.1243 | 0.1853 | 0.1143 |
| goedel | ProofNet | ProofNet | future_end | BH | 0.8853 | 0.9739 | 0.2630 | 0.0773 | 0.5947 | 0.0958 |
| goedel | ProofNet | ProofNet | future_end | BD | 0.7644 | 0.9360 | 0.3305 | 0.0937 | 0.2650 | 0.0627 |
| goedel | ProofNet | ProofNet | future_end | BHD | 0.8893 | 0.9748 | 0.2589 | 0.0761 | 0.6152 | 0.0876 |
| goedel | ProofNet | miniF2F | future_end | Constant | 0.5000 | 0.4400 | 1.1434 | 0.4169 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future_end | Length | 0.4917 | 0.4444 | 1.1079 | 0.4058 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future_end | Q | 0.5207 | 0.4583 | 1.1106 | 0.4074 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future_end | MaxW | 0.3955 | 0.3995 | 1.1997 | 0.4286 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future_end | B | 0.5270 | 0.4584 | 1.1055 | 0.4047 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future_end | BW | 0.4076 | 0.4087 | 1.1458 | 0.4155 | 0.0000 | 0.0000 |
| goedel | ProofNet | miniF2F | future_end | BH | 0.8623 | 0.8088 | 0.6756 | 0.2178 | 0.4426 | 0.0688 |
| goedel | ProofNet | miniF2F | future_end | BD | 0.7085 | 0.6022 | 0.8347 | 0.2875 | 0.1230 | 0.0345 |
| goedel | ProofNet | miniF2F | future_end | BHD | 0.8667 | 0.8123 | 0.6494 | 0.2107 | 0.3964 | 0.0530 |
| goedel | ProofNet | Putnam | future_end | Constant | — | — | 0.1591 | 0.0216 | 0.0000 | — |
| goedel | ProofNet | Putnam | future_end | Length | — | — | 0.1723 | 0.0258 | 0.0000 | — |
| goedel | ProofNet | Putnam | future_end | Q | — | — | 0.1701 | 0.0249 | 0.0000 | — |
| goedel | ProofNet | Putnam | future_end | MaxW | — | — | 0.1752 | 0.0271 | 0.0000 | — |
| goedel | ProofNet | Putnam | future_end | B | — | — | 0.1734 | 0.0263 | 0.0000 | — |
| goedel | ProofNet | Putnam | future_end | BW | — | — | 0.1727 | 0.0262 | 0.0000 | — |
| goedel | ProofNet | Putnam | future_end | BH | — | — | 0.0669 | 0.0101 | 0.6475 | — |
| goedel | ProofNet | Putnam | future_end | BD | — | — | 0.1178 | 0.0165 | 0.2791 | — |
| goedel | ProofNet | Putnam | future_end | BHD | — | — | 0.0605 | 0.0088 | 0.6630 | — |
| deepseek | miniF2F | miniF2F | future_end | Constant | 0.4848 | 0.4704 | 0.6925 | 0.2497 | 0.0000 | 0.0000 |
| deepseek | miniF2F | miniF2F | future_end | Length | 0.6058 | 0.5555 | 0.6726 | 0.2402 | 0.1510 | 0.0829 |
| deepseek | miniF2F | miniF2F | future_end | Q | 0.5827 | 0.5392 | 0.6803 | 0.2435 | 0.1345 | 0.0850 |
| deepseek | miniF2F | miniF2F | future_end | MaxW | 0.6530 | 0.5718 | 0.6453 | 0.2281 | 0.2253 | 0.1170 |
| deepseek | miniF2F | miniF2F | future_end | B | 0.6103 | 0.5629 | 0.6664 | 0.2375 | 0.1535 | 0.0895 |
| deepseek | miniF2F | miniF2F | future_end | BW | 0.7165 | 0.6580 | 0.6064 | 0.2108 | 0.2709 | 0.0994 |
| deepseek | miniF2F | miniF2F | future_end | BH | 0.8936 | 0.8451 | 0.4042 | 0.1271 | 0.6656 | 0.1184 |
| deepseek | miniF2F | miniF2F | future_end | BD | 0.8491 | 0.8173 | 0.4729 | 0.1552 | 0.5696 | 0.1091 |
| deepseek | miniF2F | miniF2F | future_end | BHD | 0.8965 | 0.8549 | 0.3974 | 0.1253 | 0.6724 | 0.1178 |
| deepseek | miniF2F | ProofNet | future_end | Constant | 0.5000 | 0.8444 | 0.7220 | 0.2644 | 0.0000 | 0.0000 |
| deepseek | miniF2F | ProofNet | future_end | Length | 0.5105 | 0.8482 | 0.7329 | 0.2670 | 0.0921 | 0.0948 |
| deepseek | miniF2F | ProofNet | future_end | Q | 0.4994 | 0.8400 | 0.7347 | 0.2698 | 0.0493 | 0.0905 |
| deepseek | miniF2F | ProofNet | future_end | MaxW | 0.4310 | 0.8259 | 0.6222 | 0.2154 | 0.3444 | 0.4175 |
| deepseek | miniF2F | ProofNet | future_end | B | 0.4930 | 0.8352 | 0.7362 | 0.2696 | 0.0682 | 0.0954 |
| deepseek | miniF2F | ProofNet | future_end | BW | 0.4499 | 0.8288 | 0.6057 | 0.2080 | 0.3743 | 0.4649 |
| deepseek | miniF2F | ProofNet | future_end | BH | 0.8659 | 0.9699 | 0.3811 | 0.1172 | 0.6522 | 0.1248 |
| deepseek | miniF2F | ProofNet | future_end | BD | 0.7654 | 0.9396 | 0.5040 | 0.1694 | 0.4977 | 0.1814 |
| deepseek | miniF2F | ProofNet | future_end | BHD | 0.8722 | 0.9715 | 0.3653 | 0.1119 | 0.6872 | 0.1373 |
| deepseek | miniF2F | Putnam | future_end | Constant | — | — | 0.7346 | 0.2707 | 0.0000 | — |
| deepseek | miniF2F | Putnam | future_end | Length | — | — | 0.7715 | 0.2826 | 0.0874 | — |
| deepseek | miniF2F | Putnam | future_end | Q | — | — | 0.7473 | 0.2758 | 0.0981 | — |
| deepseek | miniF2F | Putnam | future_end | MaxW | — | — | 0.5312 | 0.1711 | 0.4578 | — |
| deepseek | miniF2F | Putnam | future_end | B | — | — | 0.7630 | 0.2813 | 0.0810 | — |
| deepseek | miniF2F | Putnam | future_end | BW | — | — | 0.4971 | 0.1603 | 0.3607 | — |
| deepseek | miniF2F | Putnam | future_end | BH | — | — | 0.1937 | 0.0433 | 0.8202 | — |
| deepseek | miniF2F | Putnam | future_end | BD | — | — | 0.3020 | 0.0946 | 0.6864 | — |
| deepseek | miniF2F | Putnam | future_end | BHD | — | — | 0.1596 | 0.0325 | 0.8691 | — |
| goedel | miniF2F | miniF2F | future_end | Constant | 0.4624 | 0.4191 | 0.6874 | 0.2471 | 0.0000 | 0.0000 |
| goedel | miniF2F | miniF2F | future_end | Length | 0.6204 | 0.5800 | 0.6614 | 0.2343 | 0.2416 | 0.0990 |
| goedel | miniF2F | miniF2F | future_end | Q | 0.5208 | 0.4560 | 0.6853 | 0.2462 | 0.0795 | 0.0519 |
| goedel | miniF2F | miniF2F | future_end | MaxW | 0.6390 | 0.5508 | 0.6517 | 0.2305 | 0.2542 | 0.0999 |
| goedel | miniF2F | miniF2F | future_end | B | 0.6271 | 0.5565 | 0.6598 | 0.2340 | 0.2474 | 0.0999 |
| goedel | miniF2F | miniF2F | future_end | BW | 0.7144 | 0.6371 | 0.6088 | 0.2108 | 0.3454 | 0.0978 |
| goedel | miniF2F | miniF2F | future_end | BH | 0.9206 | 0.8830 | 0.3575 | 0.1119 | 0.7321 | 0.1066 |
| goedel | miniF2F | miniF2F | future_end | BD | 0.8621 | 0.8252 | 0.4597 | 0.1481 | 0.6133 | 0.0970 |
| goedel | miniF2F | miniF2F | future_end | BHD | 0.9247 | 0.8897 | 0.3487 | 0.1085 | 0.7404 | 0.1023 |
| goedel | miniF2F | ProofNet | future_end | Constant | 0.5000 | 0.8529 | 0.7855 | 0.2960 | 0.0000 | 0.0000 |
| goedel | miniF2F | ProofNet | future_end | Length | 0.5149 | 0.8484 | 0.8115 | 0.3010 | 0.1636 | 0.2363 |
| goedel | miniF2F | ProofNet | future_end | Q | 0.5787 | 0.8758 | 0.7707 | 0.2870 | 0.0926 | 0.0819 |
| goedel | miniF2F | ProofNet | future_end | MaxW | 0.3853 | 0.8187 | 0.6626 | 0.2356 | 0.3960 | 0.5810 |
| goedel | miniF2F | ProofNet | future_end | B | 0.5259 | 0.8557 | 0.7937 | 0.2934 | 0.1507 | 0.2115 |
| goedel | miniF2F | ProofNet | future_end | BW | 0.4349 | 0.8316 | 0.6636 | 0.2315 | 0.4232 | 0.5573 |
| goedel | miniF2F | ProofNet | future_end | BH | 0.8710 | 0.9711 | 0.3129 | 0.0938 | 0.9036 | 0.3609 |
| goedel | miniF2F | ProofNet | future_end | BD | 0.7030 | 0.9317 | 0.5244 | 0.1838 | 0.4971 | 0.3275 |
| goedel | miniF2F | ProofNet | future_end | BHD | 0.8804 | 0.9746 | 0.2949 | 0.0890 | 0.9190 | 0.3932 |
| goedel | miniF2F | Putnam | future_end | Constant | — | — | 0.8210 | 0.3136 | 0.0000 | — |
| goedel | miniF2F | Putnam | future_end | Length | — | — | 0.8884 | 0.3372 | 0.1326 | — |
| goedel | miniF2F | Putnam | future_end | Q | — | — | 0.8326 | 0.3139 | 0.1065 | — |
| goedel | miniF2F | Putnam | future_end | MaxW | — | — | 0.5695 | 0.1907 | 0.5171 | — |
| goedel | miniF2F | Putnam | future_end | B | — | — | 0.8978 | 0.3399 | 0.1446 | — |
| goedel | miniF2F | Putnam | future_end | BW | — | — | 0.5288 | 0.1781 | 0.4974 | — |
| goedel | miniF2F | Putnam | future_end | BH | — | — | 0.1821 | 0.0402 | 0.9434 | — |
| goedel | miniF2F | Putnam | future_end | BD | — | — | 0.3691 | 0.1244 | 0.6779 | — |
| goedel | miniF2F | Putnam | future_end | BHD | — | — | 0.1598 | 0.0345 | 0.9488 | — |

## Streaming: решение о наличии ошибки по первой тревоге

| Модель | Обучение | Проверка | Метод | FPR корректных доказательств | Любая тревога на ошибочном | Ранняя | Точно на отказе | Поздняя | Пропуск |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| deepseek | ProofNet | ProofNet | B | 0.0901 | 0.5504 | 0.0397 | 0.0617 | 0.4490 | 0.4496 |
| deepseek | ProofNet | ProofNet | BW | 0.1014 | 0.5614 | 0.0522 | 0.0879 | 0.4214 | 0.4386 |
| deepseek | ProofNet | ProofNet | BH | 0.0473 | 0.5725 | 0.0246 | 0.0956 | 0.4523 | 0.4275 |
| deepseek | ProofNet | ProofNet | BD | 0.1554 | 0.5921 | 0.0126 | 0.0956 | 0.4839 | 0.4079 |
| deepseek | ProofNet | ProofNet | BHD | 0.0968 | 0.5439 | 0.0266 | 0.0867 | 0.4305 | 0.4561 |
| deepseek | ProofNet | miniF2F | B | 0.2162 | 0.5379 | 0.1363 | 0.0624 | 0.3393 | 0.4621 |
| deepseek | ProofNet | miniF2F | BW | 0.2739 | 0.4768 | 0.1181 | 0.0510 | 0.3077 | 0.5232 |
| deepseek | ProofNet | miniF2F | BH | 0.1210 | 0.3300 | 0.0477 | 0.0204 | 0.2618 | 0.6700 |
| deepseek | ProofNet | miniF2F | BD | 0.1415 | 0.4021 | 0.0550 | 0.0321 | 0.3150 | 0.5979 |
| deepseek | ProofNet | miniF2F | BHD | 0.0904 | 0.3113 | 0.0442 | 0.0112 | 0.2559 | 0.6887 |
| deepseek | ProofNet | Putnam | B | — | 0.6825 | 0.0776 | 0.0862 | 0.5187 | 0.3175 |
| deepseek | ProofNet | Putnam | BW | — | 0.6552 | 0.0862 | 0.0603 | 0.5086 | 0.3448 |
| deepseek | ProofNet | Putnam | BH | — | 0.6537 | 0.0000 | 0.0862 | 0.5675 | 0.3463 |
| deepseek | ProofNet | Putnam | BD | — | 0.6336 | 0.0259 | 0.1006 | 0.5072 | 0.3664 |
| deepseek | ProofNet | Putnam | BHD | — | 0.6451 | 0.0086 | 0.0934 | 0.5431 | 0.3549 |
| goedel | ProofNet | ProofNet | B | 0.1000 | 0.4860 | 0.0363 | 0.0457 | 0.4039 | 0.5140 |
| goedel | ProofNet | ProofNet | BW | 0.1111 | 0.5025 | 0.0232 | 0.0865 | 0.3929 | 0.4975 |
| goedel | ProofNet | ProofNet | BH | 0.0556 | 0.3891 | 0.0100 | 0.0789 | 0.3001 | 0.6109 |
| goedel | ProofNet | ProofNet | BD | 0.0722 | 0.5338 | 0.0213 | 0.1190 | 0.3935 | 0.4662 |
| goedel | ProofNet | ProofNet | BHD | 0.0444 | 0.4424 | 0.0175 | 0.0764 | 0.3484 | 0.5576 |
| goedel | ProofNet | miniF2F | B | 0.1970 | 0.5019 | 0.0800 | 0.0210 | 0.4009 | 0.4981 |
| goedel | ProofNet | miniF2F | BW | 0.0787 | 0.2710 | 0.0278 | 0.0160 | 0.2272 | 0.7290 |
| goedel | ProofNet | miniF2F | BH | 0.0377 | 0.1579 | 0.0330 | 0.0160 | 0.1089 | 0.8421 |
| goedel | ProofNet | miniF2F | BD | 0.1608 | 0.4284 | 0.0654 | 0.0382 | 0.3248 | 0.5716 |
| goedel | ProofNet | miniF2F | BHD | 0.0843 | 0.3201 | 0.0544 | 0.0409 | 0.2248 | 0.6799 |
| goedel | ProofNet | Putnam | B | — | 0.6762 | 0.1571 | 0.0143 | 0.5048 | 0.3238 |
| goedel | ProofNet | Putnam | BW | — | 0.4667 | 0.0714 | 0.0286 | 0.3667 | 0.5333 |
| goedel | ProofNet | Putnam | BH | — | 0.6095 | 0.0286 | 0.0571 | 0.5238 | 0.3905 |
| goedel | ProofNet | Putnam | BD | — | 0.7857 | 0.1571 | 0.0667 | 0.5619 | 0.2143 |
| goedel | ProofNet | Putnam | BHD | — | 0.8667 | 0.0714 | 0.1333 | 0.6619 | 0.1333 |
| deepseek | miniF2F | miniF2F | B | 0.0886 | 0.2814 | 0.0303 | 0.0365 | 0.2145 | 0.7186 |
| deepseek | miniF2F | miniF2F | BW | 0.0880 | 0.2927 | 0.0366 | 0.0451 | 0.2110 | 0.7073 |
| deepseek | miniF2F | miniF2F | BH | 0.0894 | 0.4503 | 0.0532 | 0.0683 | 0.3288 | 0.5497 |
| deepseek | miniF2F | miniF2F | BD | 0.0915 | 0.3512 | 0.0215 | 0.0407 | 0.2891 | 0.6488 |
| deepseek | miniF2F | miniF2F | BHD | 0.0820 | 0.4689 | 0.0419 | 0.0704 | 0.3566 | 0.5311 |
| deepseek | miniF2F | ProofNet | B | 0.0090 | 0.2097 | 0.0120 | 0.0271 | 0.1706 | 0.7903 |
| deepseek | miniF2F | ProofNet | BW | 0.0270 | 0.3237 | 0.0256 | 0.0447 | 0.2534 | 0.6763 |
| deepseek | miniF2F | ProofNet | BH | 0.0991 | 0.7039 | 0.0803 | 0.1949 | 0.4287 | 0.2961 |
| deepseek | miniF2F | ProofNet | BD | 0.0518 | 0.4397 | 0.0120 | 0.1046 | 0.3230 | 0.5603 |
| deepseek | miniF2F | ProofNet | BHD | 0.1509 | 0.7245 | 0.1109 | 0.1562 | 0.4573 | 0.2755 |
| deepseek | miniF2F | Putnam | B | — | 0.3635 | 0.0057 | 0.0445 | 0.3132 | 0.6365 |
| deepseek | miniF2F | Putnam | BW | — | 0.4986 | 0.0374 | 0.0733 | 0.3879 | 0.5014 |
| deepseek | miniF2F | Putnam | BH | — | 0.8779 | 0.1250 | 0.2184 | 0.5345 | 0.1221 |
| deepseek | miniF2F | Putnam | BD | — | 0.7270 | 0.0517 | 0.1609 | 0.5144 | 0.2730 |
| deepseek | miniF2F | Putnam | BHD | — | 0.8980 | 0.1853 | 0.1667 | 0.5460 | 0.1020 |
| goedel | miniF2F | miniF2F | B | 0.0954 | 0.2907 | 0.0265 | 0.0355 | 0.2286 | 0.7093 |
| goedel | miniF2F | miniF2F | BW | 0.0937 | 0.3331 | 0.0511 | 0.0386 | 0.2434 | 0.6669 |
| goedel | miniF2F | miniF2F | BH | 0.0961 | 0.4362 | 0.0431 | 0.1094 | 0.2837 | 0.5638 |
| goedel | miniF2F | miniF2F | BD | 0.0706 | 0.3828 | 0.0181 | 0.0355 | 0.3293 | 0.6172 |
| goedel | miniF2F | miniF2F | BHD | 0.0989 | 0.4430 | 0.0383 | 0.0885 | 0.3162 | 0.5570 |
| goedel | miniF2F | ProofNet | B | 0.0000 | 0.2387 | 0.0038 | 0.0188 | 0.2162 | 0.7613 |
| goedel | miniF2F | ProofNet | BW | 0.0278 | 0.3797 | 0.0263 | 0.0482 | 0.3051 | 0.6203 |
| goedel | miniF2F | ProofNet | BH | 0.0111 | 0.4358 | 0.0150 | 0.0476 | 0.3732 | 0.5642 |
| goedel | miniF2F | ProofNet | BD | 0.0972 | 0.4754 | 0.0251 | 0.1335 | 0.3169 | 0.5246 |
| goedel | miniF2F | ProofNet | BHD | 0.0389 | 0.5098 | 0.0201 | 0.0539 | 0.4358 | 0.4902 |
| goedel | miniF2F | Putnam | B | — | 0.3429 | 0.0857 | 0.0286 | 0.2286 | 0.6571 |
| goedel | miniF2F | Putnam | BW | — | 0.5143 | 0.1857 | 0.0381 | 0.2905 | 0.4857 |
| goedel | miniF2F | Putnam | BH | — | 0.8143 | 0.0286 | 0.2048 | 0.5810 | 0.1857 |
| goedel | miniF2F | Putnam | BD | — | 0.6714 | 0.0857 | 0.0857 | 0.5000 | 0.3286 |
| goedel | miniF2F | Putnam | BHD | — | 0.8952 | 0.0524 | 0.2238 | 0.6190 | 0.1048 |

Все19 вариантов, интервалы, парные различия, показатели на фиксированных префиксах и по длине сохранены в metrics.json/metrics.csv. Интервалы:2000 повторов по группам задач, фиксированные обученные предсказания; для двухклассовых интервалов нужны минимум20 групп каждого класса. Порог заморожен на внутренних OOF-предсказаниях; test FPR может отличаться от целевого.

У present отдельно сохранены тревоги на корректных доказательствах, тревоги до ошибки, точные и поздние тревоги, задержка и пропуски. Полнота любой тревоги на ошибочном доказательстве не равна точности определения момента ошибки. Прогноз future не является результатом предотвращения ошибки или исправления генерации.
