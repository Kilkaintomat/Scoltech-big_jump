"""One unchanged answer -> selected Lean observations and original token positions."""
import collections,time
from onebigjump.e1.artifacts import identity
from onebigjump.lean.verifier import ReplError
from segmenter_v2 import align_original
from export_observations import export

def annotate(item,s,tok,replay_budget_s=300):
    row={"trace_id":item["trace_id"],"model":item["model"],"problem_id":item["problem_id"],
         "old_category":item["old_category"],"status":"not_started","p2_eligible":False,
         "generation_reused":True,"input_sha256":identity(item),"whole_label_row_sha256":item["label_row_sha256"]}
    detail={"input_sha256":identity(item),"source_identity":item["source_identity"]}
    if item.get("exclusion"):
        row.update(status="upstream_exclusion",reason=item["exclusion"]);return row,detail,False
    started=time.monotonic();restart=False
    try:
        r=s.inspect(item["header"],item["body"],item["trace_id"]);detail["observation"]=r
        if not r.get("parse_ok"):
            row["status"]="parse_unsupported";return row,detail,False
        expected=(item["old_category"]=="verified") if item["old_category"] in ["verified","localized_tactic_failure"] else None
        row.update(n_blocks=r["n_blocks"],n_old_blocks=item["n_old_blocks"],
                   observer_profile=r["observer_profile"],whole_observed_ok=r["whole_elaboration_ok"],
                   whole_verdict_agrees=None if expected is None else r["whole_elaboration_ok"]==expected)
        messages="\n".join(x.get("data","") for x in r.get("whole_errors",[])).lower()
        limited=any(w in messages for w in ["heartbeats","timeout","recursion depth","out of memory"])
        row["lean_resource_limited"]=limited;row["status"]="annotated"
        if row["whole_verdict_agrees"] is False:
            row["status"]="whole_resource_disagreement" if limited else "whole_verdict_disagreement"
        if not r["whole_elaboration_ok"] and r.get("fine_failure_candidate") is not None and not limited:
            original=s.repl._exchange;deadline=time.monotonic()+replay_budget_s
            def bounded(request,timeout_s=None,**kw):
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError("total context replay budget exhausted")
                return original(request,timeout_s=min(timeout_s or 30,remaining),**kw)
            s.repl._exchange=bounded
            try:s.replay_frontier(r,limit=2048)
            except TimeoutError as e:
                r["localization_status"]="replay_resource_limited";r["replay_error"]=str(e);restart=True
            finally:s.repl._exchange=original
        elif r["whole_elaboration_ok"]:
            r["localization_status"]="not_applicable_verified";r["annotation_ready"]=True
            r["verified_replay_policy"]="whole certificate reused; successful tactics not independently replayed again"
        else:r["localization_status"]="not_localized"
        alignment=align_original(r,tok,item["sample"],item["body_start"])
        detail["export"]=export(r,item["sample"],tok,item["body_start"])
        row.update(localization_status=r["localization_status"],n_positions=len(alignment["positions"]),
                   n_rejected_token_boundaries=len(alignment["rejected"]),
                   n_exact_token_boundaries=sum(x["boundary_kind"]=="exact" for x in alignment["observations"]),
                   n_whitespace_boundaries=sum(x["boundary_kind"]=="trailing_whitespace" for x in alignment["observations"]),
                   n_post_completion=sum(p["execution_status"]=="post_completion" for p in r["points"]),
                   n_branch_switches=sum(p["source_transition"]["branch_switch"] for p in r["points"]),
                   n_replays=len(r.get("context_replays",[])),
                   replay_status_counts=dict(collections.Counter(x["status"] for x in r.get("context_replays",[]))))
        row["p2_eligible"]=bool(row["whole_verdict_agrees"] and item["old_category"]=="localized_tactic_failure" and
            r["localization_status"]=="prefix_and_failure_reproduced" and any(p["trace_label"]=="at" for p in alignment["observations"]))
        row["ready_for_activation_extraction"]=bool(row["whole_verdict_agrees"] and alignment["observations"])
        detail["label_contract"]={"whole_category":item["old_category"],"whole_certificate_source":item["label_origin"],
            "p2_local_context_evidence_complete":row["p2_eligible"],"chronological_replay_of_cut_substrings":False,
            "original_answer_modified":False,"absorbing_source_labels":True,"new_whole_certificate_claimed":False}
    except ReplError as e:
        row.update(status="observer_runtime_error",reason=str(e),error_type=type(e).__name__,
                   p2_eligible=False,ready_for_activation_extraction=False)
        detail["runtime_failure"]={"reason":str(e),"no_new_failure_label":True}
        restart=True
    except TimeoutError as e:row.update(status="observer_timeout",reason=str(e));restart=True
    except ValueError as e:row.update(status="alignment_or_source_exclusion",reason=str(e));restart=True
    row["elapsed_s"]=time.monotonic()-started
    return row,detail,restart
