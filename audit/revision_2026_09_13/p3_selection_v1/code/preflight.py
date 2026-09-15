"""Validate selection generator, conditional model, disjoint data and threshold rules."""
from pathlib import Path
import os
import numpy as np
from scipy import stats
from experiment import sample,method_thresholds,soft_integral,rng_for,failures_sample,analyze_dataset
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,verify_manifest
from onebigjump.e1.analysis import finite_json

base=Path("/beegfs/home/denis.rakhmankin/onebigjump")
here=Path(__file__).resolve().parent
config=read_json(here.parent/"protocol.json")
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
previous=base/"audit/revision_2026_09_13/p3_constrained_v1"
verify_manifest(previous/"preflight/manifest.json")
assert digest(here/"candidate.py")==digest(previous/"code/candidate.py")
checks=[]
for i,(name,setting) in enumerate(config["scenarios"].items()):
    seed=config["preflight_seed"]+i
    cal,ev,pilot,cutoff=sample(seed,setting,config)
    assert cal.shape==(192,48) and ev.shape==pilot.shape==(48,3)
    assert not np.array_equal(ev,pilot)
    assert not set(ev.ravel()) & set(pilot.ravel())
    again=sample(seed,setting,config)
    assert np.array_equal(cal,again[0]) and np.array_equal(ev,again[1]) and np.array_equal(pilot,again[2])
    ts=method_thresholds(cal[:48],ev,pilot,cutoff,config["q"])
    assert ts["independent_floor"]==max(ts["original"],float(pilot.min()))
    changed=method_thresholds(cal[:48],ev+1000,pilot,cutoff,config["q"])
    assert changed["independent_floor"]==ts["independent_floor"]
    if cutoff is not None:
        assert ev.min()>=cutoff and pilot.min()>=cutoff
        assert ts["independent_floor"]>=cutoff and ts["oracle_correct_selection"]>=cutoff
        g=setting["shape"]
        u=cutoff+.01
        excess=np.linspace(.001,.25,20)
        conditional=stats.genpareto.logpdf(u+excess,g)-stats.genpareto.logsf(u,g)
        stable=stats.genpareto.logpdf(excess,g,scale=1+g*u)
        assert np.allclose(conditional,stable,rtol=1e-10,atol=1e-10)
    else:
        assert ts["oracle_correct_selection"] is None
        values,_=failures_sample(rng_for(seed,99),setting["shape"],setting,config,10000)
        u=stats.genpareto.cdf(values.ravel(),setting["shape"])
        pit=soft_integral(u,config)/soft_integral(1,config)
        ks=stats.kstest(pit,"uniform")
        assert ks.statistic<.02
        checks.append({"case":"soft_generator_pit","samples":len(pit),"ks_statistic":ks.statistic})
    checks.append({"case":name,"passed":True,"cutoff":cutoff,"thresholds":ts})
tiny=dict(config)
tiny["statistics"]={**config["statistics"],"bootstrap":5}
tiny["seed"]=config["preflight_seed"]
result,arrays=analyze_dataset(tiny,"original_support",0)
for name in config["calibration_budgets"]:
    assert arrays[name+"_shape"].shape==(5,5)
    assert all(c["applicable"] for c in result["methods"][name].values())
for prior in ["runs/p3_validation_20260913/protocol.json","audit/revision_2026_09_13/p3_constrained_v1/protocol.json"]:
    old=read_json(base/prior)
    n=old["datasets"]
    old_seeds={old["seed"]+s["seed_offset"]+i for s in old["scenarios"].values() for i in range(n)}
    new_seeds={config["seed"]+s["seed_offset"]+i for s in config["scenarios"].values() for i in range(config["datasets_per_scenario"])}
    assert not old_seeds & new_seeds
out=here.parent/"preflight"
metrics=finite_json({"passed":True,"checks":checks,"optimizer_unchanged":True,
                    "holdout_threshold_independent_of_evaluation":True,
                    "fresh_seeds_disjoint":True,"tiny_pipeline_passed":True,
                    "primary_changed":False})
p=write_once(out/"metrics.json",metrics)
finish(out,stage="p3-selection-model-preflight",context={"source":digest(source)},
       inputs=[source,previous/"preflight/manifest.json",here/"candidate.py",here/"experiment.py",
               Path(__file__),here.parent/"protocol.json"],
       outputs=[p],metrics=metrics)
print("SELECTION_PREFLIGHT_PASSED",out,flush=True)
