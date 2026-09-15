from pathlib import Path
import json,hashlib,os,time,traceback,collections
import numpy as np
from transformers import AutoTokenizer
from onebigjump.lean import LeanREPL,discover
from segmenter_v2 import SegmenterV2,align_original,reuse_plan
from segmenter import reconstruct,errors
O=Path(__file__).parent;ROOT=O.parents[2];dest=O/'validation';dest.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
saved=read(O/'sample.json');started=time.monotonic()
# Reuse the same 24 frozen generations retrieved by the initial bounded job.
samples={(x['model'],x['trace_id']):x for x in read(O/'frozen-generations-small.json')}
tokenizers={}
for model in ['deepseek','goedel','kimina']:
 protocol=read(ROOT/'runs/lean_reverification_20260913_local'/model/'main/protocol.json')
 tokenizers[model]=AutoTokenizer.from_pretrained(protocol['model_path'],local_files_only=True)
cases=read(O/'curated.json')
for c in cases:
 c['group']='curated'
 if c['name'] in ['calc','cases']:c['expected_points']=2
cases.extend([
 {'group':'curated','name':'post_completion','header':'example : True := by','body':'\n  trivial\n  all_goals trivial\n  all_goals trivial\n','expected_ok':True,'expected_points':3,'expected_post_completion':2},
 {'group':'curated','name':'branch_failure','header':'example : True ∧ True := by','body':'\n  constructor\n  · trivial\n  · exact bad_missing_name\n','expected_ok':False,'expected_failure':'exact bad_missing_name','expected_pre':2},
 {'group':'curated','name':'cases_failure','header':'example (P Q : Prop) (h : P ∨ Q) : Q ∨ P := by','body':'\n  cases h with\n  | inl p => exact Or.inr p\n  | inr q => exact bad_missing_name\n','expected_ok':False,'expected_points':2,'expected_failure':'exact bad_missing_name','expected_pre':1},
 {'group':'curated','name':'calc_failure','header':'example (a b c : Nat) (h1 : a=b) (h2 : b=c) : a=c := by','body':'\n  calc\n    a = b := h1\n    _ = c := bad_missing_name\n','expected_ok':False,'expected_points':2,'expect_diagnostic_only':True},
 {'group':'curated','name':'nested_noop_not_global','header':'example : True := by','body':'\n  have h : True := by\n    trivial\n    all_goals trivial\n  exact h\n','expected_ok':True,'expected_points':3,'expected_post_completion':0},
 {'group':'curated','name':'try_swallowed','header':'example : True := by','body':'\n  try exact bad_missing_name\n  trivial\n','expected_ok':True,'expected_points':2},
 {'group':'curated','name':'cases_three_steps','header':'example (P Q : Prop) (h : P ∨ Q) : Q ∨ P := by','body':'\n  cases h with\n  | inl p =>\n    skip\n    exact Or.inr p\n  | inr q =>\n    skip\n    exact Or.inl q\n','expected_ok':True,'expected_points':4},
 {'group':'curated','name':'inline_comments','header':'example : True := by','body':' trivial -- comment 😀\n','expected_ok':True,'expected_points':1},
])
cases.extend([
 {'group':'curated','name':'failure_after_completion','header':'example : True := by','body':'\n  trivial\n  exact bad_missing_name\n','expected_ok':False,'expected_points':2,'expected_failure':'exact bad_missing_name','expected_pre':1},
 {'group':'curated','name':'replay_source_with_goal_and_comment','header':'example (a : Nat) (h : a = a) : a = a := by','body':'\n  ring_nf at h ⊢\n  -- explanation\n  rfl\n','expected_ok':True,'expected_points':2},
])
for i,r in enumerate(saved):
 cases.append({'group':'saved','name':f'saved_{i:02d}_{r["model"]}','model':r['model'],'trace_id':r['trace_id'],
               'header':r['replay']['header'],'body':r['body'],'expected_ok':r['category']=='verified','old_L':len(r['steps']),'label':r})
