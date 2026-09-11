# Additive readiness campaign, 11 September 2026

The existing `runs/lean_recovery_20260911_v3` campaign and `onebigjump-recovery` tmux controller
are protected. No existing job is cancelled, restarted or assigned new executable code.
The expansion uses a separate frozen source snapshot, queue, tmux controller and output tree:
`runs/expansion_20260911`. New GPU jobs receive lower scheduling priority (`--nice=10000`).

## What is ready, and what is evidence

The three-prover main collection already schedules 20,016 attempts across 417 eligible tasks,
two temperatures and eight attempts per temperature. It is sufficiently substantial to finish
before proposing another round of the same miniF2F problems. Repeated attempts improve precision
within tasks; they do not increase the number of independent benchmark problems or remove possible
training contamination. The pilot is a technical check and an inconclusive scientific result.
No expansion result automatically promotes a main estimate to a confirmed prediction.

### P1–P3: calibration before stronger claims

* Four prespecified Monte Carlo scenarios, 200 datasets each: equal heavy-tail populations,
  a shared positional confound without coupling, a known positive asymptotic tail-index contrast,
  and threshold-coupled GPD overshoots. Each dataset has 48 disjoint calibration and 48 evaluation
  task clusters, six attempts and eight steps. Run the actual main procedure with 500 task
  bootstrap draws, 200 inner k-selection resamples, all three estimators and family size nine.
  Availability, interval coverage and rejection rates are reported separately, with Monte Carlo
  uncertainty. These four distributions are a calibration screen, not a theorem about model data.
* A restricted positional control on every completed prover measurement: take the first eligible
  refuted trace ID per task, then permute failure positions across tasks within the exact same
  family and length. Omit singleton strata, disclose the retained population, and compare both
  localization and the paired advantage over surprisal. This preserves a common position trend
  that within-trace permutations destroy. It is a sensitivity analysis, not a replacement for
  all-trace P2; exchangeability within each stratum remains an assumption.
* Whitening sensitivities at shrinkage 0.05, 0.1 and 0.2, plus disjoint task subsets for fitting
  the transform and choosing the threshold. On main data, 50 task-resampled transform fits per
  model. Evaluation stays fixed in these refits: they measure transform instability and are not
  unconditional confidence intervals. Innovation remains diagnostic. Original primary estimates
  and their frozen transform are preserved.

The heavy-null P1 target is zero; in the tail alternative the asymptotic contrast is 0.4. A pooled
mixture can have slow finite-threshold convergence: poor coverage is a finding, not a reason to
change the target. The coupled-overshoot shape target is 0.25; failure-site sample sufficiency is
checked by the existing P3 gates. Missing intervals remain missing in the calibration summary.

### P4: durable, matched mechanistic replication

Five paired training seeds (0–4), each with modular-addition labels and a fixed permutation of the
same label multiset. Same train/test split, initialization, architecture and optimization in each
pair: p=113, d=128, four heads, MLP=512, train fraction=0.3, AdamW lr=0.001, weight decay=1,
betas=(0.9,0.98), 40,000 full-batch updates, checkpoint every 100 updates. Store model, optimizer,
RNG state, data indices and SHA receipts. Resume from the last complete checkpoint after node/time
failure; corruption or changed source/config fails closed.

