"""Small AST-based observation segmenter for Lean 4, never a source rewriter.
Pinned/tested on Lean v4.34.0-rc2. No production pipeline dependency.
AST determines endpoints BEFORE Lean executes a proof (including unreachable text).
InfoTree only annotates these fixed endpoints. A point is NOT an independently
executable substring, and a source tree is NOT the Lean execution trace.

Intentional conservative frontier:
  descend into nested tactic-sequences under have/let, case, bullet, and focus;
  keep search, mapping combinators, calc terms and unknown compound tactics atomic.
The full AST and original text remain available for future refinements.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from onebigjump.lean import LeanREPL,discover

SEQ={"Lean.Parser.Tactic.tacticSeq1Indented","Lean.Parser.Tactic.tacticSeqBracketed"}
SAFE={"Lean.Parser.Tactic.tacticHave__","Lean.Parser.Tactic.tacticLet__",
      "Lean.Parser.Tactic.case","Lean.Parser.Tactic.case'","Lean.cdot",
      "Lean.Parser.Tactic.focus"}
def errors(reply):
    out=[m for m in reply.get("messages",[]) if m.get("severity")=="error"]
    if isinstance(reply.get("message"),str) and reply["message"].strip():
        out.append(dict(severity="error",data=reply["message"],pos=None))
    if str(reply.get("proofStatus","")).startswith("Error:"):
        out.append(dict(severity="error",data=reply["proofStatus"],pos=None))
    return out
def replay_status(reply):
    es=errors(reply)
    if str(reply.get("proofStatus","")).startswith("Error:") and not reply.get("message") and not any(m.get("severity")=="error" for m in reply.get("messages",[])):
        return "snapshot_kernel_rejection"
    if es:
        text="\n".join(m["data"] for m in es).lower()
        if any(x in text for x in ["timeout","heartbeats","recursion depth","out of memory"]):
            return "resource_error"
        if reply.get("message") and not reply["message"].startswith("Lean error:"):
            return "infrastructure_error"
        return "error"
    if reply.get("sorries"):return "sorry"
    if "proofState" not in reply or not isinstance(reply.get("goals"),list):return "unknown_reply"
    return "ok"
def byte_to_char(text,offset):
    return len(text.encode("utf-8")[:offset].decode("utf-8"))
def position_char(text,pos):
    lines=text.splitlines(keepends=True)
    line,col=pos["line"]-1,pos["column"]
    if line<0 or line>=len(lines) or col>len(lines[line].rstrip("\r\n")):
        raise ValueError("Lean position outside source")
    return sum(map(len,lines[:line]))+col
def children_of_sequence(node):
    # Sequence lists contain null wrappers and punctuation. Do not recurse into a
    # tactic here: it is a child node, not another item of the enclosing sequence.
    def unwrap(n):
        if n["kind"]=="null":
            for c in n.get("args",[]):yield from unwrap(c)
        elif n.get("args") and n.get("start") is not None:
            yield n
    for c in node.get("args",[]):yield from unwrap(c)

def from_ast(parse_text:str,ast:dict)->dict:
    if not parse_text.startswith("by"):raise ValueError("expected a by-expression")
    nodes=[]
    def seq_scan(n,parent):
        if n["kind"] in SEQ:
            for c in children_of_sequence(n):add(c,parent)
        else:
            for c in n.get("args",[]):seq_scan(c,parent)
    def add(n,parent):
        a,b=n.get("start"),n.get("end")
        if a is None or b is None or b<=a:return
        start,end=byte_to_char(parse_text,a),byte_to_char(parse_text,b)
        if start<2 or end>len(parse_text):raise ValueError("bad syntax range")
        i=len(nodes);text=parse_text[start:end]
        nodes.append(dict(id=i,parent_id=parent,kind=n["kind"],start_byte=a,end_byte=b,
                          start_char=start,end_char=end,text=text,children=[]))
        if parent is not None:nodes[parent]["children"].append(i)
        for c in n.get("args",[]):seq_scan(c,i)
    seq_scan(ast,None)
    def choose(i):
        n=nodes[i];kids=n["children"]
        n["policy"]="leaf" if not kids else ("refine" if n["kind"] in SAFE else "atomic_compound")
        if kids and n["kind"] in SAFE:
            return [j for c in kids for j in choose(c)]
        # Mark descendants as retained metadata, not independently labelled steps.
        def block(j):
            nodes[j]["policy"]="inside_atomic"
            for c in nodes[j]["children"]:block(c)
        for c in kids:block(c)
        return [i]
    selected=[j for n in nodes if n["parent_id"] is None for j in choose(n["id"])]
    # Endpoints of roots also retain a possible closing delimiter after the last leaf.
    endpoints={}
    for i in selected:
        endpoints.setdefault(nodes[i]["end_char"],[]).append(i)
    for n in nodes:
        if n["parent_id"] is None:endpoints.setdefault(n["end_char"],[]).append(n["id"])
    points=[];prev=2
    for end,ids in sorted(endpoints.items()):
        ids=sorted(set(ids))
        ancestors=set(ids)
        for i in ids:
            p=nodes[i]["parent_id"]
            while p is not None:
                if nodes[p]["end_char"]==end:ancestors.add(p)
                p=nodes[p]["parent_id"]
        points.append(dict(index=len(points),end_char=end,end_byte=len(parse_text[:end].encode("utf-8")),
             node_ids=ids,closing_node_ids=sorted(ancestors),span_start=prev,span_end=end,
             text=parse_text[prev:end],semantic_status="unannotated"))
        prev=end
    out=dict(version="tree-frontier-v1",source=parse_text,ast=ast,nodes=nodes,
             selected_node_ids=selected,points=points,suffix=parse_text[prev:],
             n_blocks=len(points),n_latent_points_with_prompt=len(points)+1,
             parse_ok=True,label_ready=False,execution_order="not inferred from source order")
    assert reconstruct(out)==parse_text
    assert all(a["end_char"]<b["end_char"] for a,b in zip(points,points[1:]))
    return out

def reconstruct(result):
    return result["source"][:2]+"".join(p["text"] for p in result["points"])+result["suffix"]

def attach(result,full_source,header_char_shift,reply):
    """Attach dynamic events by original source coordinates, without changing points."""
    nodes=result["nodes"];by_span={}
    for n in nodes:by_span.setdefault((n["start_char"],n["end_char"]),[]).append(n)
    events=[]
    def walk(tree,parent=None):
        node=tree.get("node") or {};stx=node.get("stx") or {};r=stx.get("range")
        eventparent=parent
        if tree.get("kind")=="TacticInfo" and r and not r.get("synthetic"):
            a=position_char(full_source,r["start"])-header_char_shift
            b=position_char(full_source,r["finish"])-header_char_shift
            e=dict(id=len(events),parent_id=parent,start_char=a,end_char=b,kind=stx["kind"],
                   goals_before=node.get("goalsBefore"),goals_after=node.get("goalsAfter"))
            events.append(e);eventparent=e["id"]
        for c in tree.get("children",[]):walk(c,eventparent)
    for t in reply.get("infotree",[]):walk(t)
    for n in nodes:
        n["events"]=[e for e in events if (e["start_char"],e["end_char"])==(n["start_char"],n["end_char"]) and e["kind"]==n["kind"]]
        n["proof_states"]=[]
        n["local_goals_empty_before"]=[not e["goals_before"] for e in n["events"]]
        # Empty LOCAL goals inside a nested proof do not imply global completion.
    for t in reply.get("tactics",[]):
        a=position_char(full_source,t["pos"])-header_char_shift
        b=position_char(full_source,t["endPos"])-header_char_shift
        for n in by_span.get((a,b),[]):
            n["proof_states"].append(dict(proof_state=t.get("proofState"),tactic=t["tactic"],goals=t["goals"]))
    selected=[nodes[i] for i in result["selected_node_ids"]]
    result["events"]=events
    result["whole_errors"]=errors(reply)
    result["whole_sorries"]=reply.get("sorries",[])
    result["whole_elaboration_ok"]=not errors(reply) and not reply.get("sorries")
    # Recovery may cause Lean to run later source; it does not undo absorption.
    diagnostics=[]
    for m in errors(reply):
        pos=position_char(full_source,m["pos"])-header_char_shift if m.get("pos") else -1
        candidates=[n for n in selected if n["start_char"]<=pos<n["end_char"]]
        diagnostics.append(dict(message=m,parse_char=pos,
             candidate_id=min(candidates,key=lambda n:n["end_char"]-n["start_char"])["id"] if candidates else None))
    result["diagnostics"]=diagnostics
    result["fine_failure_candidate"]=None
    if diagnostics:
        first=min(diagnostics,key=lambda d:d["parse_char"])
        # An unfinished enclosing goal is not a precise failure of an inner tactic.
        if first["candidate_id"] is not None and not first["message"]["data"].startswith("unsolved goals"):
            result["fine_failure_candidate"]=first["candidate_id"]
    fail=result["fine_failure_candidate"]
    end=nodes[fail]["end_char"] if fail is not None else None
    for p in result["points"]:
        if end is not None and p["end_char"]>end:p["semantic_status"]="unreached_absorbing"
        elif end==p["end_char"]:p["semantic_status"]="error_candidate_needs_replay"
        else:p["semantic_status"]="has_context" if any(nodes[i]["proof_states"] for i in p["node_ids"]) else "context_unavailable"
    result["selected_context_coverage"]=sum(bool(n["proof_states"]) for n in selected)
    return result

def align_points(result,token_offsets):
    """Exact character endpoints only; never read a token straddling a boundary.
    token_offsets must address result['source']; special tokens must be omitted.
    Real campaign token reconstruction is deliberately outside this prototype.
    """
    mapped=[];rejected=[];seen=set()
    for p in result["points"]:
        matches=[i for i,(a,b) in enumerate(token_offsets) if a<b and b==p["end_char"]]
        if not matches:
            rejected.append(p["index"]);continue
        t=max(matches)
        if t in seen:continue
        seen.add(t);mapped.append(dict(point=p["index"],token=t))
    return dict(mapped=mapped,rejected_points=rejected)

class Segmenter:
    def __init__(self,repl):
        self.repl=repl
        reply=repl.command(Path(__file__).with_name("syntax_command.lean").read_text(encoding="utf-8"),timeout_s=90)
        if errors(reply):raise RuntimeError(reply)
        self.ast_env=reply["env"]
    def parse(self,body):
        source="by"+body
        reply=self.repl._exchange(dict(cmd="#obj_ast "+json.dumps(source,ensure_ascii=False),env=self.ast_env),timeout_s=90)
        for m in reply.get("messages",[]):
            if m.get("data","").startswith("OBJAST:"):
                return from_ast(source,json.loads(m["data"][7:]))
        return dict(parse_ok=False,source=source,parse_reply=reply,n_blocks=None,label_ready=False)
    def inspect(self,header,body):
        result=self.parse(body) # no outcomes used to choose segmentation
        if not result["parse_ok"]:return result
        if not header.endswith("by"):raise ValueError("header must end in by")
        source=header+body
        reply=self.repl._exchange(dict(cmd=source,env=self.repl._base_env,infotree="original",allTactics=True),timeout_s=90)
        result["whole_reply"]=reply
        return attach(result,source,len(header)-2,reply)
    def replay_frontier(self,result,limit=60):
        """Small diagnostic only. Replay in stored local context, never bare chunks."""
        if not result.get("parse_ok"):return []
        tested=[];fail=result.get("fine_failure_candidate")
        stop=result["nodes"][fail]["end_char"] if fail is not None else None
        for i in result["selected_node_ids"]:
            n=result["nodes"][i]
            if stop is not None and n["end_char"]>stop:continue
            if len(tested)>=limit:break
            states=n.get("proof_states",[])
            if len(states)!=1 or states[0]["proof_state"] is None:continue
            s=states[0]
            reply=self.repl._exchange(dict(tactic=s["tactic"],proofState=s["proof_state"]),timeout_s=30)
            tested.append(dict(node_id=i,source=n["text"],ok=replay_status(reply)=="ok",status=replay_status(reply),reply=reply))
        result["context_replays"]=tested
        if fail is not None:
            target=next((r for r in tested if r["node_id"]==fail),None)
            result["failure_reproduced"]=target is not None and target["status"]=="error"
            expected_prefix={i for i in result["selected_node_ids"] if result["nodes"][i]["end_char"]<stop}
            actual_prefix={r["node_id"] for r in tested if result["nodes"][r["node_id"]]["end_char"]<stop}
            result["prefix_tested_ok"]=all(r["ok"] for r in tested if r["node_id"] in expected_prefix)
            result["prefix_replay_complete"]=actual_prefix==expected_prefix
            result["prefix_reproduced"]=result["prefix_tested_ok"] and result["prefix_replay_complete"]
            result["failure_and_prefix_reproduced"]=result["failure_reproduced"] and result["prefix_reproduced"]
        result["replay_skipped_node_ids"]=[i for i in result["selected_node_ids"] if
            (stop is None or result["nodes"][i]["end_char"]<=stop) and i not in {r["node_id"] for r in tested}]
        # This remains a diagnostic: no full chronological replay or token mapping certificate.
        result["label_ready"]=False
        return tested

def map_to_completion(result,completion,body_start):
    """Require exact original body; reconstructed/reformatted proof text is refused."""
    body=result["source"][2:]
    if body_start<0 or completion[body_start:body_start+len(body)]!=body:
        raise ValueError("body is not an exact slice of the original completion")
    return [{"point":p["index"],"completion_char_end":body_start+p["end_char"]-2} for p in result["points"]]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("input",type=Path,help="JSON with header (ending in by), body")
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--replay",action="store_true",help="bounded replay of stored tactic contexts")
    args=p.parse_args();x=json.loads(args.input.read_text(encoding="utf-8"))
    with LeanREPL(discover(),imports="import Mathlib\nimport Aesop") as repl:
        segmenter=Segmenter(repl);result=segmenter.inspect(x["header"],x["body"])
        if args.replay:segmenter.replay_frontier(result)
        if result["parse_ok"] and "completion" in x:
            result["completion_map"]=map_to_completion(result,x["completion"],x["body_start"])
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
