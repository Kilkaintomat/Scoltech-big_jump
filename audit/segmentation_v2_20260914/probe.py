import json,os
from pathlib import Path
from onebigjump.lean import LeanREPL,discover
from segmenter import Segmenter
O=Path(__file__).parent
cases=json.loads((O/'curated.json').read_text(encoding='utf-8'))
cases=[c for c in cases if c['name'] in ['nested_have','bullets','nested_failure','calc','cases','first_backtracking']]
cases.append({'name':'post_completion','header':'example : True := by','body':'\n  trivial\n  all_goals trivial\n  all_goals trivial\n'})
out=[]
with LeanREPL(discover(),imports='import Mathlib\nimport Aesop',startup_attempts=1,default_timeout_s=60,drain_timeout_s=10) as repl:
 s=Segmenter(repl)
 for c in cases:
  r=s.inspect(c['header'],c['body']);s.replay_frontier(r)
  def walk(t):
   n=t.get('node') or {}
   if t.get('kind')=='TacticInfo':
    st=n.get('stx',{})
    out.append({'case':c['name'],'kind':st.get('kind'),'range':st.get('range'),'before':n.get('goalIdsBefore'),'after':n.get('goalIdsAfter'),'roots_before':n.get('rootGoalsBefore'),'roots_after':n.get('rootGoalsAfter')})
   for x in t.get('children',[]):walk(x)
  for t in r.get('whole_reply',{}).get('infotree',[]):walk(t)
  (O/('probe-'+c['name']+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
  print(c['name'],[n['kind'] for n in r.get('nodes',[])],[(x['source'],x['status'],x['reply'].get('proofStatus')) for x in r.get('context_replays',[])],flush=True)
(O/'probe-events.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
