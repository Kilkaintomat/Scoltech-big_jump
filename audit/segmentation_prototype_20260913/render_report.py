from pathlib import Path
import json,datetime,html,re,hashlib,os,statistics
O=Path(__file__).parent
S=json.loads((O/'statistics.json').read_text(encoding='utf-8'))
D=json.loads((O/'length-details.json').read_text(encoding='utf-8'))
V=json.loads((O/'validation/metrics.json').read_text(encoding='utf-8'))
R=json.loads((O/'review/metrics.json').read_text(encoding='utf-8'))
C=json.loads((O/'review/cases.json').read_text(encoding='utf-8'))
U=json.loads((O/'validation_supplement/metrics.json').read_text(encoding='utf-8'))
N={'deepseek':'DeepSeek','goedel':'Goedel','kimina':'Kimina'}
out=[]
def p(s=''):out.append(s+'\n')
def num(x):return f'{x:.2f}'.replace('.',',')
def percent(a,b):return num(100*a/b)+'%'
def table(head,rows):
 p('\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+
   ['| '+' | '.join(str(c).replace('|','/').replace('\n',' ') for c in r)+' |' for r in rows]))
stamp=datetime.datetime.fromisoformat(S['captured_utc']).astimezone(datetime.timezone(datetime.timedelta(hours=3)))
p('**Сегментация Lean: измеренные длины и проверенный прототип**')
p('Срез исходных журналов: **'+stamp.strftime('%d.%m.%Y %H:%M:%S МСК')+'**. Сравнение использует одинаковые семь завершённых исправленных шардов: по 5 664 ответа на 354 задачи каждой модели, всего 16 992 ответа. Это статистика существующих журналов, а не новый запуск на всём датасете.')
p('**Рекомендация:** перейти к более частым границам по синтаксическому дереву Lean, сохраняя вложенность, исходный порядок токенов и отдельные отметки завершения доказательства. Нынешнее разбиение оставить как базовое сравнение. Прототип готов для дальнейшей малой проверки; для массовой замены проверяющего конвейера он пока не готов.')
p('**1. Что именно считаем**')
p('L — число сохранённых блоков в одной сгенерированной попытке, а не число уникальных математических задач. На слой приходится L+1 внутренних состояний X₀,…,X_L: X₀ после последнего токена промпта, затем по состоянию на конец каждого блока. Из них получают L приращений. Это число точек, заданных разметкой; подсчёт не подтверждает завершение извлечения активаций на основной серии.')
p('Для каждой группы усреднение выполнено по попыткам. Несколько попыток одной задачи зависимы. Нулевая длина steps при отсутствии пригодного разбора не означает доказательство за ноль шагов; такие записи отдельно посчитаны и не включены в среднюю длину.')
p('**2. Пригодные по типу разметки трассы: verified ∪ localized_tactic_failure**')
table(['Модель','Трасс','Среднее L','Медиана','90% не длиннее','Не более 3 блоков','Среднее точек L+1'],
 [[N[m],(v:=S['common'][m]['all_roles_temperatures']['usable'])['n'],num(v['mean']),num(v['median']),num(v['q90']),percent(v['le3'],v['n']),num(v['mean_points'])] for m in N])
p('«Пригодные» здесь означает наличие нужной категории Lean; это ещё не сертификат пригодности всех активаций для статистических тестов.')
table(['Модель','Группа','Трасс','Среднее L','Медиана','q95','Максимум'],
 [[N[m],cat,(v:=S['common'][m]['all_roles_temperatures'][cat])['n'],num(v['mean']),num(v['median']),num(v['q95']),v['max']] for m in N for cat in ['verified','localized_tactic_failure']])
p('**3. Все ответы и основная настройка evaluation, T=0,6**')
table(['Модель','Всего ответов','Есть блоки','Нет блоков','Среднее L среди имеющих блоки'],
 [[N[m],(v:=S['common'][m]['all_roles_temperatures']['all'])['n'],v['n_segmented'],v['zero_steps'],num(v['mean'])] for m in N])
table(['Модель','Группа','n','Среднее L','Медиана','q90','Максимум'],
 [[N[m],cat,(v:=S['common'][m]['evaluation_T06'][cat])['n'],num(v['mean']),num(v['median']),num(v['q90']),v['max']] for m in N for cat in ['usable','verified','localized_tactic_failure']])
