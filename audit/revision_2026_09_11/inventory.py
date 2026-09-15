import json
from pathlib import Path
from collections import Counter
base = Path('/beegfs/home/denis.rakhmankin/onebigjump')
roots = {'deepseek': base/'runs/e1_20260908T171727Z', **{n:base/'runs/lean_all_20260909'/n for n in ('goedel','kimina')}}
report = {}
for name, root in roots.items():
    labels = [json.loads(s) for s in (root/'pilot/verification/labels.jsonl').read_text().splitlines()]
    samples = [json.loads(s) for p in (root/'pilot/generation').glob('shard-*/samples.jsonl') for s in p.read_text().splitlines()]
    by_id = {s['trace_id']:s for s in samples}
    report[name] = {'attempts':len(samples), 'categories':dict(Counter(r['category'] for r in labels)), 'whole_ok':sum(r['whole_proof_ok'] is True for r in labels), 'disagreements':sum(r['unexplained_disagreement'] for r in labels)}
    print(name, json.dumps(report[name]), flush=True)
    for row in labels:
        if row['unexplained_disagreement']:
            print('DISAGREEMENT', row['trace_id'], row['whole_proof_ok'], row['replay_ok'])
            print('BODY',row.get('body'))
            print('STEPS',json.dumps([{k:s.get(k) for k in ('tactic','status','message','goals_before','goals_after')} for s in row['steps']],ensure_ascii=False))
            print('WHOLE',json.dumps(row.get('whole_reply'),ensure_ascii=False))
    if name == 'kimina':
        print('ERRORS',Counter(r.get('error') for r in labels))
        for row in labels[:3] + labels[32:34]:
            print('KIMINA',row['trace_id'],row.get('error'))
            print('PROMPT',by_id[row['trace_id']]['prompt_content'])
            print('COMPLETION',by_id[row['trace_id']]['completion'][-6500:])
(base/'audit/revision_2026_09_11/before-metrics.json').write_text(json.dumps(report,indent=2)+'\n')
