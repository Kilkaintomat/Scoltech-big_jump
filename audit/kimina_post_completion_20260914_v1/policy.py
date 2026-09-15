"""Strict terminal post-completion trimming; never relabel failed proofs."""
import numpy as np
from measure_analyze import labels
from onebigjump.e1.measurement import fit_transform
def clean_length(export,annotation):
    obs=export["observation_rows"];star=labels(export,annotation);L=len(obs)
    if star is not None:return L,star
    tags=[o["trace_label"]=="post_completion" for o in obs]
    if not any(tags):return L,None
    keep=tags.index(True)
    if keep==0:raise ValueError("no retained root-closing observation")
    if not all(tags[keep:]):raise ValueError("post-completion observations are not a terminal suffix")
    for o in obs[keep:]:
        if o.get("execution_status")!="post_completion":raise ValueError("inconsistent observation status")
        if not o.get("source_points"):raise ValueError("missing root closure evidence")
        for p in o["source_points"]:
            if p.get("trace_label")!="post_completion" or p.get("execution_status")!="post_completion":
                raise ValueError("mixed source labels")
            if p.get("root_closed_before") is not True or p.get("active_goal_ids")!=[]:
                raise ValueError("root still open or missing evidence")
    return keep,None
def slice_states(states,surprisal,L,keep):
    if states.ndim!=2 or len(states)!=L+1 or len(surprisal)!=L or not 1<=keep<=L:
        raise ValueError("state/observation shape mismatch")
    return states[:keep+1].copy(),surprisal[:keep].copy()
def validate_splits(records):
    cal={r["problem_id"] for r in records if r["role"]=="calibration"}
    ev={r["problem_id"] for r in records if r["role"]=="evaluation"}
    if cal&ev:raise ValueError("task overlap")
def fit_calibration(records,settings):
    validate_splits(records)
    calibration=[r for r in records if r["role"]=="calibration" and r["star"] is None]
    n=sum(len(r["states"])-1 for r in calibration);tasks=len({r["problem_id"] for r in calibration})
    enough=tasks>=settings["min_main_tasks"] and n>=settings["min_main_increments"]
    fit=fit_transform([r["states"] for r in calibration],settings["shrinkage"],settings["ridge"]) if enough else None
    info={"available":enough,"tasks":tasks,"increments":n,"trace_ids":[r["trace_id"] for r in calibration],
          "whitening_refitted":enough,"scope":"clean verified calibration tasks only; fixed inside subsequent bootstrap"}
    return fit,info
