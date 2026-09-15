"""Mechanistic audit of saved independent P3 validation. No refitting or promotion."""
from pathlib import Path
from collections import Counter
import os
import numpy as np
from onebigjump.e1.artifacts import read_json,write_once,finish,digest
from onebigjump.e1.stages import rows
from onebigjump.readiness.p3_validation import proportion
base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
root=base/"runs/p3_validation_20260913"
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
out=base/"audit/revision_2026_09_13"/(os.environ["SLURM_JOB_ID"]+"-p3-availability")
config=read_json(root/"protocol.json")
mans=sorted(root.glob("shard-*/manifest.json"))
records=[r for m in mans for r in rows(m.parent/"replicates.jsonl")]
expected={f"{name}:{i}" for name in config["scenarios"] for i in range(config["datasets"])}
assert len(records)==len(expected) and {r["trace_id"] for r in records}==expected
def reasons(c):
 p=c["percentile"];result=[]
 for k,threshold in [("calibration_tail_tasks",10),("calibration_excesses",20),("failure_tail_tasks",20),("failure_excesses",50)]:
  if c[k]<threshold:result.append(k+" below "+str(threshold))
 if p["n_tasks"]<config["statistics"]["min_tasks"]:result.append("too few independent tasks")
 if not p["replicates"] or p["valid"]/p["replicates"]<config["statistics"]["valid_fraction"]:result.append("too few finite bootstrap fits")
 return result
def cell_summary(sample,candidate,kind):
 available=[r for r in sample if r["methods"][candidate][kind]["ci95"] is not None]
 intervals=[(r,r["methods"][candidate][kind]["ci95"]) for r in available]
 return {"datasets":len(sample),"availability":proportion([r in available for r in sample]),
  "coverage":proportion([lo<=r["truth"]<=hi for r,(lo,hi) in intervals]),
  "miss_below_truth":sum(hi<r["truth"] for r,(lo,hi) in intervals),
  "miss_above_truth":sum(lo>r["truth"] for r,(lo,hi) in intervals),
  "mean_bias":float(np.mean([r["methods"][candidate]["point"]-r["truth"] for r in available])) if available else None}
output={};detailed=[];mismatch=[]
for scenario in config["scenarios"]:
 sample=[r for r in records if r["request"]["scenario"]==scenario]
 item={"methods":{}}
 for candidate in ["original","observed_support"]:
  causes=Counter();sets=Counter()
  for r in sample:
   c=r["methods"][candidate];why=reasons(c);avail=c["percentile"]["ci95"] is not None
   if avail==bool(why):mismatch.append([r["trace_id"],candidate,why])
   if not avail:causes.update(why);sets["; ".join(why)]+=1
   detailed.append({"trace_id":r["trace_id"],"candidate":candidate,"available":avail,"reasons":why,
                   "threshold_below_true_support":c["threshold"]<r["true_support_diagnostic_only"],
                   "saved_reason":c["percentile"]["reason"]})
  item["methods"][candidate]={"unavailable_reasons_overlap":dict(causes),"exclusive_reason_sets":dict(sets),"intervals":{}}
  for kind in ["percentile","basic"]:
   strata={}
   for name,subset in [
    ("all",sample),
    ("threshold_below_support",[r for r in sample if r["methods"][candidate]["threshold"]<r["true_support_diagnostic_only"]]),
    ("threshold_at_or_above_support",[r for r in sample if r["methods"][candidate]["threshold"]>=r["true_support_diagnostic_only"]])]:
    strata[name]=cell_summary(subset,candidate,kind)
   item["methods"][candidate]["intervals"][kind]=strata
 paired={}
 for kind in ["percentile","basic"]:
  common=[r for r in sample if all(r["methods"][c][kind]["ci95"] is not None for c in ["original","observed_support"])]
  lost=[r for r in sample if r["methods"]["original"][kind]["ci95"] is not None and r["methods"]["observed_support"][kind]["ci95"] is None]
  def covers(r,c):
   interval=r["methods"][c][kind]["ci95"]
   return interval is not None and interval[0]<=r["truth"]<=interval[1]
  paired[kind]={"common":len(common),"lost":len(lost),
    "original_common":cell_summary(common,"original",kind),
    "candidate_common":cell_summary(common,"observed_support",kind),
    "gains":sum(not covers(r,"original") and covers(r,"observed_support") for r in common),
    "losses":sum(covers(r,"original") and not covers(r,"observed_support") for r in common),
    "lost_original_covered":sum(covers(r,"original") for r in lost)}
 item["paired"]=paired;output[scenario]=item
metrics={"datasets":len(records),"source_of_data":"all saved independent validation replicates; no regeneration or re-estimation",
 "availability_rule_mismatches":mismatch,"scenarios":output,"main_method_changed":False,
 "interpretation":"Descriptive post-validation mechanism audit. Subgroup patterns are diagnostic, not a new independent calibration claim. Oracle support is only used to label diagnostic strata.",
 "next_protocol":"Any proposed repair needs a frozen method and a new independent seed; retain all availability requirements, report both conditional and unconditional coverage."}
a=write_once(out/"metrics.json",metrics);b=write_once(out/"reasons.json",detailed)
lines=["# P3: почему пропадают интервалы и где возникает недопокрытие",
 f"Проверены все {len(records)} сохранённых наборов. Метод, пороги и исходные интервалы не изменялись.",
 "Причины ниже рассчитаны по всем исходным критериям достаточности. Строка reason в старом файле могла оставаться общей даже после исключения интервала по размеру хвоста.",
 "| Сценарий | Метод | Доступно | Покрыто среди доступных | Интервал ниже истины | Выше истины |",
 "|---|---|---:|---:|---:|---:|"]
for scenario,item in output.items():
 for candidate,data in item["methods"].items():
  for kind,strata in data["intervals"].items():
   c=strata["all"];av=c["availability"];cov=c["coverage"]
   lines.append(f"| {scenario} | {candidate} {kind} | {av['successes']}/{av['datasets']} | {cov['successes']}/{cov['datasets']} | {c['miss_below_truth']} | {c['miss_above_truth']} |")
  lines.append("")
  lines.append(f"{scenario}, {candidate}: причины недоступности — {data['exclusive_reason_sets']}.")
lines += ["","Полная разбивка по положению порога относительно известной границы поддержки, смещению и парным исходам находится в metrics.json. Эта разбивка описательная: её нельзя выдавать за новую независимую валидацию.",
 "Кандидат нельзя продвигать только по условному покрытию; нужно учитывать недоступные интервалы и общую парную выборку."]
report=out/"REPORT.md";report.write_text("\n".join(lines)+"\n",encoding="utf-8")
finish(out,stage="p3-saved-validation-availability-mechanisms",context={"source":digest(source)},
 inputs=[source,Path(__file__),root/"protocol.json",*mans],outputs=[a,b,report],metrics=metrics)
assert not mismatch
print("P3_AVAILABILITY_AUDIT",out,flush=True)
