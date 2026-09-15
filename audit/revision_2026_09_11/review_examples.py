"""Select actual development traces for human-readable audit; retain every disagreement."""
import json
import os
from pathlib import Path
from onebigjump.e1.artifacts import finish, verify_manifest, write_once
from onebigjump.e1.stages import rows

base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
source=Path((base/'audit/revision_2026_09_11/snapshot-path.txt').read_text().strip())
for model in ('deepseek','goedel','kimina'):
    root=Path(os.environ.get('E1_REVIEW_ROOT', str(base/'runs/lean_recovery_20260911_v2')))/model
    old_root=base/'runs/lean_all_20260909'/model
    man=root/'pilot/verification/manifest.json'
    if not man.exists(): continue
    out=root/'pilot/review'
    if (out/'manifest.json').exists(): continue
    verify_manifest(man)
    labels=rows(man.parent/'labels.jsonl')
    old={r['trace_id']:r for r in rows(old_root/'pilot/verification/labels.jsonl')}
    picked=[]
    groups={}
    for r in labels:
        groups.setdefault(r['category'],[]).append(r)
    for group in groups.values():
        picked.extend(group[:max(1,12//len(groups))])
    for r in labels:
        if (len(picked)<12 or old[r['trace_id']]['unexplained_disagreement'] or r['unexplained_disagreement']) and r not in picked:
            picked.append(r)
    records=[]
    for r in picked:
        fail=r.get('t_star')
        records.append({'trace_id':r['trace_id'],'category':r['category'],'old_category':old[r['trace_id']]['category'],
        'whole_ok':r['whole_proof_ok'],'replay_ok':r['replay_ok'],'disagreement':r['unexplained_disagreement'],
        'old_disagreement':old[r['trace_id']]['unexplained_disagreement'],'n_steps':len(r['steps']),'t_star':fail,
        'error':r.get('error'),'whole_errors':[m.get('data') for m in r.get('whole_reply',{}).get('messages',[]) if m.get('severity')=='error'],
        'first_rejected_step':r['steps'][fail] if fail is not None else None,
        'body':r.get('body'),'step_statuses':[s['status'] for s in r['steps']], 'axioms':r.get('axioms')})
    path=write_once(out/'examples.json',records)
    finish(out,stage='actual-pilot-review-packet',context={'model':model},inputs=[source/'source-manifest.json',man,old_root/'pilot/verification/manifest.json'],outputs=[path],metrics={'selected':len(records),'manual_review':'pending'})
    print(model,len(records),path,flush=True)
