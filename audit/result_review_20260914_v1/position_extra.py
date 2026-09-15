"""Precision and cohort diagnostics for the already frozen positional null."""
import collections,itertools,math,importlib.util
import numpy as np
from support import *
spec=importlib.util.spec_from_file_location("original_position_controls",REPO/"audit/segmentation_controls_20260914_v1/controls.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def distribution(group):
    n=len(group)
    if n>12:raise ValueError("exact stratum too large")
    dp={0:{0:1}}
    for i in range(n):
        nxt={}
        for mask,poly in dp.items():
            for c in range(n):
                if mask&(1<<c):continue
                d=int(group[i]["j"]==group[c]["f"]);newmask=mask|(1<<c);dest=nxt.setdefault(newmask,{})
                for k,v in poly.items():dest[k+d]=dest.get(k+d,0)+v
        dp=nxt
    counts=dp[(1<<n)-1];assert sum(counts.values())==math.factorial(n)
    out=np.zeros(n+1)
    for k,v in counts.items():out[k]=v/math.factorial(n)
    return out
def exact(rows):
    groups=collections.defaultdict(list)
    for r in rows:groups[(r["task_family"],r["L"])].append(r)
    groups=[g for g in groups.values() if len(g)>1];use=[r for g in groups for r in g]
    prob=np.array([1.])
    for g in groups:prob=np.convolve(prob,distribution(g))
    hits=sum(r["j"]==r["f"] for r in use)
    return {"tasks":len(use),"hits":hits,"p_D0_exact":float(prob[hits:].sum()),"expected_D0":float(np.dot(prob,np.arange(len(prob)))/len(use)) if use else None,
       "strata_sizes":[len(g) for g in groups],"method":"complete permutation distribution via subset dynamic programming and convolution"}
def main():
    check_code();assert np.allclose(distribution([{"j":0,"f":0},{"j":1,"f":1}]),[.5,0,.5])
    test=[{"j":0,"f":0},{"j":1,"f":1},{"j":0,"f":2}]
    brute=collections.Counter(sum(test[i]["j"]==test[c]["f"] for i,c in enumerate(order)) for order in itertools.permutations(range(3)))
    assert np.allclose(distribution(test),[brute[k]/6 for k in range(4)])
    controls=read(CONTROL/"metrics.json");result={};inputs=[CONTROL/"manifest.json",Path(__file__)]
    for m in MODELS:
        allrows=read(CONTROL/(m+"-all-trials.json"));one={}
        for r in allrows:one.setdefault(r["problem_id"],r)
        fixed=[r for r in one.values() if r["f"]>0]
        already_matched=set(controls["models"][m]["all"]["positional_null"]["selected_trace_ids"])
        fixed_matched=[r for r in fixed if r["trace_id"] in already_matched]
        cases={"choose_one_before_removing_first_errors":mod.positional_null(fixed),
               "original_matched_cohort_then_remove_first_errors":mod.positional_null(fixed_matched)}
        out={}
        for subset,v in controls["models"][m].items():
            path=CONTROL/(m+"-"+subset+"-trials.json");inputs.append(path);rows=read(path);ids=set(v["positional_null"]["selected_trace_ids"])
            e=exact([r for r in rows if r["trace_id"] in ids])
            e["existing_monte_carlo_p"]=v["positional_null"].get("pvalues",{}).get("D=0")
            e["bonferroni48_exploratory"]=min(1,e["p_D0_exact"]*48)
            out[subset]=e
        result[m]={"frozen_subsets_exact":out,"cohort_sensitivity":cases}
    finish("position_extra",{"models":result,"scope":"post-result audit of exact D0 p-values and representative-trace selection; not a new primary test","algorithm_checks_passed":2},inputs)
    print("POSITION EXTRA COMPLETE",flush=True)
if __name__=="__main__":main()
