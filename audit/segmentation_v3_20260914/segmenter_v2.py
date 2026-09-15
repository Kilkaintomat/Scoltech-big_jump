"""Hierarchy-aware observations for unchanged Lean source (prototype v2).
One source segmentation, separate elaboration tree, original-token mapping.
This is an adapter; existing trusted whole-proof verification remains authoritative.
"""
from __future__ import annotations
import hashlib,json
from bisect import bisect_left
from pathlib import Path
import segmenter as base
from onebigjump.e1.spans import original_token_spans

def digest_text(x):return hashlib.sha256(x.encode('utf-8')).hexdigest()
def root_closed(rows):
    return isinstance(rows,list) and bool(rows) and all(r.get('assigned') and not r.get('containsMVar') and not r.get('containsSorry') for r in rows)
def pending(rows):
    return sorted({g for r in rows for g in r.get('pendingIds',[])}) if isinstance(rows,list) else None

def attach_semantics(result,header,reply,trace_id=""):
    if not result.get('parse_ok'):return result
    source=header+result['source'][2:];shift=len(header)-2
    native=[]
    def walk(t,parent=None):
        n=t.get('node') or {}; st=n.get('stx') or {};r=st.get('range');ep=parent
        if t.get('kind')=='TacticInfo' and r and not r.get('synthetic'):
            try:a=base.position_char(source,r['start'])-shift;b=base.position_char(source,r['finish'])-shift
            except ValueError:a=b=-1
            e={'id':len(native),'parent_event_id':parent,'kind':st.get('kind'),'start_char':a,'end_char':b,
               'goal_ids_before':n.get('goalIdsBefore'),'goal_ids_after':n.get('goalIdsAfter'),
               'root_before':n.get('rootGoalsBefore'),'root_after':n.get('rootGoalsAfter')}
            native.append(e);ep=e['id']
        for ch in t.get('children',[]):walk(ch,ep)
    for tree in reply.get('infotree',[]):walk(tree)
    by={}
    for e in native:by.setdefault((e['start_char'],e['end_char'],e['kind']),[]).append(e)
    nodes=result['nodes']
    for n in nodes:
        n['native_events']=by.get((n['start_char'],n['end_char'],n['kind']),[])
        path=[];p=n['parent_id']
        while p is not None:
            path.append(p);p=nodes[p]['parent_id']
        n['ancestor_ids']=list(reversed(path))
        n['branch_path']=[i for i in n['ancestor_ids'] if nodes[i]['kind'] in {
            'Lean.cdot','Lean.Parser.Tactic.case',"Lean.Parser.Tactic.case'",
            'Lean.Parser.Tactic.cases','Lean.Parser.Tactic.induction'}]
    # Ignore final unsolved-goal diagnostics when a concrete earlier tactic error exists.
    actionable=[d for d in result['diagnostics'] if d['parse_char']>=2 and
                d['candidate_id'] is not None and not d['message']['data'].startswith('unsolved goals')]
    chosen=min(actionable,key=lambda d:d['parse_char']) if actionable else None
    failure=chosen['candidate_id'] if chosen else None
    result['fine_failure_candidate']=failure
    fail_end=nodes[failure]['end_char'] if failure is not None else None
    result['localization_blockers']=[d for d in result['diagnostics']
        if not d['message']['data'].startswith('unsolved goals') and
        (d['parse_char']<0 or (failure is not None and d['parse_char']<nodes[failure]['start_char'] and d['candidate_id'] is None))]
    if result.get('whole_sorries'):result['localization_blockers'].append({'reason':'sorry_or_recovery_hole'})
    verified=result['whole_elaboration_ok']
    for pt in result['points']:
        selected=[nodes[i] for i in pt['node_ids'] if i in result['selected_node_ids']]
        node=max(selected or [nodes[i] for i in pt['node_ids']],key=lambda n:len(n['ancestor_ids']))
        ev=node['native_events'];event=ev[0] if len(ev)==1 else None
        pt.update(node_id=node['id'],branch_path=node['branch_path'],event_ids=[x['id'] for x in ev],
                  observation_kind='calc_step' if node['kind'] in {'Lean.calcFirstStep','Lean.calcStep'} else 'tactic',
                  event_multiplicity=len(ev),trace_label='verified_trace' if verified else 'unlocalized_failure')
        if event:
            pt.update(active_goal_ids=event['goal_ids_before'],next_goal_ids=event['goal_ids_after'],
                      root_pending_before=pending(event['root_before']),root_pending_after=pending(event['root_after']),
                      root_closed_before=root_closed(event['root_before']),root_closed_after=root_closed(event['root_after']))
            pt['goal_namespace']=trace_id
            b,a=event['goal_ids_before'],event['goal_ids_after']
            pt['execution_status']='observed'
            if root_closed(event['root_before']) and b==[]:pt['execution_status']='post_completion'
            elif b==[]:pt['execution_status']='inactive_local_context'
            if root_closed(event['root_after']) and not root_closed(event['root_before']):
                pt['transition']='completes_root'
            elif b and a==[]:pt['transition']='closes_local_goals'
            elif b is not None and a is not None and len(a)>len(b):pt['transition']='splits_goals'
            else:pt['transition']='updates_context'
        else:
            pt['execution_status']='ambiguous_events' if ev else 'no_tactic_event'
            pt['transition']='unknown'
        if fail_end is not None:
            pt['trace_label']='pre' if pt['end_char']<fail_end else ('at_candidate' if pt['end_char']==fail_end else 'post')
            if pt['end_char']>fail_end:
                pt['absorbing_unreached']=True
                pt['observed_during_lean_recovery']=bool(ev)
        if verified and pt['execution_status']=='post_completion':pt['trace_label']='post_completion'
    result.update(version='tree-frontier-v2',trace_id=trace_id,native_events=native,
                  source_sha256=digest_text(result['source']),header_sha256=digest_text(header),
                  localization_status='candidate' if failure is not None else ('not_applicable_verified' if verified else 'not_localized'),
                  annotation_ready=False,label_ready=False,
                  runtime_semantics='original elaboration; goal IDs scoped to this trace; source order is distinct from execution nesting')
    return result