p('Дополнительно statistics.json содержит все квантили, точные гистограммы L, категории и последний доступный объём по каждой модели. У Goedel к этому снимку уже есть полная принятая сборка из 6 672 ответов; для сравнения моделей выше намеренно использованы одинаковые задачи и шарды.')
p('**4. Почему текущие траектории коротки — и почему длинная не всегда содержательная**')
table(['Модель','Блоков','Вложенных по старой метке','Среднее строк на блок','С записанным goals_before=0'],
 [[N[m],D[m]['total_steps'],percent(D[m]['structured_steps'],D[m]['total_steps']),num(D[m]['mean_lines']),D[m]['recorded_empty_goals_before']] for m in N])
p('У DeepSeek и Goedel один блок в среднем содержит около двенадцати строк. Большой have … := by скрывает последовательность вложенных действий. Но у Kimina встречается обратная проблема: множество формально допустимых повторений после закрытия целей.')
x=next(x for x in D['kimina']['longest'] if x['category']=='verified')
p(f'Конкретная принятая трасса **{x["trace_id"]}**: L={x["L"]}, из них {x["empty_goals_before"]} блоков с уже пустым списком целей. Повторяющаяся тактика — all_goals norm_num. Это не {x["L"]} содержательных математических переходов.')
p(f'У Kimina всего {D["kimina"]["recorded_empty_goals_before"]} таких записанных блоков в {D["kimina"]["empty_goal_traces"]} пригодных трассах. Их нельзя молча удалять, подбирая удобный результат. Нужно заранее ввести отдельный признак post_completion и отдельно анализировать активное доказательство и продолжение генерации.')
p(f'Описательная чувствительность: у Kimina среднее L={num(S["common"]["kimina"]["all_roles_temperatures"]["usable"]["mean"])}; если лишь для диагностики убрать {D["kimina"]["n_L_gt30"]} трасс с L>30, оно становится {num(D["kimina"]["mean_without_L_gt30"])}. Основная таблица включает эти трассы.')
p('**5. Дерево доказательства и линейная траектория модели**')
p('Текст генерируется слева направо; его префиксы образуют линейную последовательность. Логическая структура доказательства содержит вложенные подцели и ветвления. Это разные объекты. Не следует склеивать локальные цели разных ветвей в цепочку якобы одной задачи.')
p('Для Lean состояние удобно представлять как Y_t=(Γ_t,G_t,K_t): локальный контекст Γ_t, список открытых целей G_t, информация о вложенности/возврате K_t. Каждый шаг меняет это состояние. В эксперименте измеряется X_t — вектор модели на текстовом префиксе; он не тождественен Y_t.')
p('При возврате из have или переходе к другой ветви скачок X может отражать смену контекста. Поэтому к границе нужно прикреплять тип действия, родителя, глубину, локальные цели до/после и признак смены ветви. Пустой список ЛОКАЛЬНЫХ целей внутри have ещё не означает, что всё доказательство завершено.')
p('**6. Как устроен реализованный прототип**')
p('1. В неизменённом окружении Lean разбираем выражение by + тело доказательства штатным Parser.runParserCategory. Получаем AST — синтаксическое дерево — с точными диапазонами UTF-8.\n\n2. Выбираем границы из AST до выполнения доказательства. Поэтому они не зависят от будущего успеха или отказа, и текст после ошибки сохраняет границы.\n\n3. Разворачиваем вложенные последовательности под have/let, явными case, маркерами · и focus. Сохраняем parent_id и весь AST. calc, first, try, all_goals, <;> и неизвестные составные конструкции в этой версии остаются атомарными; cases … with также сохраняется целиком.\n\n4. Строим строго возрастающие окончания блоков в исходном порядке текста. Совпадающие окончания родителя и ребёнка объединяем: одно место текста не даёт двух разных состояний модели. Исходный текст восстанавливается без изменений.\n\n5. Полное доказательство передаём REPL с infotree=original и allTactics=true. Дерево выполнения добавляет контекст, но не меняет границы. Для доступных однозначных proofState повторяем тактику в сохранённом локальном состоянии.\n\n6. Сообщение ошибки, независимое воспроизведение ошибки и воспроизведение всего префикса — отдельные признаки. Неполное покрытие не объявляется точной разметкой. После кандидата на первый отказ сохраняется поглощение; события восстановления Lean не превращаются в правильные шаги.')
p('Интервалы между точками наблюдения включают вводные слова и разделители. Их нельзя напрямую исполнять как самостоятельные тактики. Для исполнения используются отдельные AST-узлы и сохранённые proofState.')
p('Связь с токенами: байтовые координаты AST переводятся в индексы символов. Перенос в оригинальный ответ разрешён только при точном совпадении тела с подстрокой completion. Если один токен пересекает выбранную границу, прототип отклоняет эту точку, а не читает текст следующего шага. Реальные токенизаторы трёх моделей в этом запуске ещё не проверялись.')
p('**7. Качество на малом наборе**')
p(f'Живой запуск Slurm {V["job_id"]}: {V["n_curated"]} контрольных конструкций, {V["n_saved"]} сохранённых ответов и {V["n_illustrative"]} ранее разобранных примера. Основная серия и генерации не изменены. Дополнительный запуск {U["job_id"]}: три короткие проверки после исправления обработки ошибок; он также проверил шесть вариантов ответа протокола.')
g=R['groups']['saved']
p(f'Синтаксические проверки контрольных конструкций прошли 17/17, включая ожидаемый отказ разбора некорректного синтаксиса. Отдельная проверка повторного исполнения контекстов выявила ограничения, описанные ниже. Для сохранённых ответов полная обработка завершилась на {g["n"]}/24: один ответ превысил 90 секунд, ещё один отклонён строгим парсером. Последний исход не означает новую ошибку модели: старый конвейер мог локализовать отказ в уже разобранном префиксе, тогда как новый прототип требует разбора всего тела.')
table(['Модель','Обработано из 8','Блоков раньше','Блоков теперь','Среднее раньше','Среднее теперь'],
 [[N[m],R['saved'][m]['n'],R['saved'][m]['old'],R['saved'][m]['new'],num(R['saved'][m]['mean_old']),num(R['saved'][m]['mean_new'])] for m in N])