results=[]
with LeanREPL(discover(),imports='import Mathlib\nimport Aesop',default_timeout_s=90,startup_attempts=1,drain_timeout_s=10) as repl:
 s=SegmenterV2(repl)
 for c in cases:
  tick=time.monotonic();row={k:v for k,v in c.items() if k not in ['header','body','label']}
  checks={}
  try:
   r=s.inspect(c['header'],c['body'],c.get('trace_id',c['name']))
   row['parse_ok']=r['parse_ok']
   if c.get('expected_parse') is False:
    checks['expected_parse_error']=not r['parse_ok']
   elif r['parse_ok']:
    checks['lossless']=reconstruct(r)==r['source']
    checks['original_body']=r['source'][2:]==c['body']
    checks['whole_verdict']=r['whole_elaboration_ok']==c['expected_ok']
    checks['ordered_distinct_endpoints']=all(a['end_char']<b['end_char'] for a,b in zip(r['points'],r['points'][1:]))
    checks['tree_containment']=all(n['parent_id'] is None or r['nodes'][n['parent_id']]['start_char']<=n['start_char']<n['end_char']<=r['nodes'][n['parent_id']]['end_char'] for n in r['nodes'])
    plain=s.parse(c['body']);checks['outcome_independent_points']=[x['end_char'] for x in plain['points']]==[x['end_char'] for x in r['points']]
    replays=s.replay_frontier(r,limit=100)
    row.update(new_L=r['n_blocks'],whole_ok=r['whole_elaboration_ok'],n_replays=len(replays),
               replay_status_counts=dict(collections.Counter(x['status'] for x in replays)),
               localization_status=r['localization_status'],annotation_ready=r['annotation_ready'],
               n_post_completion=sum(p['execution_status']=='post_completion' for p in r['points']),
               n_inactive_local=sum(p['execution_status']=='inactive_local_context' for p in r['points']),
               n_native_context=sum(bool(p.get('event_ids')) for p in r['points']),
               n_pre=sum(p['trace_label']=='pre' for p in r['points']))
    if 'expected_points' in c:checks['point_count']=r['n_blocks']==c['expected_points']
    if 'expected_post_completion' in c:checks['post_completion']=row['n_post_completion']==c['expected_post_completion']
    if c['name'] in ['nested_have','bullets']:
     checks['local_completion_not_global']=any(p['transition']=='closes_local_goals' and p['root_pending_after'] for p in r['points'])
     checks['last_step_completes_root']=r['points'][-1]['transition']=='completes_root'
     checks['local_replays_accepted']=all(x['status']=='ok' for x in replays)
    if c.get('expected_failure'):
     f=r['fine_failure_candidate']
     checks['correct_failure']=f is not None and r['nodes'][f]['text']==c['expected_failure']
     checks['prefix_and_error_reproduced']=r['localization_status']=='prefix_and_failure_reproduced'
     checks['pre_count']=row['n_pre']==c['expected_pre']
     checks['absorbing_labels']=all(p.get('absorbing_unreached') for p in r['points'] if p['trace_label']=='post')
    if c.get('expect_diagnostic_only'):checks['term_error_not_promoted_to_replayed']=r['localization_status']=='diagnostic_only'
    if c['name'] in ['cases','cases_three_steps','bullets','explicit_case']:
     paths={tuple(p['branch_path']) for p in r['points'] if p['branch_path']}
     checks['separate_branch_paths']=len(paths)==2
     checks['branch_switch_detected']=any(p['source_transition']['branch_switch'] for p in r['points'])
    if c['name']=='replay_source_with_goal_and_comment':
     checks['source_replay_success']=all(x['status']=='ok' for x in replays)
    if c['name']=='failure_after_completion':
     checks['error_not_hidden_by_closed_goal']=r['points'][-1]['trace_label']=='at'
    if c['group']=='saved':
     label=c['label'];sample=samples[(c['model'],c['trace_id'])]
     alignment=align_original(r,tokenizers[c['model']],sample,label['body_start'])
     r['reuse_plan']=reuse_plan(r,sample,label)
     row.update(n_aligned=len(alignment['observations']),n_exact=sum(p['boundary_kind']=='exact' for p in alignment['observations']),
                n_whitespace=sum(p['boundary_kind']=='trailing_whitespace' for p in alignment['observations']),
                n_crossing_code=len(alignment['rejected']),n_latent_points=alignment['n_latent_points'])
     checks['generation_reused_unchanged']=r['reuse_plan']['already_generated_answer_unchanged']
     checks['token_positions_strict']=all(a<b for a,b in zip(alignment['positions'],alignment['positions'][1:]))
     checks['no_future_code']=all(x['trailing_whitespace_bytes']==0 or sample['completion'].encode('utf-8')[x['semantic_end_byte']:x['token_end_byte']].strip()==b'' for x in alignment['observations'])
     # A localization certificate also requires the error observation to be representable by tokens.
     row['localized_error_has_token']=any(x['trace_label']=='at' for x in alignment['observations'])
     row['p2_label_and_alignment_ready']=r['localization_status']=='prefix_and_failure_reproduced' and row['localized_error_has_token']
   else:
    row['parse_error_kind']='original_source_not_parsable';checks['parse_ok']=False
   r['case']={k:v for k,v in c.items() if k!='label'};write(dest/('case--'+c['name']+'.json'),r)
  except Exception as ex:
   row.update(exception=repr(ex),traceback=traceback.format_exc());checks['no_exception']=False
   if isinstance(ex,TimeoutError):repl.restart();s=SegmenterV2(repl)
  row['checks']=checks;row['checks_passed']=all(checks.values());row['elapsed_s']=time.monotonic()-tick
  results.append(row);write(dest/'cases-summary.json',results)
  print('CASE',c['name'],json.dumps({k:v for k,v in row.items() if k not in ['traceback']},ensure_ascii=True),flush=True)