def align_original(result,tokenizer,sample,body_start):
    """Map byte boundaries using saved vocabulary pieces, never re-tokenize the answer.
    Keep exact ends and ends followed only by whitespace within the same original token.
    A token containing future code is not a usable observation of the preceding step.
    """
    completion=sample['completion'];body=result['source'][2:]
    if body_start<0:raise ValueError('negative body_start')
    if completion[body_start:body_start+len(body)]!=body:
        raise ValueError('body is not an exact slice of the saved completion')
    offsets=original_token_spans(tokenizer,sample['completion_token_ids'],completion)
    raw=completion.encode('utf-8');ends=[b for a,b in offsets];n_prompt=len(sample['prompt_token_ids'])
    if not n_prompt:raise ValueError('missing original prompt IDs')
    observations=[];rejected=[];seen={}
    for pt in result['points']:
        char_end=body_start+pt['end_char']-2;b=len(completion[:char_end].encode('utf-8'))
        idx=bisect_left(ends,b)
        if idx>=len(ends):
            rejected.append({'point':pt['index'],'reason':'out_of_tokens'});continue
        extra=raw[b:ends[idx]]
        if extra and any(c not in b' \t\r\n' for c in extra):
            rejected.append({'point':pt['index'],'reason':'token_contains_future_code','extra_bytes':len(extra),'token_index':idx});continue
        pos=n_prompt+idx
        if pos in seen:
            seen[pos]['point_indices'].append(pt['index']);continue
        row={'observation_index':len(observations),'point_indices':[pt['index']],'token_position':pos,
             'completion_token_index':idx,'semantic_end_char':char_end,'semantic_end_byte':b,
             'token_end_byte':ends[idx],'trailing_whitespace_bytes':len(extra),'boundary_kind':'exact' if not extra else 'trailing_whitespace',
             'trace_label':pt['trace_label'],'execution_status':pt['execution_status']}
        observations.append(row);seen[pos]=row
    result['token_alignment']={'observations':observations,'rejected':rejected,'n_original_tokens':len(offsets),
        'prompt_position':n_prompt-1,'positions':[n_prompt-1]+[x['token_position'] for x in observations],
        'n_latent_points':1+len(observations),'completion_sha256':digest_text(completion),
        'completion_token_ids_sha256':digest_text(json.dumps(sample['completion_token_ids'],separators=(',',':'))),
        'policy':'original bytes; exact or whitespace-only suffix; future code excluded; omitted boundaries explicitly listed'}
    return result['token_alignment']

class SegmenterV2(base.Segmenter):
    def inspect(self,header,body,trace_id=""):
        r=super().inspect(header,body)
        if r.get('parse_ok'):
            attach_semantics(r,header,r['whole_reply'],trace_id)
            annotate_source_scopes(r)
        return r
    def replay_frontier(self,result,limit=100):
        # Separate local-context evidence from the independent whole-proof verdict.
        replays=super().replay_frontier(result,limit=limit)
        if not result.get('parse_ok'):return replays
        by={r['node_id']:r for r in replays}
        for pt in result['points']:
            pt['replay_evidence']=[{'node_id':i,'status':by[i]['status'],'proof_status':by[i]['reply'].get('proofStatus')} for i in pt['node_ids'] if i in by]
        if result.get('failure_and_prefix_reproduced') and not result.get('localization_blockers'):
            result['localization_status']='prefix_and_failure_reproduced'
            for pt in result['points']:
                if pt['trace_label']=='at_candidate':pt['trace_label']='at'
        elif result.get('failure_reproduced'):
            result['localization_status']='failure_reproduced_prefix_incomplete'
        elif result.get('fine_failure_candidate') is not None:
            result['localization_status']='diagnostic_only'
        result['annotation_ready']=result['whole_elaboration_ok'] or result['localization_status']=='prefix_and_failure_reproduced'
        # Activation extraction and a production certificate adapter are still separate steps.
        result['label_ready']=False
        return replays