p(f'На {g["n"]} обработанных ответах: {g["old_total"]} → {g["new_total"]} блоков, среднее {num(g["mean_old"])} → {num(g["mean_new"])}. Текст сохранён, вердикт полной проверки совпал с сохранённым на всех этих ответах. Отдельный контекст найден для {g["contexts"]}/{g["selected"]} выбранных узлов ({percent(g["contexts"],g["selected"])}).')
p(f'Выполнено {g["replays"]} повторов в локальных контекстах: {g["replay_ok"]} успешных; остальные исходы хранятся отдельно. Среди {g["errors"]} обработанных отвергнутых ответов координаты диагностики сопоставлены с новым узлом в {g["diagnostic_localizations"]} случаях; сам отказ воспроизведён в {g["error_reproduced"]}; отказ вместе со всем выбранным префиксом — в {g["error_and_entire_prefix_reproduced"]}. Это ограниченная проверка механизма, не оценка точности на всём датасете.')
p('Отказы повторного исполнения на сохранённой выборке: '+str(R['saved_replay_status_counts'])+'. Ошибка snapshot_kernel_rejection означает отказ проверки завершения в извлечённом снимке; она не считается ни успешным повтором, ни доказательством ошибки модели. В этих ответах встречалось сообщение kernel declaration has metavariables: снимок из InfoTree не обеспечивал полноценного воспроизведения всей доказательной зависимости. Это наблюдалось и у исходно принятых доказательств. Из 17 контрольных конструкций nested_have также выявил эту проблему при повторе завершающего exact h. Поэтому прототип пригоден как наблюдатель структуры, но его адаптер независимого повтора пока не годится как замена основного проверяющего конвейера.')
p('Выборка фиксировалась до испытания: по четыре verified и четыре localized_tactic_failure каждой модели, evaluation T=0,6, L≤30, порядок по фиксированному хешу trace_id. Она сбалансирована по исходам, исключает очень длинные хвосты и не репрезентативна для среднего по всей серии. Коэффициент учащения нельзя переносить на 20 016 ответов.')
p('В первой версии обнаружена и исправлена ошибка: отказ вида {"message": "Lean error: …"} ошибочно считался успешным, если отсутствовал список messages. Финальная версия также читает proofStatus, различает отказ тактики, ресурсное ограничение и сбой интерфейса. В отчёте использованы пересчитанные результаты. Старые сырые ответы и исходная версия сохранены для аудита.')
p('**8. Два реальных примера**')
for name in ['deepseek_sqrt','kimina_sequence']:
 row=next(r for r in C if r['name']==name)
 p(f'**{name}:** {row["old_L"]} → {row["new_L"]} точек конца блока; старый pre={row["old_t_star"]}, перед новым кандидатом pre={row["new_pre"]}. Воспроизведён отказ: {row.get("failure_reproduced")}; весь выбранный префикс: {row.get("prefix_reproduced")}.')
