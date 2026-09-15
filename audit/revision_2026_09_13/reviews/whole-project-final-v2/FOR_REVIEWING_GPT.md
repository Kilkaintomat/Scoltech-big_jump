# Новый блокер, который нужно проверить первым

Один Kimina shard имеет полный manifest, но не прошёл semantic gate. Не считать такой manifest достаточным допуском к анализу. Проверь превращение <;> в > при dedent, изолированный candidate и его границы проверки. Production-исправление и восстановление ветки пока не выполнены.

# Задание независимому GPT / исследователю

Проведи критическую ревизию One Big Jump по этому пакету. Не предполагай, что гипотеза обязана подтвердиться. Начни с REPORT.md, NEXT_PLAN.md, metrics.json и P3_ALL_CELLS.md.

Проверь:
1. Какие результаты завершены и имеют manifest, какие являются partial main progress, какие относятся к старому lineage. Не складывай их в одну выборку.
2. Provenance: source commit+dirty, immutable source hashes, package versions, hardware, inputs/outputs. artifact-index.json задаёт соответствие серверных путей локальным копиям. Веса/все активации не включены; явно перечисли, какие зависимости ты не можешь проверить.
3. P3-код: правильность constrained optimizer и boundary; независимость calibration/evaluation/support; правила threshold и перерасчёт при bootstrap; сравнение equal-budget с pooled_original. Все новые draws включены.
4. Различие availability, coverage conditional on availability и попадания в цель на всей запланированной выборке. Проверь знаменатели, причины gate failures, направления bias и Monte Carlo uncertainty.
5. Фиксированный primary candidate и семейные bounds только по четырём hard-сценариям. Soft stress оценивает recovery parent/asymptotic target при misspecification; не называй его точной GPD calibration. Oracle неприменим к реальным данным.
6. Какие ограничения iid-синтетики препятствуют переносу результатов на зависимые Lean-трассы, whitening и absorbing first-failure selection. q=0.001 здесь не проверен.
7. Lean: source/ содержит основной v7; проверяй scopes без утечки константы-ответа, proofStatus, I/O, cleanup и absorbing labels. Случаи native-policy-only не равны математическим ошибкам. Gate-пакет не является случайной независимой ревизией всего main.
8. Pilot controls: сравни старый model_root с текущим и semantic label delta; не считай эквивалентность меток доказательством равенства активаций. Проверь disjoint task split, shrinkage, n/d, first-step population и парный surprisal.
9. P4: все три signed gamma, fixed-fraction vs full-tail, отсутствие псевдорепликации по checkpoints; отрицательный/неопределённый результат должен сохраниться.
10. Deduction: формат отдельно от reasoning, unchanged checker, обе fresh непарные выборки, закрытый main gate. P5: идентифицируемость theta/tau и held-out design.
11. Противоречия experimental_specification.md, runtime amendments и фактически выполненной программы. Отдельно укажи незакрытые эксперименты draft.

Верни:
- конкретные ошибки с файлами/функциями и воспроизводимым примером;
- подтверждённые наблюдения и отдельно неподдержанные claims;
- ограничения мощности и external validity;
- исправленный приоритетный план с критериями завершения;
- какие проверки ты реально выполнил и какие не смог.

Не предлагай подбирать seeds, primary cell, окно P4 или gate ради желаемого знака. Не заменяй недоступный результат нулём и не выводи bounded support из одной отрицательной точки.
