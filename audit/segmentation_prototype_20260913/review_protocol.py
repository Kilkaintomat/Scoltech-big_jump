from pathlib import Path
import json,os,datetime,hashlib
from segmenter import replay_status
O=Path(__file__).parent
def read(name):return json.loads((O/'review'/(name+'.json')).read_text(encoding='utf-8'))
ks=read('kimina_sequence')
bad=next(r for r in ks['context_replays'] if r['node_id']==ks['fine_failure_candidate'])
assert replay_status(bad['reply'])=='error'
nested=read('nested_have')
kernel=next(r for r in nested['context_replays'] if r['source']=='exact h')
assert replay_status(kernel['reply'])=='snapshot_kernel_rejection'
first=read('first_backtracking')
assert all(replay_status(r['reply'])=='ok' for r in first['context_replays'])
assert replay_status({'message':'Unknown environment.'})=='infrastructure_error'
assert replay_status({'message':'Lean error: maximum number of heartbeats exceeded'})=='resource_error'
assert replay_status({})=='unknown_reply'
d=dict(job_id=os.environ.get('SLURM_JOB_ID'),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 passed=6,total=6,source_sha256=hashlib.sha256((O/'segmenter.py').read_bytes()).hexdigest(),
 cases=['real nested arithmetic error envelope','real incomplete snapshot kernel rejection',
 'caught backtracking is not a proof failure','invalid environment','resource limit','empty malformed reply'])
(O/'protocol-review.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
# Runnable example JSON; preserves the body used in the live supplementary check.
(O/'example-input.json').write_text(json.dumps(ks['case'],ensure_ascii=False,indent=2),encoding='utf-8')
print('PROTOCOL_REVIEW',d,flush=True)
