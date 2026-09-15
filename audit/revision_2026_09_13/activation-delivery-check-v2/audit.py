"""Audit completed activation artifacts without changing any experiment."""
from pathlib import Path
from collections import Counter
import json, os, datetime
import numpy as np
from onebigjump.e1.artifacts import digest, identity, read_json, write_once, finish

BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/activation-delivery-check-v2"
OUT=HERE/("result-"+os.environ["SLURM_JOB_ID"])
ROOT=BASE/"runs/lean_reverification_20260913_local"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"

def checked_rows(path):
    result=[]
    with path.open(encoding="utf-8") as f:
        for line in f:
            r=json.loads(line)
            expected=r.pop("row_sha256")
            assert identity(r)==expected,("row digest",path,r.get("trace_id"))
            r["row_sha256"]=expected
            result.append(r)
    assert len({r["trace_id"] for r in result})==len(result)
    return result

def main():
    OUT.mkdir()
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    inventory=read_json(HERE/"inventory.json")
    inputs=[Path(__file__),HERE/"inventory.json",HERE/"audit.sbatch",SOURCE]
    labels={}
    summary=[]
    seen=set()
    dimensions={}
    for item in inventory:
        model=item["model"]
        p=Path(item["manifest"])
        assert digest(p)==item["sha256"]
        meta=read_json(p)
        inputs.append(p)
        output_digests={str(Path(k).resolve()):v for k,v in meta["outputs"].items()}
        if model not in labels:
            lm=ROOT/model/"main/verification/manifest.json"
            lv=ROOT/model/"main/verification/labels.jsonl"
            label_outputs={str(Path(k).resolve()):v for k,v in read_json(lm)["outputs"].items()}
            assert digest(lv)==label_outputs[str(lv.resolve())]
            labels[model]={r["trace_id"]:r for r in checked_rows(lv)}
            inputs.append(lm)
        rows=checked_rows(p.parent/"trajectories.jsonl")
        assert len(rows)==meta["metrics"]["attempts"]
        for name,sha in meta["outputs"].items():
            assert digest(name)==sha,("output digest",name)
        statuses=Counter();cats=Counter();checked_forward=0;arrays_checked=0
        means=[]
        for r in rows:
            key=(model,r["trace_id"]);assert key not in seen;seen.add(key)
            label=labels[model][r["trace_id"]]
            for key in ["category","problem_id","role","temperature","request_sha256"]:
                assert r[key]==label[key],(key,r["trace_id"])
            statuses[r["extraction_status"]]+=1
            if r["extraction_status"]!="extracted":continue
            cats[r["category"]]+=1
            n=r["n_steps"]
            assert n==len(label["steps"])
            positions=r["alignment"]["positions"]
            assert len(positions)==n+1 and all(a<b for a,b in zip(positions,positions[1:]))
            assert 0<=positions[0] and positions[-1]<r["alignment"]["n_tokens"]
            spans=r["alignment"]["step_token_spans_inclusive"]
            assert len(spans)==n
            assert all(0<=lo<=hi==positions[j+1] for j,(lo,hi) in enumerate(spans))
            assert r["states_sha256"]==output_digests[str(Path(r["states_path"]).resolve())]
            with np.load(r["states_path"],allow_pickle=False) as data:
                state_keys=[k for k in data.files if k.startswith("states_")]
                assert len(state_keys)==3
                for k in state_keys:
                    a=data[k]
                    assert a.ndim==2 and a.shape[0]==n+1 and np.isfinite(a).all()
                    shape_key=(model,k)
                    if shape_key in dimensions:assert dimensions[shape_key]==a.shape[1]
                    dimensions[shape_key]=a.shape[1]
                    arrays_checked+=1
                assert data["surprisal"].shape==(n,) and np.isfinite(data["surprisal"]).all()
                arrays_checked+=1
            for check in r.get("forward_check",{}).values():
                assert check["passed"] and np.isfinite(check["max_abs_error"])
                checked_forward+=1
            comparison=r["backend_logprob_comparison"]
            assert comparison["n"]>0 and np.isfinite(comparison["mean_abs_error"])
            means.append(comparison["mean_abs_error"])
        assert statuses["extracted"]==meta["metrics"]["extracted"]
        summary.append(dict(model=model,shard=p.parent.name,attempts=len(rows),
            statuses=dict(statuses),extracted_categories=dict(cats),arrays_checked=arrays_checked,
            independent_forward_checks=checked_forward,
            backend_mean_absolute_error_trace_median=float(np.median(means)),
            backend_mean_absolute_error_trace_max=float(np.max(means))))
        print("SHARD_CHECKED",summary[-1],flush=True)
    metrics=dict(passed=True,started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        shards=summary,attempts=sum(s["attempts"] for s in summary),
        extracted=sum(s["statuses"].get("extracted",0) for s in summary),
        limitations=["Only completed shards frozen in inventory are covered.",
          "Artifact integrity and alignment do not establish the scientific hypothesis.",
          "Generation and teacher-forced backends are not claimed to be bitwise identical."],
        main_jobs_changed=False,main_artifacts_changed=False)
    m=write_once(OUT/"metrics.json",metrics)
    text=["# Проверка первых сохранённых активаций","",
        "Проверены контрольные суммы файлов, идентичность записей и соответствие разметке, размеры и конечность массивов, позиции шагов и результаты независимого forward-контроля.","",
        "| Модель | Порция | Учтено ответов | С активациями | Проверок слоёв независимым forward |",
        "|---|---|---:|---:|---:|"]
    for s in summary:
        text.append(f'| {s["model"]} | {s["shard"]} | {s["attempts"]} | {s["statuses"].get("extracted",0)} | {s["independent_forward_checks"]} |')
    text.extend(["","Исключённые ответы сохранены отдельными записями; они не потеряны при извлечении.","",
        "Проверка относится к указанным завершённым порциям. Она не заменяет основной анализ и не подтверждает гипотезу о локализации ошибок скачками активаций."])
    report=OUT/"REPORT.md";report.write_text("\n".join(text)+"\n",encoding="utf-8")
    finish(OUT,stage="completed-activation-artifact-audit",context={"source":digest(SOURCE)},
        inputs=inputs,outputs=[m,report],metrics=metrics)
    print("AUDIT_COMPLETE",metrics["attempts"],metrics["extracted"],flush=True)

if __name__=="__main__":main()
