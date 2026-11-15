# Projection tails and scalar-Kesten calibration: protocol v1
Frozen 2026-11-15 before any new real projection/tail outcomes.
Run: runs/rebuttal_projection_tails_20261115_v1.
Original requests: REQUEST_RU.txt, PROMPT_local_tails.md. No public publication.

## Scope and safeguards
Saved refined step boundaries, hidden states/increments, labels, OOF splits and geometry normals only.
No language-model generation or forward passes. All numerical work, validation and report generation
runs through Slurm on Zhores. Existing jobs and environments are not changed.
Tables and narrative numbers are rendered from metrics. SHA-256 of this protocol is frozen first.
A mandatory sequential synthetic gate precedes reading/calculating any new real projections.
A failed gate stops real tests 1–5 and their scientific verdicts, and produces a complete calibration report.
No retuning of grids, bandwidths, seeds, rejection criteria or window rules following outcomes.
Implementation defects may be repaired with an audit trail; this does not authorize changing the protocol.

## Interpretation fixed before outcomes
The geometry results establish usefulness for specified probes, not sufficiency of a single direction
or absence of all information in its orthogonal complement. They do not measure a Gaussian bulk.
The identity ||d||^2 = (n'd)^2 + ||(I-nn')d||^2 holds for unit n in raw coordinates, not for an
arbitrarily whitened norm. Concentration near sqrt(d) requires specific scale/isotropy assumptions.
A projection with positive spectral mass inherits a regularly varying vector's index;
an exactly orthogonal projection with zero spectral mass need not.
In a diagonal recurrence, a generic projection usually inherits the heaviest coordinate tail.
Therefore the diagonal alternative below places the thinner tail in the designated axis and the
heavier tail in its complement; it does not presume that every random direction has a distinct index.
Symmetric independent innovations and positive scalar multipliers give a symmetric stationary
distribution with constant reference trajectory; real-state drift, selection, and nonstationarity
can break increment symmetry without refuting a latent symmetric error model.
Finite-threshold GPD shape and finite-window zero-location GPD ratio shape are not automatically the
asymptotic extreme-value index. The old local-tail calibration exposed this issue for LN/Weibull.
This study revalidates methods for its own signed projections and dependent vector recurrences.
Signed gamma is reported, alongside the paper's order parameter max(gamma,0), never silently clipped.
Sources: https://sites.stat.columbia.edu/rdavis/papers/mvreg2.pdf
https://arxiv.org/abs/1808.09678
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.genpareto.html

## Cells, refined boundaries, normals and leakage
Input rows/states: runs/tactic_granularity_full_20261113_v1/fine/data/{model}/{dataset}.
Geometry: runs/localizer_geometry_20261114_v1/stages/offline/{dataset}/{model}/{fold}/outer.
Use stored raw-coordinate unit Hn and Dn, and Hoffset. Their generating fixed hazard classifiers
had lambda=.01; standardized coefficients were already transformed back by dividing train SD.
Do not use conditional normals CHn/CDn or localizer normals LHn/LDn as substitutes.
Main: ProofNet DeepSeek OOF, ProofNet Goedel OOF, Putnam DeepSeek OOF.
Secondary: Putnam Goedel OOF, ProofNet-to-miniF2F and ProofNet-to-Putnam frozen, both models.
Putnam OOF and ProofNet-to-Putnam are distinct readouts of the same target population.
OOF failed groups use exactly geometry offline_splits; all attempts of each task use its test-fold normal.
Verified attempts in these same task groups use that same normal (not one fitted on the task).
Verified groups outside the failed offline registry are excluded and counted, without inventing a fold.
miniF2F transfer uses full-ProofNet frozen normals; target groups must not intersect source groups.
All saved normal hashes, train/test IDs and state source manifests must be checked before real use.
If a normal is missing, refit with the unchanged frozen geometry source and fixed hyperparameters.
Nuisance inventory first reads only lengths, group/trace IDs, f, splits, and normal train-group metadata.
It may record expected state hashes but does not compute any projection or tail result.
The refined population is authoritative; old coarse counts are not silently imposed on different boundaries.

## Step statistics and windows
Raw increments d_t=X_t-X_(t-1), original formal-entry anchor, raw coordinates.
sD=Dn'd, sH=Hn'd, h=Hn'X+Hoffset, q=norm(d-Dn*sD),
r=norm(d), w=stored whitened norm. Twenty fixed independent Gaussian unit directions, seed fixed,
in the same 4096-dimensional space; no selection on labels. Reused across folds within each model.
Analyze positive and negative values separately, excluding exact zero and reporting exclusions.
Verified window: all L; failed P1/accepted window: f=t*-1. No error/post-error values in P1.
At-error and post-error describe selected/unreached positions, never accepted negative examples.
Local A: original window length>=3 AND at least two strictly positive values; condition bank on their count.
Local B: original length>=4 AND at least three positives; condition on positive count.
C: original length>=5, scale=MAD of signed values about their within-window median; no epsilon replacement,
exclude MAD<=0 with counts. Its median/MAD includes tested values, a stated dependence.
D: t*>=3, positive error score and positive previous maximum, strictly larger at error.
C2 donors: accepted records at the same position in other task groups with failure later/verified;
keep original C2 matching/weights. No label-blind interpretation of this selected contrast.
Under exact threshold coupling, record gap log(error/max_before) is an UPPER, not lower, bound
on log(error/tolerance). Selection can truncate accepted-prefix tails.