def reuse_plan(result,sample,label):
    """Explicitly describe what can be reused; never certify a changed problem or answer."""
    body_ok=result.get('parse_ok') and result['source'][2:]==label['body']
    original_ok=body_ok and sample['completion'][label['body_start']:label['body_start']+len(label['body'])]==label['body']
    alignment=result.get('token_alignment')
    return {'reuse_generation':bool(original_ok),'reuse_saved_token_ids':bool(original_ok),
        'reuse_whole_verdict_if_context_and_runtime_match':bool(original_ok),
        'whole_category_from_existing_label':label['category'],'old_label_row_sha256':label.get('row_sha256'),
        'new_semantic_annotations_required':True,'new_activation_positions_required':bool(alignment),
        'already_generated_answer_unchanged':bool(original_ok),
        'production_ready':False,'reason':'prototype validated on bounded examples; no new GPU extraction; production certificate integration pending'}

SCOPE_KINDS={
    "Lean.Parser.Tactic.tacticHave__","Lean.Parser.Tactic.tacticLet__",
    "Lean.cdot","Lean.Parser.Tactic.case","Lean.Parser.Tactic.case'",
    "Lean.Parser.Tactic.focus","Lean.Parser.Tactic.inductionAlt"}
BRANCH_KINDS={"Lean.cdot","Lean.Parser.Tactic.case","Lean.Parser.Tactic.case'",
              "Lean.Parser.Tactic.inductionAlt"}

def annotate_source_scopes(result):
    """Lexical branch/scope metadata; never interpreted as a chronological Lean state chain."""
    scopes=[]
    def walk(n,parent=None):
        kind=n["kind"];a=n.get("start");b=n.get("end")
        if kind in SCOPE_KINDS and a is not None and b is not None:
            sid=len(scopes)
            scopes.append({"id":sid,"parent_id":parent,"kind":kind,
                "start_char":base.byte_to_char(result["source"],a),
                "end_char":base.byte_to_char(result["source"],b)})
            parent=sid
        for c in n.get("args",[]):walk(c,parent)
    walk(result["ast"])
    previous=[]
    for pt in result["points"]:
        n=result["nodes"][pt["node_id"]]
        path=[x["id"] for x in scopes if x["start_char"]<=n["start_char"] and n["end_char"]<=x["end_char"]]
        path.sort(key=lambda i:(scopes[i]["start_char"],-scopes[i]["end_char"],i))
        branch=[i for i in path if scopes[i]["kind"] in BRANCH_KINDS]
        pt["scope_path"]=path;pt["branch_path"]=branch
        common=0
        while common<min(len(previous),len(path)) and previous[common]==path[common]:common+=1
        exited=previous[common:];entered=path[common:]
        pt["source_transition"]={
            "exit_scope_ids":list(reversed(exited)),"enter_scope_ids":entered,
            "branch_switch":any(scopes[i]["kind"] in BRANCH_KINDS for i in exited) and
                            any(scopes[i]["kind"] in BRANCH_KINDS for i in entered),
            "scope_changed":bool(exited or entered)}
        if n["id"] not in result["selected_node_ids"]:
            pt["observation_kind"]="scope_close"
            pt["event_covers_scope"]=True
        previous=path
    result["scopes"]=scopes
    return result

def main():
    import argparse
    from onebigjump.lean import LeanREPL,discover
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("input",type=Path,help="One JSON: header ending in by, exact body, optional trace_id/sample/body_start")
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--replay-limit",type=int,default=100)
    p.add_argument("--tokenizer",type=Path,help="Local tokenizer directory; no network/model generation")
    args=p.parse_args()
    if not 0<=args.replay_limit<=100:raise ValueError("bounded prototype: replay-limit must be 0..100")
    x=json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(x,dict):raise ValueError("one proof per invocation; no batch mode")
    with LeanREPL(discover(),imports="import Mathlib\nimport Aesop",startup_attempts=1,default_timeout_s=90,drain_timeout_s=10) as repl:
        s=SegmenterV2(repl)
        r=s.inspect(x["header"],x["body"],x.get("trace_id","single-proof"))
        if r.get("parse_ok"):
            s.replay_frontier(r,limit=args.replay_limit)
            if args.tokenizer:
                from transformers import AutoTokenizer
                tok=AutoTokenizer.from_pretrained(args.tokenizer,local_files_only=True)
                align_original(r,tok,x["sample"],x["body_start"])
    args.output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":main()
