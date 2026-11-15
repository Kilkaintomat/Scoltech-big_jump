# Local scale-invariant tails: frozen protocol v1
Date: 2026-11-15. Deadline in request is explicitly waived by the user.
Status at freeze: no new real-data R/H/O outcomes or synthetic recovery results inspected.
Run: runs/rebuttal_local_tails_20261115_v1
Source: experiments/rebuttal_local_tails_20261115_v1

## Scope and execution
Saved scalar whitened norms only; no generation, no model forward, no recomputation from hidden vectors.
All scientific work and checks run through Slurm. Existing experiments and environments remain untouched.
No public repository publication. Report tables, numbers and figures are generated from metrics.
The request is copied as REQUEST_RU.txt. Input/source/output hashes and Slurm metadata accompany every job.

## Scientific clarifications fixed before outcomes
The signed GPD shape gamma is distinct from the paper's order parameter max(gamma,0). Do not clip estimates.
For exponential, lognormal and Weibull-min with positive shape, the upper extreme-value index is zero.
For an exactly GPD-distributed epsilon, its shape is the extreme-value index.
Fitting a zero-location GPD to finite-window ratios from another family estimates a pseudo-parameter;
scale invariance alone does not prove this pseudo-parameter is that family's extreme-value index.
Synthetic recovery must check this issue rather than assume it away.

An exponential mixture is Lomax when the exponential RATE is gamma distributed
(equivalently the SCALE has the corresponding inverse-gamma law).
For lognormal scale mixing the survival is E[exp(-x/sigma)], not automatically Lomax.
Positive finite-sample Hill, even without mixing, does not establish a Pareto tail.

Under exact threshold coupling max_before < tau < w_error,
log(w_error/max_before) > log(w_error/tau).
Thus O is an UPPER bound on the threshold log-overshoot. The request's lower-bound wording is reversed.
D measures a conditional record gap and does not identify an unobserved tolerance or the Kesten mechanism.
For iid continuous samples, conditional on the last observation being the record,
O has the same distribution as R for the full prefix length. Selection by a failure mechanism can change it.

Definitions of the simulated distributions:
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.genpareto.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.weibull_min.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.lognorm.html

## Populations, windows, nuisance-only inventory
Main cells: miniF2F T=.6 DeepSeek/Goedel/Kimina; ProofNet T=.6 DeepSeek/Goedel.
Secondary: miniF2F T=1 DeepSeek/Goedel/Kimina; PutnamBench DeepSeek/Goedel, failures only.
Readout: zero-based layer 14 DeepSeek, 17 Goedel/Kimina; last tactic token; formal-entry;
fold0 whitening, shrinkage .1. Raw norm w, not log1p(w).
miniF2F .6 uses the saved evaluation score table used by Table 1/N5, including Kimina traces
that are in Table 1 but not eligible for supervised tactic-metadata fitting.
ProofNet failures are restricted to the immutable learned-comparison trace IDs:
DeepSeek 452/166 groups, Goedel 259/133. Assert exact IDs/labels and scalar agreement.
ProofNet verified attempts come from the same saved score table and only represented task groups.
miniF2F verified attempts are restricted to the same evaluation problem registry as failed attempts.
Putnam saved extraction failures: 118/58 DeepSeek, 48/35 Goedel.
T=1 uses already saved main-readout scores. Never recompute missing verified scores or substitute another
readout: report such secondary coverage missing. Do not invent a verified comparison where unavailable.

Window: verified all L; failed accepted prefix of length f=t*-1 (f is the saved zero-based error index).
Empty prefixes are retained in census but excluded from any statistic needing a positive length.
Minimum n: A >=3, B >=4, C >=5; D error position >=3 and strict positive record gap.
Nonpositive/nonfinite w are counted and rejected explicitly; no epsilon replacement.
Length and per-proof median inventory is allowed before real outcomes because it parametrizes the requested simulation.
No R/H/O or real family fits in this inventory.
Synthetic log-scale SD is sqrt(equal-group mean[(log median(w_window)-weighted mean)^2])
over nonempty primary windows; no subtraction of finite-window median sampling noise.
Simulation scales have log mean zero and that SD. This nuisance estimate does not identify latent scale dispersion.
The synthetic bank conditions on each exact integer window length. Synthetic group labels, attempt counts,
failed/verified flags and fixed folds reproduce the saved design.

