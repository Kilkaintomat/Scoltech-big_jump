"""Denominators for localised failures on the already audited matched cohort."""
from pathlib import Path
from collections import Counter
import os
from onebigjump.e1.artifacts import read_json, write_once, finish, digest

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/label-yield-audit-v1"
PARENT=HERE/"result-8466260"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
cohort=set(read_json(PARENT/"matched-task-ids.json"))
raw=read_json(PARENT/"audited-row-summary.json")
groups={m:[r for r in rr if r["problem_id"] in cohort] for m,rr in raw.items()}
groups["all"]=[r for rr in groups.values() for r in rr]
result={}
for model, rr in groups.items():
    counts=Counter(r["category"] for r in rr)
    local=[r for r in rr if r["category"]=="localized_tactic_failure"]
    assert all(isinstance(r["t_star"],int) and 0<=r["t_star"]<r["n_steps"] for r in local)
    n=len(rr); verified=counts["verified"]; not_verified=n-verified; localized=len(local)
    terminal=counts["terminal_unsolved_goals"]
    result[model]=dict(attempts=n,verified=verified,not_verified=not_verified,localized=localized,
        verified_pct=100*verified/n,localized_pct_all=100*localized/n,
        localized_pct_nonverified=100*localized/not_verified,
        other=n-verified-localized,other_pct_all=100*(n-verified-localized)/n,
        terminal_unsolved=terminal,localized_plus_terminal_pct_all=100*(localized+terminal)/n,
        localized_plus_terminal_pct_nonverified=100*(localized+terminal)/not_verified,
        verified_plus_localized_pct=100*(verified+localized)/n,
        localized_multistep=sum(r["n_steps"]>=2 for r in local),
        localized_single_step=sum(r["n_steps"]==1 for r in local),
        localized_first_step=sum(r["t_star"]==0 for r in local),
        unexplained_disagreements=sum(r["unexplained_disagreement"] for r in rr),
        categories=dict(counts))
out=HERE/("localization-share-"+os.environ["SLURM_JOB_ID"])
metric=write_once(out/"metrics.json",dict(matched_tasks=len(cohort),groups=result,
    source_snapshot_utc=read_json(PARENT/"metrics.json")["started_utc"],
    meaning="Lean ground-truth first rejection availability, not model-state detector accuracy"))
lines=["# Доля ответов с локализованным отказом Lean","",
"| Модель | Всего | verified | Локализован отказ | % всех | % без verified | Прочие, % всех |",
"|---|---:|---:|---:|---:|---:|---:|"]
for m,s in result.items():
    lines.append(f'| {m} | {s["attempts"]} | {s["verified"]} | {s["localized"]} | {s["localized_pct_all"]:.2f}% | {s["localized_pct_nonverified"]:.2f}% | {s["other_pct_all"]:.2f}% |')
lines+=["","Категория localized_tactic_failure означает, что Lean указал первый шаг отказа. Это не показатель точности детектора по активациям.",
    "terminal_unsolved_goals учитывается отдельно. Прочие исходы включают обрывы, ограничения ресурсов, синтаксис, политику аксиом и другие исключения; их нельзя все называть ошибками математики или разметки.",
    "Метрики также содержат число одношаговых трасс и отказов на первом шаге. Наличие точки отказа ещё не означает нетривиальную задачу её предсказания."]
report=out/"REPORT.md";report.write_text("\n".join(lines)+"\n",encoding="utf-8")
finish(out,stage="localization-label-share",context=dict(parent=digest(PARENT/"manifest.json")),
    inputs=[SOURCE,PARENT/"manifest.json",Path(__file__),HERE/"localization-share.sbatch"],
    outputs=[metric,report],metrics=dict(groups=result,matched_tasks=len(cohort)))
print("RESULT",result,flush=True)