## Weights, uncertainty and folds
Group -> eligible attempt -> eligible step, equal weights at each level; A/B/D one statistic per attempt.
2000 multinomial whole-task bootstrap draws; percentile 95% intervals only >=20 contributing groups
and >=95% finite draws. Joint contrasts share the same group multiplicities, including absent groups.
Refit all tail/family parameters, thresholds, k and fold-training fits in every bootstrap.
Saved OOF normals and external simulated density banks are fixed measurement definitions:
intervals are CONDITIONAL on these normals, not uncertainty in relearning a classifier.
This interpretation follows the instruction to reuse saved normals and is reported explicitly.
Copies of groups remain in their original folds; no resplitting or train-test overlap.
Global E9: 5 folds, training quantiles .90,.95; >=80 train exceedances in >=20 groups.
Reuse E9 likelihood implementations Pareto/exp/truncated LN/GPD; correct weights to group/attempt/step.
Report all folds, support failures as infinite NLL, no support clipping.
N5: Hill/moment/GPD, double-bootstrap k selection (k_min=20, 200 resamples), rerun k each resample.
Local A/B/D: exp; Weibull .30:.05:3; LN logSD .10:.05:2.50; GPD -.50:.05:1.50.
Fixed KDE of log(R/H/O), bandwidth .15, grid [-28,6] spacing 1/128, 8-bandwidth convolution;
65536 simulated windows per exact positive count and parameter. Bank/data seeds independent.
Reuse bit-identical old A bank where available; generate missing n including n=2 with same algorithm.
Known GPD(0) and Weibull(1) exactly share exponential reference.
Local CV refits shape on training groups. R=log(top1/top2);
B=.5*[log(top1/top3)+log(top2/top3)]. A/GPD signed shape is the primary local statistic.
A thinning, long-window n>=10, position-normalization sensitivity inherit the local-tail request;
no real sensitivity analysis is run if the synthetic gate fails.

## Seed and sequential mandatory validation
Master seed 2026111511; tags hashed SHA256, first eight bytes little endian.
20 random directions, 4096 dimensions, 100 independent datasets per generating case and unique target cell,
2000 whole-group resamples per dataset; no adaptive sample-size changes.
Six unique target populations; duplicated Putnam transfer/OOF populations reuse the same synthetic design,
since synthetic designated directions are prescribed, not fitted to real labels.
Synthetic windows use exact observed accepted/verified lengths, group weights and fixed folds.
Empty windows counted. Synthetic failures are independent of generated values; this isolates the estimator.
Saved real normal coefficients are NOT inspected during the gate; synthetic normal=e1.

0V numerical validation precedes simulations: finite/unit direction checks, exact projection/norm
decomposition, full-vector vs reduced-space distributional validation, exp ratio CDF, group weighting,
bootstrap refitting checks, and hash/fold checks. No environmental changes.

0A masking:
For each step, first coordinate is an independent fair sign times GPD(xi,scale=1,loc=0),
xi in {0,.2,.5}. Remaining 4095 coordinates iid N(0,1), independent over time and attempts.
This is a specified masking example, not an estimated model of real residual streams.
Generate exact 4096-dimensional projection/norm laws via the span of e1 and 20 random directions
plus an independent chi-square radial remainder. A direct full-vector simulation validates this reduction.
Fit local A to positive e1, its negative, each random direction, raw norm and perpendicular norm.
Projection recovery must not have a systematic signed-shape bias exceeding .10:
FAIL if abs(mean bias)>.10 AND abs(mean bias)-3*MCSE>.10 in any main cell/xi.
Masking is demonstrated by a larger absolute raw-norm bias than e1 bias for heavy cases, with
99% paired Monte Carlo CI excluding zero; xi=0 is descriptive. If not shown in >=2/3 main cells
for BOTH heavy cases, gate fails (the stipulated demonstration did not generalize to the fixed design).
Numerical finite-rate gate: >=95% finite fits and bootstrap draws for each main combination.
If 0A fails, stop without running 0B or real tests; unfinished calibration entries are explicit.

