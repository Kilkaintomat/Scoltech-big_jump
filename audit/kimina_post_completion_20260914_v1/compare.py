"""Compare retained original-token measurements and report the separate cleaned sensitivity."""
import json
import numpy as np
import pandas as pd
from data import check_manifest
from support import *
def rate(result,key):
    value=result.get("P2",{}).get(key)
    if isinstance(value,dict):return value.get("top1")
    return value
def main():
    check_code();check_code("analysis-source-manifest.json")
    old_m=STATES/"measurement/kimina/manifest.json";old_a=STATES/"analysis/kimina/manifest.json"
    for p in [old_m,old_a,OUT/"measurement/manifest.json",OUT/"analysis/manifest.json"]:check_manifest(p)
    before=read(STATES/"analysis/kimina/primary-cell.json");after=read(OUT/"analysis/primary-cell.json")
    old=pd.read_parquet(STATES/"measurement/kimina/deviations.parquet");new=pd.read_parquet(OUT/"measurement/deviations.parquet")
    keep={r["trace_id"]:r["keep_steps"] for r in read(OUT/"preflight/masks.json")}
    a=old[(old.statistic=="raw")&(old.t<old.trace_id.map(keep))].sort_values(["trace_id","t"]).reset_index(drop=True)
    b=new[new.statistic=="raw"].sort_values(["trace_id","t"]).reset_index(drop=True)
    columns=["trace_id","prompt_id","t","L","z","surprisal","valid","t_star","status","outcome","role","temperature","category"]
    a=a.copy();a["L"]=a.trace_id.map(keep)
    pd.testing.assert_frame_equal(a[columns],b[columns],check_dtype=False,check_exact=True)
    q=read(OUT/"preflight/metrics.json");out=OUT/"comparison";out.mkdir(exist_ok=False)
    metrics={"scope":"structural sensitivity, no model regeneration or changed verdicts",
       "retained_raw_values_surprisal_and_labels_identical":True,"refuted_traces_changed":0,
       "before":{"P1":before["P1"],"P2":before["P2"],"P3":before["P3"],"task_bootstrap":before["task_bootstrap"]},
       "after":{"P1":after["P1"],"P2":after["P2"],"P3":after["P3"],"task_bootstrap":after["task_bootstrap"]},
       "cleanup":q,"generation_calls":0,"model_forward_calls":0,"decision":"sensitivity results; assess effects and intervals, no automatic confirmation"}
    atomic(out/"comparison.json",finite(metrics))
    def fmt(x):return "NA" if x is None else f"{100*x:.2f}%"
    lines=["# Kimina: контроль хвостов после закрытия цели","",
      f"Удалены только терминальные post_completion: {q['removed_steps']} наблюдений из {q['trimmed_traces']} принятых трасс.",
      "Общий вердикт доказательств, исходные токены, позиции ошибок и все ошибочные трассы сохранены.",
      "Whitening переоценён отдельно по температурам на очищенных принятых калибровочных трассах. Пороги P3 пересчитаны из очищенных значений.",
      "Это дополнительная структурная чувствительность. Она не заменяет исходный анализ и не является новой независимой подтверждающей проверкой.","",
      "| Срез | Трасс P2 | Задач P2 | Максимум на ошибке | Surprisal | Случайный уровень |",
      "|---|---:|---:|---:|---:|---:|"]
    for name,result in [("Исходная сегментация",before),("Без post_completion",after)]:
        p=result["P2"];lines.append(f"| {name} | {p.get('n_traces')} | {p.get('n_tasks')} | {fmt(rate(result,'jump'))} | {fmt(rate(result,'surprisal'))} | {fmt(p.get('chance'))} |")
    lines += ["","Сравнение сохранённых raw-значений, surprisal и меток на всех оставшихся наблюдениях прошло точную проверку равенства.",
      "Изменение локализации в ошибочных трассах после очистки связано с переоценкой преобразования, поскольку сами эти трассы не обрезались.",
      "Все три оценки хвостового индекса, парные интервалы по задачам, пороги и результаты P3 сохранены в comparison.json. Позиционные контроли нового среза — в analysis/positional-controls.json.",
      "Преобразование фиксировано внутри bootstrap; использование одной калибровки для преобразования и порога остаётся ограничением. Рассматривать нужно размеры эффектов, неопределённость и согласованность с позиционным нулём."]
    report=out/"REPORT_RU.md";report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    finish(out,{"comparison_complete":True,"raw_and_surprisal_identical":True,"decision":"sensitivity"},[
      HERE/"analysis-source-manifest.json",old_m,old_a,OUT/"measurement/manifest.json",OUT/"analysis/manifest.json",
      OUT/"preflight/manifest.json"],[out/"comparison.json",report])
    print("COMPARISON READY",str(out),flush=True)
def finite(x):
    from onebigjump.e1.analysis import finite_json
    return finite_json(x)
if __name__=="__main__":main()