## Weighting, folds, resampling
Equal problem/group weight, equal eligible attempts within a group. One R/H/O per proof for the relevant test.
For pooled C, equal eligible groups, then attempts, then steps within each attempt. This intentionally corrects
E9's old equal-group/equal-step weighting to the requested equal-attempt weighting, while reusing its density fits.
Use the original ProofNet five outer folds. miniF2F uses the immutable secondary group registry and five folds;
Putnam uses the archived localizer group folds if names match, otherwise deterministic GroupKFold(5)
on sorted unique groups, frozen in the inventory. No label stratification or outcome-driven reassignment.
For synthetic studies folds are held fixed from that inventory.
2000 multinomial whole-group bootstrap draws, with all shape choices and all fold training fits redone in each draw.
Group copies retain their original fold to avoid leakage. Train-only nuisance normalizations are refit as applicable.
Percentile 95% intervals. No interval with fewer than 20 contributing groups.
An interval also requires >=95% finite bootstrap replicates; otherwise report the failure fraction.
No unreported clipping, discarded support violations, or post-result tuning.

## Simulation-density bank and fixed grids
Seed master = 2026111507; each purpose/cell/family/replicate gets a deterministic SHA256-derived seed.
Families: exponential (scale 1); Weibull-min k=.30,.35,...,3.00;
lognormal log SD=.10,.15,...,2.50 (log mean zero);
zero-location GPD shape=-.50,-.45,...,1.50 with scale 1.
GPD shape 0 and Weibull k=1 reuse the exponential bank exactly.
No extra Pareto candidate in A/B/D: the decision rule's GPD-or-Pareto alternative is tested using GPD.
Every integer n has 65536 iid simulated order-statistic windows per parameter (>=20000).
Top order statistics may be sampled directly from uniform order statistics; this is exact,
not an approximation that changes the window law.
Use common uniforms across parameter values; independent seeds for bank and validation data.
Gaussian KDE on log of positive R/H/O with fixed bandwidth h=.15 in log-statistic units.
Numerical implementation: linear-binned KDE, grid [-28,6] spacing 1/128, Gaussian convolution truncated
at 8 bandwidths. Linear interpolation of density; include Jacobian 1/statistic.
Do not silently extrapolate beyond grid: mark numerical validation failure. Zero density remains nonfinite.
Conditional record D uses the R bank at n=t*, justified by exchangeability.
Thin A: M2 is largest at distance >=2 indices from the earliest maximum; exclude if none exists.
Its simulation accounts for random positions and this eligibility, drawing until >=65536 eligible windows.
For n>=4 the top four order statistics and their random distinct positions suffice.
No KDE bandwidth refitting in the bootstrap; bank is an externally simulated fixed reference distribution.

## Step 0: sequential mandatory synthetic gate
The gate is deliberately sequential. Complete the frozen 0A batch before considering real-data outcomes.
0A: for every available cell and each generating family exp, LN(.5), Weibull(2), GPD(.2), GPD(.5),
generate 100 independent data sets with the actual primary-window lengths, group structure and scales.
Refit GPD shape and all other family candidates from R for each data set; 2000 whole-group bootstrap
shape refits per data set; record known-family fitted parameter, mean GPD shape, bias relative to true
signed extreme-value index, bootstrap coverage, grid-boundary frequency and numerical issues.
Calculate heldout NLL points with refitting on all five train folds.
A finite-window estimator may be noisy, so a systematic recovery failure requires BOTH:
(1) |mean GPD shape - known extreme-value index| > .10 (two GPD grid steps);
(2) |bias| - 3*MCSE > .10, where MCSE is the SD of the 100 independently fitted shapes / sqrt(100).
This is a predeclared conservative Monte Carlo diagnostic, NOT a group-bootstrap CI.
A reproducible failure in any main cell/family fails the literal universal-index recovery requested.
Also fail if the correctly specified generating-family parameter has systematic bias
over .10 for GPD/LN or .20 for Weibull by the same three-MCSE rule.
Out-of-grid statistics, invalid density normalization, or insufficient finite estimates are explicit gate failures.
Bootstrap intervals remain group intervals; the Monte Carlo repeat distribution is reported separately.
Check exact scale cancellation and exponential-R analytic CDF against the simulation bank.
For each replicate compute original N5 pooled Hill using select_k(double_bootstrap,k_min=20,resamples=200)
on both sigma*epsilon and epsilon, retaining chosen k and fallback status. Pairing shows what scale mixing adds;
a positive Hill value alone is not labelled an asymptotic Pareto artifact.

If 0A fails: STOP new real-data analyses A-D; do not retune grids, bandwidth, threshold or gate.
Produce a failure report, complete 0A metrics and manifest; mark B/C/D calibration, full-rule type-I,
real-data tests and associated figures NOT RUN because the prerequisite failed.
Do not replace the user's empirical heavy-tail verdict by a synthetic verdict. Its status is NOT EVALUATED.
The report explains whether parametric finite-window shape can be recovered even though universal EVI cannot.
This explicit stop has priority over the downstream deliverable list.

Only if 0A passes, continue 0B:
- repeat B and D shape-recovery calibration with the same 100 generators/designs, thresholds and CIs;
  for D simulate full windows through the assigned error position and condition on last being a record.
