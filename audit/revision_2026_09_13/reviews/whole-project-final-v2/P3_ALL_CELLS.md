# P3: все ячейки и причины недоступности

## bounded_null

| Ячейка | Доступность | Условное покрытие | MC CI95 | Попадание / все | Bias | Width | Промах ниже / выше |
| --- | --- | --- | --- | --- | --- | --- | --- |
| current/independent_floor/basic | 188/200 (94.00%) | 178/188 (94.68%) | [0.90436, 0.9742] | 178/200 (89.00%) | -0.052911 | 0.52408 | 6 / 4 |
| current/independent_floor/percentile | 188/200 (94.00%) | 173/188 (92.02%) | [0.87182, 0.95466] | 173/200 (86.50%) | -0.052911 | 0.52408 | 14 / 1 |
| current/observed_minimum/basic | 188/200 (94.00%) | 178/188 (94.68%) | [0.90436, 0.9742] | 178/200 (89.00%) | -0.052911 | 0.52407 | 6 / 4 |
| current/observed_minimum/percentile | 188/200 (94.00%) | 173/188 (92.02%) | [0.87182, 0.95466] | 173/200 (86.50%) | -0.052911 | 0.52407 | 14 / 1 |
| current/oracle_correct_selection/basic | 188/200 (94.00%) | 178/188 (94.68%) | [0.90436, 0.9742] | 178/200 (89.00%) | -0.052911 | 0.52409 | 6 / 4 |
| current/oracle_correct_selection/percentile | 188/200 (94.00%) | 173/188 (92.02%) | [0.87182, 0.95466] | 173/200 (86.50%) | -0.052911 | 0.52409 | 14 / 1 |
| current/original/basic | 188/200 (94.00%) | 178/188 (94.68%) | [0.90436, 0.9742] | 178/200 (89.00%) | -0.052911 | 0.52411 | 6 / 4 |
| current/original/percentile | 188/200 (94.00%) | 173/188 (92.02%) | [0.87182, 0.95466] | 173/200 (86.50%) | -0.052911 | 0.52411 | 14 / 1 |
| current/pooled_original/basic | 200/200 (100.00%) | 187/200 (93.50%) | [0.89141, 0.96494] | 187/200 (93.50%) | -0.028734 | 0.33567 | 10 / 3 |
| current/pooled_original/percentile | 200/200 (100.00%) | 180/200 (90.00%) | [0.84979, 0.93784] | 180/200 (90.00%) | -0.028734 | 0.33567 | 19 / 1 |
| larger/independent_floor/basic | 194/200 (97.00%) | 181/194 (93.30%) | [0.88814, 0.96384] | 181/200 (90.50%) | -0.055075 | 0.51778 | 10 / 3 |
| larger/independent_floor/percentile | 194/200 (97.00%) | 168/194 (86.60%) | [0.80983, 0.91055] | 168/200 (84.00%) | -0.055075 | 0.51778 | 25 / 1 |
| larger/observed_minimum/basic | 194/200 (97.00%) | 181/194 (93.30%) | [0.88814, 0.96384] | 181/200 (90.50%) | -0.055075 | 0.51778 | 10 / 3 |
| larger/observed_minimum/percentile | 194/200 (97.00%) | 168/194 (86.60%) | [0.80983, 0.91055] | 168/200 (84.00%) | -0.055075 | 0.51778 | 25 / 1 |
| larger/oracle_correct_selection/basic | 194/200 (97.00%) | 181/194 (93.30%) | [0.88814, 0.96384] | 181/200 (90.50%) | -0.055075 | 0.51778 | 10 / 3 |
| larger/oracle_correct_selection/percentile | 194/200 (97.00%) | 168/194 (86.60%) | [0.80983, 0.91055] | 168/200 (84.00%) | -0.055075 | 0.51778 | 25 / 1 |
| larger/original/basic | 194/200 (97.00%) | 181/194 (93.30%) | [0.88814, 0.96384] | 181/200 (90.50%) | -0.055075 | 0.51778 | 10 / 3 |
| larger/original/percentile | 194/200 (97.00%) | 168/194 (86.60%) | [0.80983, 0.91055] | 168/200 (84.00%) | -0.055075 | 0.51778 | 25 / 1 |
| larger/pooled_original/basic | 200/200 (100.00%) | 185/200 (92.50%) | [0.87932, 0.95742] | 185/200 (92.50%) | -0.029001 | 0.32416 | 11 / 4 |
| larger/pooled_original/percentile | 200/200 (100.00%) | 175/200 (87.50%) | [0.82103, 0.91745] | 175/200 (87.50%) | -0.029001 | 0.32416 | 24 / 1 |

