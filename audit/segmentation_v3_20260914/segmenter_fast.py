"""Selected-source Lean observer, fixed AST boundaries and original-token alignment."""
import time
import segmenter as base
from segmenter_v2 import SegmenterV2,attach_semantics,annotate_source_scopes,align_original

class SegmenterFast(SegmenterV2):
    def __init__(self,repl,timeout_s=180):
        super().__init__(repl)
        self.timeout_s=timeout_s
    def inspect(self,header,body,trace_id=""):
        started=time.monotonic()
        r=self.parse(body)
        if not r.get("parse_ok"):return r
        if not header.endswith("by"):raise ValueError("header must end in by")
        wanted=set(r["selected_node_ids"])
        wanted.update(i for p in r["points"] for i in p["node_ids"])
        nodes=[r["nodes"][i] for i in sorted(wanted)]
        shift=len(header.encode("utf-8"))-2
        ranges=[]
        for n in nodes:
            descend=any(n["id"]!=m["id"] and n["start_byte"]<=m["start_byte"] and m["end_byte"]<=n["end_byte"] for m in nodes)
            ranges.append({"first":shift+n["start_byte"],"last":shift+n["end_byte"],"kind":n["kind"],"descend":descend})
        request={"cmd":header+body,"env":self.repl._base_env,"observeRanges":ranges}
        reply=self.repl._exchange(request,timeout_s=self.timeout_s)
        if not isinstance(reply.get("observerProfile"),dict):
            raise RuntimeError("selected observer did not return its runtime contract")
        if reply["observerProfile"]["requested_ranges"]!=len(ranges):
            raise RuntimeError("selected observer range count mismatch")
        r["whole_reply"]=reply
        base.attach(r,header+body,len(header)-2,reply)
        attach_semantics(r,header,reply,trace_id)
        annotate_source_scopes(r)
        r["version"]="tree-frontier-v3-selected"
        r["observer_profile"]=reply.get("observerProfile")
        r["observer_wall_s"]=time.monotonic()-started
        r["observation_ranges"]=ranges
        r["production_label_certificate"]=False
        return r