summary={'job':os.environ['SLURM_JOB_ID'],'elapsed_s':time.monotonic()-started,'n_cases':len(results),
         'n_curated':sum(r['group']=='curated' for r in results),'n_saved':24,
         'n_passed':sum(r['checks_passed'] for r in results),'new_generation':False,'new_model_forward':False,
         'production_changed':False,'observer_binary_sha256':hashlib.sha256((O/'repl-observer').read_bytes()).hexdigest(),
         'groups':{}}
for group in ['curated','saved']:
 rs=[r for r in results if r['group']==group];good=[r for r in rs if r.get('new_L') is not None]
 totals=collections.Counter()
 for r in good:totals.update(r['replay_status_counts'])
 summary['groups'][group]={'n':len(rs),'processed':len(good),'passed':sum(r['checks_passed'] for r in rs),
  'old_L_total':sum(r.get('old_L',0) for r in good),'new_L_total':sum(r['new_L'] for r in good),
  'replay_status_counts':dict(totals),'n_post_completion':sum(r['n_post_completion'] for r in good),
  'n_aligned':sum(r.get('n_aligned',0) for r in good),'n_exact':sum(r.get('n_exact',0) for r in good),
  'n_whitespace':sum(r.get('n_whitespace',0) for r in good),'n_crossing_code':sum(r.get('n_crossing_code',0) for r in good),
  'p2_label_and_alignment_ready':sum(r.get('p2_label_and_alignment_ready',False) for r in good)}
write(dest/'metrics.json',summary)
write(dest/'manifest.json',{'job':os.environ['SLURM_JOB_ID'],'files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [O/'segmenter.py',O/'segmenter_v2.py',O/'validate_v2.py',O/'sample.json',O/'runtime-manifest.json',*dest.glob('*.json')] if p.name!='manifest.json'}})
print('SUMMARY',json.dumps(summary,indent=2),flush=True)