0B scalar and diagonal recurrences (run only after 0A passes):
B_t iid N(0,I4096), independent multipliers/attempts; burn-in 1024 from zero, then actual window lengths.
Scalar: log(a)~N(-alpha*.6^2/2,.6^2), alpha=3 and 5. Thus E log a<0, E a^alpha=1.
Analyze increments E_t-E_(t-1), not levels.
Diagonal alternative: alpha=5 on axis e1, alpha=3 shared scalar on other 4095 axes,
independent first/bulk multipliers, same innovations. Hence e1 xi=.2, generic random xi=1/3.
Shared bulk is a diagonal matrix with two blocks; it is not a fully independent-per-coordinate model.
Efficient exact law simulation retains coordinates in the 21-dimensional span and the perpendicular
radius; Gaussian radial updates preserve dependence between new state and increment norms.
Validate it against full-vector simulation before outcomes.
First test the necessary local-A part of test 4 and test-5 exceedance symmetry:
all three paired shape contrasts (n-median_random, n-perp, n-norm), plus log positive/negative
exceedance ratio at absolute-value weighted quantiles .90,.95,.99, threshold refitted per draw.
Zero counts give infinite log ratio, not pseudocounts; report invalid/one-sided intervals.
For the decision's random control use the median of the 20 log ratios, refitted per bootstrap,
and also show each direction individually; no cherry-picked random direction.
Report per-cell rejection rates and Wilson 99% Monte Carlo intervals.
Type-I failure if the 99% lower bound exceeds .10 for a nominal .05 contrast/symmetry test
in ANY main scalar-cell/alpha combination. The .10 tolerance is prospective, not a revised nominal size.
Tests 4 includes norm/perpendicular contrasts, so a failure there invalidates interpreting them as
equal-asymptotic-index tests, even if n-vs-random is calibrated.
Power gate for the diagonal n-vs-random local-A contrast: 99% lower bound >.50 in >=2/3 main cells.
Report all secondary cells without forcing low-powered secondaries to pass.
For every replicate, combine three main cells exactly as the requested Kesten rule: >=2 reject
n-vs-median-random OR signed-q95 asymmetry with median-random CI including zero.
Report this decision's scalar-null type-I and diagonal power, not only individual contrasts.
Local-A heavy-tail necessary conditions are counted, clearly distinguished from the FULL heavy-tail rule.
If this necessary calibration fails, STOP. Do not assert full-rule type-I was measured.
Only if 0B passes proceed to full E9/N5/B–D synthetic validation and full heavy-tail-rule type-I,
using the same generators, seeds, 100 replicates, 2000 draws, grids and type-I tolerance.
LN(.5), Weibull(2), exp light-tail inherited controls use fair signs and Gaussian bulk.
No real-data decision can pass without the FULL heavy-tail rule's calibration.
A mandatory early stop is a completed gate outcome, not a negative real-data tail result.

## Real tests 1–5 (conditional on ALL validation gates)
1. Global signed tails sD+/-,sH+/-, h+/-, raw r,w,q by verified/before/at/after:
E9 heldout family NLL and N5 all estimators; same table for each random normal; median,5–95% random range.
2. Local A–D above, P1 before-vs-verified; skip fractions by positive counts/length/MAD;
failed accepted and verified remain separate P1 populations. D C2 control and record selection flagged.
3. Accepted steps: all, raw-norm top5%,top1% weighted by group/attempt/step, one raw max per window.
Mean signed cos, mean abs cos, P(cos>0), mean cos²; same selected steps with each random direction.
At-error separate and selected by construction. Rank by raw norm for max signed-projection step.
Refit selection quantiles during bootstrap. Report distributions and joint tail plots.
4. Accepted local-A and global signed-shape contrasts n-median_random, n-perp, n-norm;
positive/negative learned direction and all twenty positive random directions.
5. Tail-shape positive-minus-negative and signed exceedance log-ratios for sD/sH and each random
at symmetric abs quantiles .90,.95,.99. Drift/selection caveat applies to mechanistic interpretation.

## Frozen decisions
Heavy tail SUPPORTED only if all three main cells have local-A lower CI>0; in >=2/3 cells a GPD
or Pareto beats BOTH exp and LN in heldout NLL with CI excluding zero; and learned local-A point
shape exceeds the empirical .95 quantile of random-direction point shapes in ALL three main cells.
Use q=.90 as primary E9 threshold; q=.95 sensitivity, no choosing the favorable threshold.
NOT SUPPORTED if local-A upper CI<=.05 in ALL three main cells. Otherwise UNDETERMINED.
Scalar Kesten REJECTED by the stipulated observational rule if >=2/3 main cells satisfy
(a) local-A learned-minus-median-random CI excludes zero OR
(b) signed q=.95 log-ratio CI excludes zero while median-random CI includes zero.
This does not identify a latent error-reference decomposition and is not a universal rejection theorem.
P1 and P3: per-cell contrasts only, no aggregate verdict. Putnam lacks verified controls.
If a required gate fails: all real-data decisions NOT TESTED, never NOT SUPPORTED/REJECTED.

## Deliverables
REPORT_RU.md, protocol.md and SHA256, metrics.json, CSVs, manifests, source code, calibration
plots/results and explicit status for every requested test. Full real figures only if gate passes.
RU/EN reviewer text for 1ooR B1a, wDaH B1/22Kj C1, paper Sec9/AppendixF:
report the actual status; supported/non-supported alternatives are marked conditional templates,
never presented as measurements when the prerequisite tests were not run.