### current/independent_floor/percentile

Недоступность: {"failure_excesses_insufficient": 7, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 3, "too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 98538, "uniform_boundary_wins": 1462}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/observed_minimum/percentile

Недоступность: {"failure_excesses_insufficient": 7, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 3, "too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 98538, "uniform_boundary_wins": 1462}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/oracle_correct_selection/percentile

Недоступность: {"failure_excesses_insufficient": 7, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 3, "too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 98538, "uniform_boundary_wins": 1462}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/original/percentile

Недоступность: {"failure_excesses_insufficient": 7, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 3, "too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 98538, "uniform_boundary_wins": 1462}.

Порог ниже support, original / bootstrap: 0 / 413.

### current/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 99980, "uniform_boundary_wins": 20}.

Порог ниже support, original / bootstrap: 0 / 413.

### larger/independent_floor/percentile

Недоступность: {"failure_excesses_insufficient": 4, "too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 99113, "uniform_boundary_wins": 887}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/observed_minimum/percentile

Недоступность: {"failure_excesses_insufficient": 4, "too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 99113, "uniform_boundary_wins": 887}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/oracle_correct_selection/percentile

Недоступность: {"failure_excesses_insufficient": 4, "too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 99113, "uniform_boundary_wins": 887}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/original/percentile

Недоступность: {"failure_excesses_insufficient": 4, "too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 99113, "uniform_boundary_wins": 887}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 99996, "uniform_boundary_wins": 4}.

Порог ниже support, original / bootstrap: 0 / 0.

## exponential_null

| Ячейка | Доступность | Условное покрытие | MC CI95 | Попадание / все | Bias | Width | Промах ниже / выше |
| --- | --- | --- | --- | --- | --- | --- | --- |
| current/independent_floor/basic | 189/200 (94.50%) | 178/189 (94.18%) | [0.89825, 0.97059] | 178/200 (89.00%) | -0.038038 | 0.58804 | 7 / 4 |
| current/independent_floor/percentile | 189/200 (94.50%) | 167/189 (88.36%) | [0.82908, 0.9256] | 167/200 (83.50%) | -0.038038 | 0.58804 | 21 / 1 |
| current/observed_minimum/basic | 189/200 (94.50%) | 178/189 (94.18%) | [0.89825, 0.97059] | 178/200 (89.00%) | -0.038038 | 0.58802 | 7 / 4 |
| current/observed_minimum/percentile | 189/200 (94.50%) | 167/189 (88.36%) | [0.82908, 0.9256] | 167/200 (83.50%) | -0.038038 | 0.58802 | 21 / 1 |
| current/oracle_correct_selection/basic | 189/200 (94.50%) | 178/189 (94.18%) | [0.89825, 0.97059] | 178/200 (89.00%) | -0.038038 | 0.588 | 7 / 4 |
| current/oracle_correct_selection/percentile | 189/200 (94.50%) | 167/189 (88.36%) | [0.82908, 0.9256] | 167/200 (83.50%) | -0.038038 | 0.588 | 21 / 1 |
| current/original/basic | 189/200 (94.50%) | 178/189 (94.18%) | [0.89825, 0.97059] | 178/200 (89.00%) | -0.038038 | 0.58815 | 7 / 4 |
| current/original/percentile | 189/200 (94.50%) | 167/189 (88.36%) | [0.82908, 0.9256] | 167/200 (83.50%) | -0.038038 | 0.58815 | 21 / 1 |
| current/pooled_original/basic | 200/200 (100.00%) | 182/200 (91.00%) | [0.86149, 0.94579] | 182/200 (91.00%) | -0.018548 | 0.38892 | 13 / 5 |
| current/pooled_original/percentile | 200/200 (100.00%) | 180/200 (90.00%) | [0.84979, 0.93784] | 180/200 (90.00%) | -0.018548 | 0.38892 | 20 / 0 |
| larger/independent_floor/basic | 197/200 (98.50%) | 186/197 (94.42%) | [0.90229, 0.9718] | 186/200 (93.00%) | -0.031407 | 0.57088 | 9 / 2 |
| larger/independent_floor/percentile | 197/200 (98.50%) | 175/197 (88.83%) | [0.83581, 0.92868] | 175/200 (87.50%) | -0.031407 | 0.57088 | 21 / 1 |
| larger/observed_minimum/basic | 197/200 (98.50%) | 186/197 (94.42%) | [0.90229, 0.9718] | 186/200 (93.00%) | -0.031407 | 0.57088 | 9 / 2 |
| larger/observed_minimum/percentile | 197/200 (98.50%) | 175/197 (88.83%) | [0.83581, 0.92868] | 175/200 (87.50%) | -0.031407 | 0.57088 | 21 / 1 |
| larger/oracle_correct_selection/basic | 197/200 (98.50%) | 186/197 (94.42%) | [0.90229, 0.9718] | 186/200 (93.00%) | -0.031407 | 0.57088 | 9 / 2 |
| larger/oracle_correct_selection/percentile | 197/200 (98.50%) | 175/197 (88.83%) | [0.83581, 0.92868] | 175/200 (87.50%) | -0.031407 | 0.57088 | 21 / 1 |
| larger/original/basic | 197/200 (98.50%) | 186/197 (94.42%) | [0.90229, 0.9718] | 186/200 (93.00%) | -0.031407 | 0.57088 | 9 / 2 |
| larger/original/percentile | 197/200 (98.50%) | 175/197 (88.83%) | [0.83581, 0.92868] | 175/200 (87.50%) | -0.031407 | 0.57088 | 21 / 1 |
| larger/pooled_original/basic | 200/200 (100.00%) | 180/200 (90.00%) | [0.84979, 0.93784] | 180/200 (90.00%) | -0.015064 | 0.3705 | 16 / 4 |
| larger/pooled_original/percentile | 200/200 (100.00%) | 179/200 (89.50%) | [0.84398, 0.93382] | 179/200 (89.50%) | -0.015064 | 0.3705 | 20 / 1 |

### current/independent_floor/percentile

Недоступность: {"failure_excesses_insufficient": 9, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 99332, "uniform_boundary_wins": 668}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/observed_minimum/percentile

Недоступность: {"failure_excesses_insufficient": 9, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 99332, "uniform_boundary_wins": 668}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/oracle_correct_selection/percentile

Недоступность: {"failure_excesses_insufficient": 9, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 99332, "uniform_boundary_wins": 668}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/original/percentile

Недоступность: {"failure_excesses_insufficient": 9, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 2}.

Bootstrap fit: {"interior_stationary_maximum": 99332, "uniform_boundary_wins": 668}.

Порог ниже support, original / bootstrap: 0 / 410.

### current/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 99976, "uniform_boundary_wins": 24}.

Порог ниже support, original / bootstrap: 0 / 410.

### larger/independent_floor/percentile

Недоступность: {"failure_excesses_insufficient": 3}.

Bootstrap fit: {"interior_stationary_maximum": 99778, "uniform_boundary_wins": 222}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/observed_minimum/percentile

Недоступность: {"failure_excesses_insufficient": 3}.

Bootstrap fit: {"interior_stationary_maximum": 99778, "uniform_boundary_wins": 222}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/oracle_correct_selection/percentile

Недоступность: {"failure_excesses_insufficient": 3}.

Bootstrap fit: {"interior_stationary_maximum": 99778, "uniform_boundary_wins": 222}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/original/percentile

Недоступность: {"failure_excesses_insufficient": 3}.

Bootstrap fit: {"interior_stationary_maximum": 99778, "uniform_boundary_wins": 222}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: 0 / 0.

## lower_support

| Ячейка | Доступность | Условное покрытие | MC CI95 | Попадание / все | Bias | Width | Промах ниже / выше |
| --- | --- | --- | --- | --- | --- | --- | --- |
| current/independent_floor/basic | 190/200 (95.00%) | 177/190 (93.16%) | [0.88584, 0.96307] | 177/200 (88.50%) | -0.045977 | 0.66059 | 9 / 4 |
| current/independent_floor/percentile | 190/200 (95.00%) | 173/190 (91.05%) | [0.86061, 0.94701] | 173/200 (86.50%) | -0.045977 | 0.66059 | 17 / 0 |
| current/observed_minimum/basic | 190/200 (95.00%) | 177/190 (93.16%) | [0.88584, 0.96307] | 177/200 (88.50%) | -0.045977 | 0.66053 | 9 / 4 |
| current/observed_minimum/percentile | 190/200 (95.00%) | 173/190 (91.05%) | [0.86061, 0.94701] | 173/200 (86.50%) | -0.045977 | 0.66053 | 17 / 0 |
| current/oracle_correct_selection/basic | 190/200 (95.00%) | 177/190 (93.16%) | [0.88584, 0.96307] | 177/200 (88.50%) | -0.045977 | 0.66049 | 9 / 4 |
| current/oracle_correct_selection/percentile | 190/200 (95.00%) | 173/190 (91.05%) | [0.86061, 0.94701] | 173/200 (86.50%) | -0.045977 | 0.66049 | 17 / 0 |
| current/original/basic | 190/200 (95.00%) | 177/190 (93.16%) | [0.88584, 0.96307] | 177/200 (88.50%) | -0.045977 | 0.6602 | 9 / 4 |
| current/original/percentile | 190/200 (95.00%) | 173/190 (91.05%) | [0.86061, 0.94701] | 173/200 (86.50%) | -0.045977 | 0.6602 | 17 / 0 |
| current/pooled_original/basic | 200/200 (100.00%) | 182/200 (91.00%) | [0.86149, 0.94579] | 182/200 (91.00%) | -0.022489 | 0.44883 | 12 / 6 |
| current/pooled_original/percentile | 200/200 (100.00%) | 189/200 (94.50%) | [0.90372, 0.97223] | 189/200 (94.50%) | -0.022489 | 0.44883 | 11 / 0 |
| larger/independent_floor/basic | 197/200 (98.50%) | 182/197 (92.39%) | [0.87752, 0.95676] | 182/200 (91.00%) | -0.046789 | 0.63892 | 11 / 4 |
| larger/independent_floor/percentile | 197/200 (98.50%) | 177/197 (89.85%) | [0.84757, 0.93688] | 177/200 (88.50%) | -0.046789 | 0.63892 | 20 / 0 |
| larger/observed_minimum/basic | 197/200 (98.50%) | 182/197 (92.39%) | [0.87752, 0.95676] | 182/200 (91.00%) | -0.046789 | 0.63892 | 11 / 4 |
| larger/observed_minimum/percentile | 197/200 (98.50%) | 177/197 (89.85%) | [0.84757, 0.93688] | 177/200 (88.50%) | -0.046789 | 0.63892 | 20 / 0 |
| larger/oracle_correct_selection/basic | 197/200 (98.50%) | 182/197 (92.39%) | [0.87752, 0.95676] | 182/200 (91.00%) | -0.046789 | 0.63892 | 11 / 4 |
| larger/oracle_correct_selection/percentile | 197/200 (98.50%) | 177/197 (89.85%) | [0.84757, 0.93688] | 177/200 (88.50%) | -0.046789 | 0.63892 | 20 / 0 |
| larger/original/basic | 197/200 (98.50%) | 182/197 (92.39%) | [0.87752, 0.95676] | 182/200 (91.00%) | -0.046789 | 0.63892 | 11 / 4 |
| larger/original/percentile | 197/200 (98.50%) | 177/197 (89.85%) | [0.84757, 0.93688] | 177/200 (88.50%) | -0.046789 | 0.63892 | 20 / 0 |
| larger/pooled_original/basic | 200/200 (100.00%) | 181/200 (90.50%) | [0.85562, 0.94183] | 181/200 (90.50%) | -0.017895 | 0.43191 | 15 / 4 |
| larger/pooled_original/percentile | 200/200 (100.00%) | 184/200 (92.00%) | [0.87334, 0.95358] | 184/200 (92.00%) | -0.017895 | 0.43191 | 15 / 1 |

### current/independent_floor/percentile

Недоступность: {"failure_excesses_insufficient": 10}.

Bootstrap fit: {"interior_stationary_maximum": 99832, "uniform_boundary_wins": 168}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/observed_minimum/percentile

Недоступность: {"failure_excesses_insufficient": 10}.

Bootstrap fit: {"interior_stationary_maximum": 99832, "uniform_boundary_wins": 168}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/oracle_correct_selection/percentile

Недоступность: {"failure_excesses_insufficient": 10}.

Bootstrap fit: {"interior_stationary_maximum": 99832, "uniform_boundary_wins": 168}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/original/percentile

Недоступность: {"failure_excesses_insufficient": 10}.

Bootstrap fit: {"interior_stationary_maximum": 99832, "uniform_boundary_wins": 168}.

Порог ниже support, original / bootstrap: 0 / 440.

### current/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 99995, "uniform_boundary_wins": 5}.

Порог ниже support, original / bootstrap: 0 / 440.

### larger/independent_floor/percentile

Недоступность: {"failure_excesses_insufficient": 3}.

Bootstrap fit: {"interior_stationary_maximum": 99948, "uniform_boundary_wins": 52}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/observed_minimum/percentile

Недоступность: {"failure_excesses_insufficient": 3}.

Bootstrap fit: {"interior_stationary_maximum": 99948, "uniform_boundary_wins": 52}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/oracle_correct_selection/percentile

Недоступность: {"failure_excesses_insufficient": 3}.

Bootstrap fit: {"interior_stationary_maximum": 99948, "uniform_boundary_wins": 52}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/original/percentile

Недоступность: {"failure_excesses_insufficient": 3}.

Bootstrap fit: {"interior_stationary_maximum": 99948, "uniform_boundary_wins": 52}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: 0 / 0.

## original_support

| Ячейка | Доступность | Условное покрытие | MC CI95 | Попадание / все | Bias | Width | Промах ниже / выше |
| --- | --- | --- | --- | --- | --- | --- | --- |
| current/independent_floor/basic | 147/200 (73.50%) | 136/147 (92.52%) | [0.87005, 0.96205] | 136/200 (68.00%) | -0.021143 | 0.48376 | 8 / 3 |
| current/independent_floor/percentile | 147/200 (73.50%) | 137/147 (93.20%) | [0.87845, 0.9669] | 137/200 (68.50%) | -0.021143 | 0.48376 | 9 / 1 |
| current/observed_minimum/basic | 148/200 (74.00%) | 137/148 (92.57%) | [0.87091, 0.96232] | 137/200 (68.50%) | -0.021181 | 0.48414 | 8 / 3 |
| current/observed_minimum/percentile | 148/200 (74.00%) | 137/148 (92.57%) | [0.87091, 0.96232] | 137/200 (68.50%) | -0.021181 | 0.48414 | 10 / 1 |
| current/oracle_correct_selection/basic | 149/200 (74.50%) | 139/149 (93.29%) | [0.88004, 0.96735] | 139/200 (69.50%) | -0.021006 | 0.48229 | 6 / 4 |
| current/oracle_correct_selection/percentile | 149/200 (74.50%) | 139/149 (93.29%) | [0.88004, 0.96735] | 139/200 (69.50%) | -0.021006 | 0.48229 | 10 / 0 |
| current/original/basic | 200/200 (100.00%) | 161/200 (80.50%) | [0.74321, 0.85751] | 161/200 (80.50%) | -0.094104 | 0.52126 | 36 / 3 |
| current/original/percentile | 200/200 (100.00%) | 162/200 (81.00%) | [0.74867, 0.8619] | 162/200 (81.00%) | -0.094104 | 0.52126 | 38 / 0 |
| current/pooled_original/basic | 200/200 (100.00%) | 154/200 (77.00%) | [0.70539, 0.82642] | 154/200 (77.00%) | -0.080549 | 0.39958 | 44 / 2 |
| current/pooled_original/percentile | 200/200 (100.00%) | 163/200 (81.50%) | [0.75414, 0.86627] | 163/200 (81.50%) | -0.080549 | 0.39958 | 37 / 0 |
| larger/independent_floor/basic | 200/200 (100.00%) | 184/200 (92.00%) | [0.87334, 0.95358] | 184/200 (92.00%) | -0.021513 | 0.432 | 11 / 5 |
| larger/independent_floor/percentile | 200/200 (100.00%) | 184/200 (92.00%) | [0.87334, 0.95358] | 184/200 (92.00%) | -0.021513 | 0.432 | 14 / 2 |
| larger/observed_minimum/basic | 200/200 (100.00%) | 184/200 (92.00%) | [0.87334, 0.95358] | 184/200 (92.00%) | -0.021176 | 0.4328 | 11 / 5 |
| larger/observed_minimum/percentile | 200/200 (100.00%) | 183/200 (91.50%) | [0.86739, 0.9497] | 183/200 (91.50%) | -0.021176 | 0.4328 | 14 / 3 |
| larger/oracle_correct_selection/basic | 200/200 (100.00%) | 183/200 (91.50%) | [0.86739, 0.9497] | 183/200 (91.50%) | -0.021406 | 0.43086 | 11 / 6 |
| larger/oracle_correct_selection/percentile | 200/200 (100.00%) | 186/200 (93.00%) | [0.88534, 0.9612] | 186/200 (93.00%) | -0.021406 | 0.43086 | 12 / 2 |
| larger/original/basic | 200/200 (100.00%) | 174/200 (87.00%) | [0.81535, 0.91329] | 174/200 (87.00%) | -0.065415 | 0.45592 | 21 / 5 |
| larger/original/percentile | 200/200 (100.00%) | 167/200 (83.50%) | [0.77616, 0.88362] | 167/200 (83.50%) | -0.065415 | 0.45592 | 33 / 0 |
| larger/pooled_original/basic | 200/200 (100.00%) | 177/200 (88.50%) | [0.83245, 0.92569] | 177/200 (88.50%) | -0.053714 | 0.34253 | 21 / 2 |
| larger/pooled_original/percentile | 200/200 (100.00%) | 166/200 (83.00%) | [0.77063, 0.8793] | 166/200 (83.00%) | -0.053714 | 0.34253 | 34 / 0 |

### current/independent_floor/percentile

Недоступность: {"calibration_excesses_insufficient": 52, "calibration_tail_tasks_insufficient;calibration_excesses_insufficient": 1}.

Bootstrap fit: {"interior_stationary_maximum": 99997, "uniform_boundary_wins": 3}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/observed_minimum/percentile

Недоступность: {"calibration_excesses_insufficient": 51, "calibration_tail_tasks_insufficient;calibration_excesses_insufficient": 1}.

Bootstrap fit: {"interior_stationary_maximum": 99997, "uniform_boundary_wins": 3}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/oracle_correct_selection/percentile

Недоступность: {"calibration_excesses_insufficient": 50, "calibration_tail_tasks_insufficient;calibration_excesses_insufficient": 1}.

Bootstrap fit: {"interior_stationary_maximum": 99997, "uniform_boundary_wins": 3}.

Порог ниже support, original / bootstrap: 0 / 0.

### current/original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 99997, "uniform_boundary_wins": 3}.

Порог ниже support, original / bootstrap: 112 / 55463.

### current/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: 112 / 55463.

### larger/independent_floor/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/observed_minimum/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/oracle_correct_selection/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: 0 / 0.

### larger/original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: 117 / 56956.

### larger/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: 117 / 56956.

## soft_selection_stress

| Ячейка | Доступность | Условное покрытие | MC CI95 | Попадание / все | Bias | Width | Промах ниже / выше |
| --- | --- | --- | --- | --- | --- | --- | --- |
| current/independent_floor/basic | 130/200 (65.00%) | 115/130 (88.46%) | [0.81684, 0.93396] | 115/200 (57.50%) | -0.058425 | 0.72249 | 12 / 3 |
| current/independent_floor/percentile | 130/200 (65.00%) | 113/130 (86.92%) | [0.7989, 0.92194] | 113/200 (56.50%) | -0.058425 | 0.72249 | 17 / 0 |
| current/observed_minimum/basic | 130/200 (65.00%) | 115/130 (88.46%) | [0.81684, 0.93396] | 115/200 (57.50%) | -0.058425 | 0.72249 | 12 / 3 |
| current/observed_minimum/percentile | 130/200 (65.00%) | 113/130 (86.92%) | [0.7989, 0.92194] | 113/200 (56.50%) | -0.058425 | 0.72249 | 17 / 0 |
| current/original/basic | 130/200 (65.00%) | 115/130 (88.46%) | [0.81684, 0.93396] | 115/200 (57.50%) | -0.058425 | 0.72249 | 12 / 3 |
| current/original/percentile | 130/200 (65.00%) | 113/130 (86.92%) | [0.7989, 0.92194] | 113/200 (56.50%) | -0.058425 | 0.72249 | 17 / 0 |
| current/pooled_original/basic | 200/200 (100.00%) | 183/200 (91.50%) | [0.86739, 0.9497] | 183/200 (91.50%) | -0.034836 | 0.52596 | 13 / 4 |
| current/pooled_original/percentile | 200/200 (100.00%) | 176/200 (88.00%) | [0.82673, 0.92158] | 176/200 (88.00%) | -0.034836 | 0.52596 | 20 / 4 |
| larger/independent_floor/basic | 136/200 (68.00%) | 126/136 (92.65%) | [0.86893, 0.96418] | 126/200 (63.00%) | -0.052211 | 0.71585 | 9 / 1 |
| larger/independent_floor/percentile | 136/200 (68.00%) | 118/136 (86.76%) | [0.79891, 0.91963] | 118/200 (59.00%) | -0.052211 | 0.71585 | 18 / 0 |
| larger/observed_minimum/basic | 136/200 (68.00%) | 126/136 (92.65%) | [0.86893, 0.96418] | 126/200 (63.00%) | -0.052211 | 0.71585 | 9 / 1 |
| larger/observed_minimum/percentile | 136/200 (68.00%) | 118/136 (86.76%) | [0.79891, 0.91963] | 118/200 (59.00%) | -0.052211 | 0.71585 | 18 / 0 |
| larger/original/basic | 136/200 (68.00%) | 126/136 (92.65%) | [0.86893, 0.96418] | 126/200 (63.00%) | -0.052211 | 0.71585 | 9 / 1 |
| larger/original/percentile | 136/200 (68.00%) | 118/136 (86.76%) | [0.79891, 0.91963] | 118/200 (59.00%) | -0.052211 | 0.71585 | 18 / 0 |
| larger/pooled_original/basic | 200/200 (100.00%) | 179/200 (89.50%) | [0.84398, 0.93382] | 179/200 (89.50%) | -0.02614 | 0.49942 | 15 / 6 |
| larger/pooled_original/percentile | 200/200 (100.00%) | 179/200 (89.50%) | [0.84398, 0.93382] | 179/200 (89.50%) | -0.02614 | 0.49942 | 19 / 2 |

### current/independent_floor/percentile

Недоступность: {"failure_excesses_insufficient": 69, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 1}.

Bootstrap fit: {"interior_stationary_maximum": 99339, "uniform_boundary_wins": 661}.

Порог ниже support, original / bootstrap: None / None.

### current/observed_minimum/percentile

Недоступность: {"failure_excesses_insufficient": 69, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 1}.

Bootstrap fit: {"interior_stationary_maximum": 99339, "uniform_boundary_wins": 661}.

Порог ниже support, original / bootstrap: None / None.

### current/original/percentile

Недоступность: {"failure_excesses_insufficient": 69, "failure_excesses_insufficient;too_few_finite_bootstrap_fits": 1}.

Bootstrap fit: {"interior_stationary_maximum": 99339, "uniform_boundary_wins": 661}.

Порог ниже support, original / bootstrap: None / None.

### current/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 99970, "uniform_boundary_wins": 30}.

Порог ниже support, original / bootstrap: None / None.

### larger/independent_floor/percentile

Недоступность: {"failure_excesses_insufficient": 64}.

Bootstrap fit: {"interior_stationary_maximum": 99728, "uniform_boundary_wins": 272}.

Порог ниже support, original / bootstrap: None / None.

### larger/observed_minimum/percentile

Недоступность: {"failure_excesses_insufficient": 64}.

Bootstrap fit: {"interior_stationary_maximum": 99728, "uniform_boundary_wins": 272}.

Порог ниже support, original / bootstrap: None / None.

### larger/original/percentile

Недоступность: {"failure_excesses_insufficient": 64}.

Bootstrap fit: {"interior_stationary_maximum": 99728, "uniform_boundary_wins": 272}.

Порог ниже support, original / bootstrap: None / None.

### larger/pooled_original/percentile

Недоступность: {}.

Bootstrap fit: {"interior_stationary_maximum": 100000}.

Порог ниже support, original / bootstrap: None / None.