- C raw/normalized diagnostics on the same synthetic data, with original estimators and all safeguards;
- 100 independent five-main-cell batches per exponential and LN null. In each batch refit
  all decision-rule components including 2000 group bootstrap fits and thin-A.
  Report empirical false-support rate, binomial Wilson 95% interval and false-not-supported rate.
- Gate fails if full-rule false-support rate >.05 with Wilson lower bound >.05.
Only after all these gates pass may new real-data A-D outcomes be computed.

## Planned real A (conditional on all gates)
R=log(M1/M2). Weighted means in bins 3-5,6-10,11-20,21-40,41+.
Weighted OLS intercept and log(n), group refit CI.
Exponential conditional PIT and mean observed minus simulated expectation.
Select shape by weighted maximum likelihood on train groups; fixed five-fold heldout NLL;
full-cell GPD shape and bootstrap CI are primary.
Primary decision applies to combined verified and accepted-before-failure windows; P1 splits them,
using joint group bootstrap for failed-minus-verified shape and indicator coefficient in R~1+log(n)+failed.
Sensitivity: thin A (distance>=2 with matching bank), n>=10, position normalization.
Position normalization uses verified calibration attempts; ten relative-position bins floor(10*t/L), capped at9,
equal-group/attempt/step weighted median; missing bins nearest available bin, ties lower;
refit calibration median per bootstrap and exclude absent calibration support. No target-outcome fitting.
Five-fold fits use only calibration or train-fold verified groups, never heldout groups.

## Planned B
H=.5*(log(M1/M3)+log(M2/M3)), n>=4. Same weights, exponential PIT/expectation,
conditional simulation-density fits, heldout NLL, GPD shape and P1 bootstrap difference as A.

## Planned C
Primary scale s=median(primary window), n>=5. Verified uses full proof; failed uses accepted prefix only.
Apply this SAME pre-failure s to accepted, first-error and post-error diagnostic values; never use post-error
values to estimate s. Post-error diagnostics are explicitly secondary and do not enter A/B/D or the main verdict.
Reuse E9 lp and fit_family from experiments/extensions_20261108_v1/tails_rank_v2.py
on raw w and u=w/s; train-only weighted thresholds .90,.95, >=80 training exceedances in >=20 groups.
No clipping of test values outside fitted GPD support. Refit thresholds and parameters every group bootstrap.
N5 uses select_k(double_bootstrap,k_min=20,resamples=200) and weighted_fit from
experiments/rebuttal_noise_20261115_v1/n5.py, for verified/before/at/after.
Refit k within every bootstrap; report signed Hill/moment/GPD and all failures.
Median self-normalization (including the maximum) and short-window dependence are explicit limitations.
No cross-scale comparison of absolute raw and normalized NLL: compare families within each scale.

## Planned D
Failures with f>=2 and w[f]>max(w[:f]); O=log ratio. Strict records; ties excluded.
Weighted slope on log(f), bootstrap refit. Fit R-like bank at n=f+1 under record conditioning.
For each target position k=f+1, later-failing donor attempts with error position>k contribute accepted records.
Only donors from the same saved selected population. C2 requires common supported positions.
At a target position average O over eligible donor records by equal donor group, then attempt.
A donor may contribute to several positions, but each failure contributes one target O and one standardized
control mean; cluster-bootstrap entire donor and target groups jointly and rebuild controls.
Primary target-minus-control mean and regression adjustment for log(k-1), with donor support counts.
No interpreted independence of the overlapping prefixes; resampling is at whole-group level.

## Frozen decision rule (real data, only after gate)
SUPPORTED only if in the same >=4/5 main cells:
GPD A CI lower>0; GPD heldout NLL beats BOTH exponential and lognormal with refit-bootstrap gain CI lower>0;
and all these conditions survive thin A.
NOT SUPPORTED if GPD A CI upper<=.05 in >=4/5 main cells.
Otherwise UNDETERMINED; unavailable intervals cannot satisfy either side.
No pooling of p-values, tuning on secondary cells or substitution of fitted GPD shape for a validated universal EVI.
P1 reports per-cell differences only. P3 reports D slopes/contrasts only.
This rule cannot validate a Kesten recursion, latent reference trajectory or causal failure mechanism.

## Outputs
REPORT_RU.md generated from metrics; synthetic recovery/mixing CSVs and plots; gate.json;
protocol.md and protocol.sha256; sources, job history, manifests and input/output hashes.
If gate passes: all A-D metrics/CSVs/sensitivities and PIT/R/O figures as requested.
If gate fails: status table for every downstream item with reason; no empty results presented as computed.
RU/EN reviewer text for 1ooR B1a, wDaH B1,22Kj C1 includes an immediately usable actual-status version
and clearly conditional supported/not-supported/undetermined templates. P4 is not tested by this task.
