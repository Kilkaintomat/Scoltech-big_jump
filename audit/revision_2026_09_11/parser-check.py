import os
from collections import Counter
from pathlib import Path
from onebigjump.e1.artifacts import finish, read_json, write_once
from onebigjump.e1.spans import formal_body, SourceExclusion
from onebigjump.e1.stages import generation_inputs, rows
from onebigjump.e1.verification import trusted_prefix

base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
source=Path(os.environ['E1_SNAPSHOT'])/'source-manifest.json'
metrics={}
inputs=[source,Path(__file__)]
for model in ('deepseek','goedel','kimina'):
    root=base/'runs/lean_all_20260909'/model
    samples,manifests=generation_inputs(root,'pilot')
    previous={r['trace_id']:r for r in rows(root/'pilot/verification/labels.jsonl')}
    problems={r['problem_id']:r for r in read_json(root/'inputs/problems.json')}
    config=read_json(root/'pilot/protocol.json')
    counts=Counter(); preserved=0
    for sample in samples:
        old=previous[sample['trace_id']]
        problem=problems[sample['problem_id']]
        try:
            parsed=formal_body(sample['completion'],problem['statement'],trusted_prefix(problem,config['lean']['max_heartbeats']))
            counts['parsed']+=1
            if old.get('body') is not None and model in ('deepseek','goedel'):
                assert parsed['body']==old['body'], 'changed previously extracted proof body: '+sample['trace_id']
                preserved+=1
        except SourceExclusion as exc:
            counts[exc.category]+=1
            assert old['category'] not in ('verified','localized_tactic_failure','unsupported_segmentation'), 'lost formerly parsed proof: '+sample['trace_id']
    metrics[model]={'attempts':len(samples),'counts':dict(counts),'previous_bodies_preserved':preserved}
    inputs.extend(manifests+[root/'pilot/verification/manifest.json'])
    print(model,metrics[model],flush=True)
out=base/'audit/revision_2026_09_11'/('parser-'+os.environ['SLURM_JOB_ID'])
path=write_once(out/'metrics.json',metrics)
finish(out,stage='real-completion-parser-regression',context={},inputs=inputs,outputs=[path],metrics={'passed':True,'models':metrics})
