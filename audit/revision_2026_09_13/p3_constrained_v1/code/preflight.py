"""Numerical correctness checks before independent validation data are generated."""
from pathlib import Path
from collections import Counter
import os
import warnings
import numpy as np
from scipy import optimize, stats
from candidate import constrained_gpd_fit
from onebigjump.e1.artifacts import read_json, write_once, finish, digest, verify_manifest
from onebigjump.e1.analysis import finite_json

base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
here = Path(__file__).resolve().parent
out = here.parent / "preflight"
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
previous = base / "runs/p3_fit_diagnostics_20260913"
verify_manifest(previous / "manifest.json")
config = read_json(here.parent / "protocol.json")
# Published data and rounded target estimates: Grimshaw 1993 Table 1 / section 4.
nylon = np.array([.051,.140,.365,.561,.030,.268,.184,.100,.876,.092,.011,.200,.518,.338,.056])
known = constrained_gpd_fit(nylon)
assert known.converged and abs(known.gamma + .117698) < 2e-6
assert abs(known.sigma - .283040) < 2e-6 and abs(known.loglik - 5.697968) < 2e-6
cases = [("published_nylon", nylon)]
for shape in [-.8,-.4,-.2,0,.25,.8,2]:
    quantiles = (np.arange(1, 257) - .5) / 256
    cases.append(("quantile_control:" + str(shape), stats.genpareto.ppf(quantiles, shape)))
cases += [("constant", np.ones(20)), ("near_constant", np.linspace(.99,1,20)),
          ("exact_exponential_stationarity", np.array([1.,1.,1.,1.,6.]))]
for example in read_json(previous / "examples.json"):
    cases.append((example["trace_id"] + "/" + example["method"] + "/" + str(example["bootstrap_index"]),
                  np.array(example["excesses"])))
results = []
failures = []
for index, (name, values) in enumerate(cases):
    fit = constrained_gpd_fit(values)
    dense = constrained_gpd_fit(values, grid_size=2049)
    consistent = fit.converged == dense.converged and abs(fit.loglik-dense.loglik) < 1e-5
    if not consistent:
        failures.append([name, "grid_resolution"])
    scale_checks = []
    for scale in [1e-8,1e8]:
        other = constrained_gpd_fit(values * scale)
        ok = (fit.converged == other.converged and abs(fit.gamma-other.gamma) < 1e-6
              and np.isclose(other.sigma / scale, fit.sigma, rtol=1e-6))
        scale_checks.append(ok)
        if not ok: failures.append([name, "scale_equivariance",scale])
    permuted = constrained_gpd_fit(values[::-1])
    if not (fit.converged == permuted.converged and abs(fit.gamma-permuted.gamma) < 1e-6):
        failures.append([name, "permutation_invariance"])
    # Independent two-dimensional objective, normalized by max for scale stability.
    r = values / values.max()
    def nll(theta):
        gamma, logsigma = theta
        sigma = np.exp(logsigma)
        if sigma + gamma <= 0:
            return 1e8 + 1e5 * abs(sigma + gamma)
        result = -np.sum(stats.genpareto.logpdf(r, gamma, scale=sigma))
        return float(result) if np.isfinite(result) else 1e12
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        reference = optimize.differential_evolution(
            nll, [(-.999999,8),(-30,5)], seed=71313000+index,
            maxiter=500, popsize=12, tol=1e-10, polish=True,
        )
    # Boundary is known exactly; no fitted data or target shape enters it.
    reference_nll = min(0.0, float(reference.fun))
    candidate_nll = -fit.loglik - len(values) * np.log(values.max())
    gap = candidate_nll - reference_nll
    if abs(gap) > 1e-4:
        failures.append([name, "independent_objective",float(gap)])
    if name in ["constant","near_constant"] and (fit.converged or fit.gamma != -1):
        failures.append([name, "boundary_not_flagged"])
    results.append({"case":name,"fit":fit.as_dict(),"dense_fit":dense.as_dict(),
                    "scale_checks":scale_checks,"reference_nll":reference_nll,
                    "candidate_nll":candidate_nll,"objective_gap":gap,
                    "reference_success":bool(reference.success)})
    print(name, fit.reason, fit.gamma, "objective_gap", gap, flush=True)
try:
    constrained_gpd_fit([1,2,3,4,np.nan,-1])
    failures.append(["short_input","not_rejected"])
except ValueError:
    pass
clean = constrained_gpd_fit(np.r_[nylon, np.nan, np.inf, -1,0])
assert clean.n_excesses == len(nylon) and abs(clean.gamma-known.gamma)<1e-12
old_config = read_json(base / "runs/p3_validation_20260913/protocol.json")
old_seeds = {old_config["seed"]+i+s["seed_offset"] for s in old_config["scenarios"].values()
             for i in range(old_config["datasets"])}
new_seeds = {config["seed"]+i+s["seed_offset"] for s in config["scenarios"].values()
             for i in range(config["datasets"])}
assert not old_seeds & new_seeds and len(new_seeds) == config["datasets"]*len(config["scenarios"])
metrics = finite_json({"passed":not failures,"failures":failures,"cases":len(cases),
    "fits":results,"case_categories":dict(Counter(r["fit"]["reason"] for r in results)),
    "published_reference_fit":known.as_dict(),"fresh_seed_overlap":len(old_seeds & new_seeds),
    "primary_changed":False,"protocol_sha256":digest(here.parent/"protocol.json")})
p = write_once(out/"metrics.json",metrics)
finish(out,stage="constrained-gpd-numerical-preflight",
       context={"source":digest(source)},
       inputs=[source,previous/"manifest.json",Path(__file__),here/"candidate.py",
               here.parent/"protocol.json",base/"runs/p3_validation_20260913/protocol.json"],
       outputs=[p],metrics={"passed":not failures,"cases":len(cases),"primary_changed":False})
assert not failures, failures
print("PREFLIGHT_PASSED", out, flush=True)