A second pass chooses six key frequencies from the FINAL checkpoint and reuses them for all
restricted/excluded-loss measurements. This follows the mechanistic motivation of
[Nanda et al.](https://arxiv.org/abs/2301.05217); accuracy alone cannot identify circuit formation.
The prespecified anchor is the first checkpoint of five consecutive test accuracies >=0.90.
Compare median indices/losses in the five checkpoints before and five after (500 updates each),
using the REAL run's anchor for BOTH arms. Missing transitions and incomplete windows remain
missing. This anchor defines a reproducible diagnostic; it does not equate accuracy with a circuit.

All checkpoint curves report Hill, moment and GPD at a fixed 5% tail fraction. Separate full
k-selection and input-bootstrap analyses at updates 0, 10k, 20k, 30k, 40k report sensitivity and
conditional intervals. The selected k is fixed inside those input resamples; between-training
variation uses matched seeds, not p-squared input pairs as independent training replications.
Five pairs are a replication screen, not a high-power confirmation. A finite input population
cannot identify a literal asymptotic tail; discuss intermediate-scale behavior in the article.

### Controlled deduction and P5

A new single-entity modus-ponens task, inspired by step-verifiable synthetic deduction such as
[PrOntoQA](https://github.com/asaparov/prontoqa), is explicitly NOT a full PrOntoQA reproduction.
Qwen/Qwen2.5-7B-Instruct is pinned to the downloaded immutable model revision. Generated predicate
identities, disjoint tasks and prompt are frozen before sampling. Lengths are 3–12 with a unique
shortest proof chain and a distractor branch. The checker accepts only single supplied-rule
inferences from established facts and preserves the original completion offsets. Absorbing
failure labels apply from the first invalid step; unsupported formatting receives no invented t*.

Pilot: 40 tasks and 80 attempts. Main: 40 calibration plus 100 evaluation tasks per length,
1,400 tasks and 5,600 attempts (two attempts at each of T=0.6/1.0). Main requires pilot format
adherence >=90%, complete extraction of eligible traces, exact token/span alignment, independent
hook agreement and completed analysis artifacts. Semantic success rate is NOT a gate or resampling
criterion. All attempts, failures and truncations are retained. Generation does not receive
verifier feedback. The final answer is always true by construction; only the complete proof is
scored, so guessing the answer does not pass.

P1–P3 receive the same estimators and controls. P5 uses assigned-length intention-to-treat counts:
malformed outputs remain failures in the denominator. The exponential length fit is diagnostic;
it cannot separate theta from tau, its naive likelihood ratio ignores within-task dependence, and
assigned length is not the actual number of opportunities in a malformed proof. No mechanistic
P5 claim or confirmatory p-value is supported by that diagnostic alone. A later task-bootstrap
held-out predictive check, independent extremal-index measurement and tolerance intervention
are needed before making the full draft's P5 claim.

## Remaining article scope

The draft contains P1–P5, not numbered P6 and later predictions. Its additional promised settings
(two-hop composition, recurrent depth, Tracr/ngram mechanism controls, supervised probes, the
other general-purpose models and code tasks) lack a validated implementation/protocol here.
Starting placeholder jobs would not establish those results. Treat these as a second milestone
or remove the corresponding claims/settings from the article. First use the real primary data,
calibration and paired P4 to decide which extension would distinguish competing explanations.

## Should proof validity be increased?

Improve technical validity of measurement: exact source, correct parsing, pinned Lean environment,
whole-proof/replay agreement, trusted axioms and an independently reviewed label sample. A larger
pass rate itself is not the objective: P1/P2 need both verified and refuted trajectories. Do not
filter to successful proofs, repair main completions, use verifier feedback, or loosen the axiom
policy to improve the headline pass rate. Those interventions change the sampling distribution.
If studied, add a separately registered, budget-matched arm on development tasks and report all
attempts. Independent held-out tasks, calibrated uncertainty, positional/mechanistic controls and
honest negative outcomes strengthen the evidence more than repeated attempts on familiar tasks.

## Execution and interruption

Run format/lint/type checks plus all unit, live Lean and ML tests on Slurm before admitting new
work. Freeze src/scripts/tests/configs and this protocol with a SHA manifest. The host controller
only manages files/jobs; no scientific computation runs on the login node. Slurm owns each job;
`onebigjump-expansion` tmux owns the controller, so SSH disconnection affects neither. Each stage
checks upstream manifests and journals completed items. New submission caps: two GPU jobs and four
CPU jobs, with at most two long calibration/refit jobs. Infrastructure interruptions receive at
most three automatic retries; semantic/checker/code failures block dependent work. No automatic
cancellation or modification of any existing experiment is implemented.