ks=next(r for r in U['cases'] if r['name']=='kimina_sequence')
p(f'Для Kimina последовательность из 11 крупных блоков стала 21; перед ошибочным nlinarith видно {ks["new_pre"]} внутренних действий вместо четырёх крупных блоков. Дополнительный живой запуск подтвердил и отказ, и этот префикс. В DeepSeek увеличилось число точек, но ошибка внутри <;> пока подтверждена только диагностикой полного доказательства: отдельного снимка всего комбинатора REPL не выдаёт.')
p('В HTML ниже можно выбрать доказательство и нажать на узел: подсветится исходный фрагмент, будут показаны родитель, тип узла и цели до/после. Цвет статуса не заменяет сертификат точности разметки.')
p('**9. Почему не нужно делить на всё более мелкие куски без ограничения**')
p('Для границ b_j крупное приращение равно сумме мелких: Δ_j^coarse = Σ_(t=b_(j−1)+1)^b_j Δ_t^fine. Норма суммы может быть намного меньше отдельных слагаемых из-за компенсации. Поэтому внутри большого блока может скрываться скачок. Но границы посреди выражения создают изменения, которым невозможно приписать самостоятельный смысл и вердикт Lean.')
p('Частое разбиение меняет сам наблюдаемый процесс, распределение длины, зависимость соседних измерений и задачу локализации. Оно не гарантирует тяжёлый хвост и не создаёт новых независимых задач. После смены сегментации whitening нужно заново калибровать на соответствующих verified-трассах отдельного calibration split; старую ковариацию переносить автоматически нельзя.')
p('Рекомендуемый предел частоты: явные действия в исходном тексте, для которых можно описать контекст и границу. Внутренние автоматические переписывания simp не создают новых токенов модели и не должны давать дополнительные X_t на одном и том же месте.')
p('**10. Просить модель писать линейно?**')
p('Полезно просить прозрачный стиль: одна явная тактика на строке, именованные промежуточные утверждения, явные case, без длинных цепочек ; и <;> там, где их легко раскрыть. Полностью запрещать вложенность не рекомендую: доказательства конъюнкций, индукция и разбор случаев всё равно имеют несколько целей и локальные области видимости.')
p('Более того, замена вложенного доказательства на один exact с большим термом сделает текст короче и уменьшит число наблюдений. Новый промпт меняет распределение ответов и трудность задачи для модели. Это отдельное будущее условие эксперимента, а не способ честно пересегментировать уже сгенерированные ответы.')
p('**11. Что требуется до массового применения**')
p('Нужно расширить доступ к снимкам составных тактик, поддержать неполные AST при синтаксической ошибке и локализацию ошибок в заголовке вложенного утверждения; сохранить стабильные идентификаторы целей и полную область возврата; отличать global proof_completed от закрытия локальной цели; проверить реальные токены и численное извлечение состояний. Проверки должны сравнивать тот же текст и доверенный theorem statement. Затем — отдельное заранее определённое сравнение coarse/fine с повторной калибровкой и признаками смены ветви, завершения и no-op.')
p('Прототип не был внедрён в основную серию. Никакие P1–P5 по новой сегментации не запускались. Нет статистических тестов тяжёлого хвоста на этой малой выборке.')
p('**Файлы и источники**')
p('[segmenter.py](segmenter.py), [команда экспорта AST](syntax_command.lean), [статистика и гистограммы](statistics.json), [построчные длины](block-counts.csv), [детали длинных хвостов](length-details.json), [финальные метрики проверки](review/metrics.json), [живая дополнительная проверка](validation_supplement/metrics.json).')
p('Техническая основа: [исходный код InfoTree в Lean REPL](https://github.com/leanprover-community/repl/blob/master/REPL/Lean/InfoTree.lean), [официальное описание REPL](https://github.com/leanprover-community/repl), [справочник тактик Lean](https://lean-lang.org/doc/reference/latest/Tactic-Proofs/Tactic-Reference/). Реальные проверки выполнены на закреплённом в проекте Lean v4.34.0-rc2, snapshot lean-io-v9.')
md='\n'.join(out)
(O/'REPORT_RU.md').write_text(md,encoding='utf-8')
# Lightweight standalone renderer; no CDN or external library required.
def inline(s):
 s=html.escape(s)
 s=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',s)
 s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',s)
 return s
