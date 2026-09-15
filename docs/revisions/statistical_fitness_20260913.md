# Statistical fitness amendment, 2026-09-13

This is a supplementary analysis amendment after pilot results and P3 calibration have been seen.
The frozen primary cell, original family of nine, original estimators, bootstrap gates and all
negative results remain in force. This amendment does not turn existing data into a fresh
confirmatory experiment.

## Questions and estimands

The practical question is whether a deviation score helps localize the first error beyond token
surprisal and simple position. The mechanistic question is whether intermediate-range tails and
the proposed coupling explain this. Success on the practical question alone does not establish
the mechanism; failure to reject a shape null does not prove algorithmic reasoning.

Add paired top-1 gain per task, equal weighting across tasks, on identical finite-score traces.
Retain all eligible attempts inside each task. Report the task mean, a Hoeffding bound for bounded
independent task means, and an exact sign screen for win probability among non-tied task effects.
The sign screen tests a different estimand from mean gain and needs iid task signs. No claim that
permuting algorithm labels is justified merely by a mean-zero null. Below twenty tasks the
existing bootstrap is still unavailable; the new bounds are finite-sample inequalities, not an
attempt-level bootstrap fallback. Fixed-benchmark generalization remains an assumption.

Report the earliest-position baseline and uniform-position reference, and retain the existing
restricted family/length permutation control. Report a separate drop-first population, with
excluded failures counted. Normalized failure-rank gain is exploratory only.

For threshold coupling, add accepted-step exceedance and first-failure exceedance per task,
plus their difference on tasks with both types. No GPD fit is needed for this finite-threshold
question. Exclude every post-failure step from accepted-step denominators. Threshold and transform
must be independent of evaluation tasks; reusing transform-fit data to set the threshold remains
a calibration defect. Original and already planned disjoint-transform/threshold controls stay
separate. These rates do not establish asymptotic tail shape or the overshoot limit.

Only the three model-specific whitened primary-cell supplementary gains form a family of three;
report Bonferroni simultaneous bounds for that explicitly named family. Other temperatures,
layers, raw/innovation scores, ranks and exclusion variants are exploratory. Do not substitute
this new family for the original family of nine.

## What remains strict, and why

Keep prompt-level dependence, source/label integrity, independent transform/threshold/evaluation
splits, signed moment/GPD estimates and all three estimators. The twenty-task and exceedance
cutoffs are screening heuristics for a difficult tail estimator, not universal laws. Reducing
them would not fix the observed undercoverage. Keep q=0.001 as a sparse-tail diagnostic when
unsupported. A larger number of bootstrap replicates refines Monte Carlo quantiles, not the
underlying data or estimator bias.

A confidence interval containing zero is inconclusive about a zero shape. A negative estimate
alone is not a proof of the model's algorithmic mechanism. Equivalence requires a scientific
margin fixed independently of the observed effect. P4's independent units are training seed
pairs, not checkpoints.

## Processing and sample growth

First finish verification of saved completions. The validated concurrency implementation is
now launched through an adaptive node-capacity guard: one or two independent Lean processes
inside a 32-CPU allocation, with unchanged proof budgets and one parent journal writer.
The initial four-process production attempt hit the shared node file-handle limit before
writing any labels and was rolled back. The final guard checks file-nr/file-max, reserves
capacity, and holds a per-node project lock for the whole job. It does not control other users'
future load and can reduce concurrency when resources are scarce. Existing running jobs retain
their source and parameters. No regeneration is required.

The completed operational correction, benchmark, tests, rollout history and provenance are in
[the final review](../../audit/revision_2026_09_13/statistical-fitness-v1/report-v2/REPORT.md).
The immutable statistical-fitness-v1 snapshot retains the original amendment text; this paragraph
records the later operational correction. The statistical methods and primary protocol are unchanged.

Use task-based sample planning. Repeated attempts improve within-task estimates but do not
create new independent tasks. If expansion is still needed after the full fixed batch, favor
new, disjoint prompts and more independently verified calibration tasks; freeze the next batch
size and stopping point using precision/cost rather than observed significance. Never pool
models/layers/steps as new independent samples.

## Sources

- Hoeffding (1963), probability inequalities for bounded independent variables:
  https://doi.org/10.1080/01621459.1963.10500830
- SciPy exact binomial/sign-test implementation and exact proportion intervals:
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html
- SciPy permutation-test null hypotheses and pairing assumptions:
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html
- Python concurrent.futures, independent external process coordination:
  https://docs.python.org/3/library/concurrent.futures.html