parts=[]
for block in md.strip().split('\n\n'):
 lines=block.splitlines()
 if lines and lines[0].startswith('|'):
  cells=[[c.strip() for c in ln.strip('|').split('|')] for ln in lines]
  parts.append('<div class="scroll"><table><thead><tr>'+''.join('<th>'+inline(c)+'</th>' for c in cells[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in rr)+'</tr>' for rr in cells[2:])+'</tbody></table></div>')
 else:parts.append('<p>'+inline(block).replace('\n','<br>')+'</p>')
examples=[]
for row in C:
 if row['group'] not in ['saved','illustrative'] and row['name'] not in ['nested_have','bullets','first_backtracking','nested_failure']:continue
 r=json.loads((O/'review'/(row['name']+'.json')).read_text(encoding='utf-8'))
 examples.append(dict(name=row['name'],old=row['old_L'],new=row['new_L'],source=r['source'],nodes=r['nodes'],
                      points=r['points'],case=r['case'],diagnostics=r['diagnostics'][:3]))
data=json.dumps(examples,ensure_ascii=False).replace('<','\\u003c')
js=r"""
const data=DATA;
const sel=document.getElementById('proof');
for(let i=0;i<data.length;i++){let o=document.createElement('option');o.value=i;o.textContent=data[i].name+' · '+data[i].old+' → '+data[i].new;sel.append(o);}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function showNode(d,n){
 document.getElementById('code').innerHTML=esc(Array.from(d.source).slice(0,n.start_char).join(''))+'<mark>'+esc(Array.from(d.source).slice(n.start_char,n.end_char).join(''))+'</mark>'+esc(Array.from(d.source).slice(n.end_char).join(''));
 document.getElementById('detail').textContent=JSON.stringify({id:n.id,parent:n.parent_id,kind:n.kind,policy:n.policy,events:n.events,proof_states:n.proof_states},null,2);
}
function select(){
 const d=data[+sel.value],tree=document.getElementById('tree');tree.replaceChildren();
 document.getElementById('code').textContent=d.source;
 document.getElementById('detail').textContent='Выберите узел. Это локальные состояния Lean, а не векторы модели.';
 document.getElementById('summary').textContent=d.old+' → '+d.new+' блоков. Концы блоков дают '+(d.new+1)+' планируемых точек с X₀. Показаны исходные by + тело.';
 for(const n of d.nodes){
 let depth=0,p=n.parent_id;while(p!==null){depth++;p=d.nodes[p].parent_id;}
 const b=document.createElement('button');b.style.marginLeft=(depth*13)+'px';b.className=n.policy==='inside_atomic'?'muted':'';
 b.textContent='#'+n.id+' '+n.text.split('\n')[0].slice(0,85)+' ['+n.policy+']';b.onclick=()=>showNode(d,n);tree.append(b);
 }
}
sel.onchange=select;select();
""".replace('DATA',data)
css="body{max-width:1200px;margin:32px auto;padding:0 24px;font:17px/1.6 system-ui;color:#202b38;background:#fafafa}p{margin:20px 0}strong{color:#123652}table{border-collapse:collapse;min-width:650px;width:100%;font-size:15px}th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #d4dce2}th{background:#e8f0f5}.scroll{overflow:auto}a{color:#086dad}select{font:inherit;max-width:100%;padding:8px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}pre{white-space:pre-wrap;overflow:auto;max-height:630px;background:#edf1f4;padding:14px;font:14px/1.5 monospace}#tree{overflow:auto;max-height:630px}button{display:block;text-align:left;border:0;background:#e3edf2;margin:5px;padding:6px;cursor:pointer;max-width:95%}button.muted{color:#657783;background:#f0f0f0}mark{background:#ffe28a}@media(max-width:800px){.grid{grid-template-columns:1fr}}"
doc='<!doctype html><html lang="ru"><meta charset="utf-8"><title>Сегментация Lean — аудит и прототип</title><style>'+css+'</style><body>'+''.join(parts)+'<hr><p><strong>Просмотр дерева и исходного текста</strong></p><select id="proof"></select><p id="summary"></p><div class="grid"><div id="tree"></div><pre id="code"></pre></div><pre id="detail"></pre><script>'+js+'</script></body></html>'
(O/'REPORT_RU.html').write_text(doc,encoding='utf-8')
manifest=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job_id=os.environ.get('SLURM_JOB_ID'),files={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [O/'REPORT_RU.md',O/'REPORT_RU.html',O/'render_report.py',O/'statistics.json',O/'review/metrics.json',O/'validation_supplement/metrics.json']})
(O/'report-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('REPORT_READY',len(doc),'bytes',flush=True)
