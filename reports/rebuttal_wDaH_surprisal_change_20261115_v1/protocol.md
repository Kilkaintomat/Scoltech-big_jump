# Surprisal-change ablation for reviewer wDaH B2

Date fixed: 2026-11-15 (Europe/Moscow). Deadline: 2026-11-16 22:00 Europe/Moscow.
All computation and tests run in Slurm on Zhores; only saved data and frozen source code are used. No LLM generation, new forward passes, GPU work, public publication, or changes to existing jobs/results.

## Estimand and cohorts
Retrospective first-rejection localization conditional on a localized failed proof. All generated tactic candidates are available to the conditional softmax, including candidates after the first rejection. This is not streaming or binary error-presence prediction.
ProofNet T=0.6: DeepSeek 452 attempts / 166 exercise groups; Goedel 259 / 133.
PutnamBench: DeepSeek 118 / 58; Goedel 48 / 35.
Use original ablation load_rows and unchanged labels, jump scores, surprisal, group IDs and attempt order. Assert these four counts before fitting; a mismatch stops the study and requires an explanation, not population repair.

## Fixed implementation and feature columns
Import experiments/localizer_feature_ablation_20261113_v1/run.py, its revision_20261107_v1/localizer.py and audit/lean_localizer_20260925_v1/engine.py unchanged.
S: standardized mean-surprisal spline columns selected by split_columns(preprocessor)['S']; cubic, train-only weighted knots at 0, 1/3, 2/3, 1; include_bias=False, constant extrapolation; original linear fallback if insufficient distinct knots.
D is exactly localizer.deltas(rows): column 0 delta_surprisal_signed = q[t]-q[t-1], column 1 delta_surprisal_absolute = abs(q[t]-q[t-1]); both set to 0 for t=1. Standardize using localizer.extra_prep, with train-only weights 1/(G*n_group*L), original variance floor 1e-10.
There is NO dedicated missing-predecessor column in D. The archived metadata says "existing first indicator, no duplicate column": first is a separate P column in M0/MD and is excluded here. Therefore the requested no-indicator version is identical to the primary D and is not separately fitted or counted. The deterministic first-step zeros may implicitly reveal position; do not call D wholly position-independent.
W: the exact standardized log(1+jump) final column from M0W, with train-only mean and scale.
Arms: S, SW, SD, SDW, D, DW. SD=[S,D]; SDW=[S,D,W]; D=[signed,absolute]; DW=[D,W]. No position, relative position, first/last, tactic type or tactic-token-count columns.

## Fixed fitting and splits
Every arm is retrained independently with the archived conditional logit engine.
Ridge lambda grid: 0.0001, 0.001, 0.01, 0.1, 1, 10. Selection minimizes pooled inner OOF group-weighted NLL; ties within 1e-10 use the largest lambda.
L-BFGS-B: original maxiter=3000, ftol=1e-13, gtol=1e-8, maxls=40; convergence requires success and gradient max <2e-5.
ProofNet OOF uses the exact archived outer=5 / inner=3 group splits at runs/lean_localizer_20260925_v1/splits.json.
PutnamBench OOF uses saved offline_splits.json from runs/localizer_putnam_stream_20261113_v1/data/<model>/Putnam/, unchanged; verify complete test coverage, no group overlap, and consistency with the saved population.
Frozen ProofNet -> PutnamBench uses each arm's lambda minimizing the mean of its five ProofNet-outer-fold inner-NLL values, exactly as the 13 November ablation; refit preprocessing and coefficients on all ProofNet and apply unchanged to Putnam. No Putnam tuning for transfer.
Equal weight per exercise group, then equal weight per attempt within group. Feature preprocessing additionally divides each attempt's weight equally among its L candidates. Earliest argmax tie-breaking is retained.

## Mandatory control gate
First fit S and SW on all ProofNet folds, compare with the archived per-trace probabilities, argmax and selected lambda from runs/localizer_feature_ablation_20261113_v1; maximum probability difference <1e-6 and zero argmax mismatches; NLL aggregate tolerance 1e-6.
Rounded ProofNet controls must equal 20.47 -> 27.92 percent DeepSeek and 24.06 -> 26.90 percent Goedel. Also compare the full-precision saved metrics, rather than only rounded values.
If the control does not reproduce, STOP new-arm computation and diagnose source/code/splits/environment. Do not adjust model settings to match.
Only after control_pass.json exists do SD/SDW/D/DW and other regimes fit. Reuse the freshly fitted control models; do not fit a second duplicate S/SW for ProofNet.

## Metrics and inference
Report equal-group Hit, +/-1 Hit and conditional NLL for all arms and regimes.
Fixed four contrasts: SDW-SD (primary), DW-D, SD-S, SW-S (control).
For each: delta Hit in percentage points and NLL gain = base minus new.
Paired bootstrap of whole groups with fixed predictions, B=20000, seed=2026111307, chunks=500, identical to the archived ablation report. Group means are computed before resampling, retaining within-group attempts. Percentile 95% individual intervals. No CI or test for fewer than 20 groups.
Two-sided centered-bootstrap p=(1+sum(abs(draw-observed)>=abs(observed)))/(B+1).
One PRIMARY Holm family across both models, three regimes, four contrasts, two metrics = 48 hypotheses. Report raw p, Holm p, individual CIs; do not relabel individual intervals as simultaneous.
Bootstrap does not include refitting or model-selection uncertainty. These are exploratory reanalyses of existing traces.

## Optional extension fixed before new outcomes
If saved eligible inputs and splits are available, run the same six arms and four contrasts on miniF2F T=0.6 for DeepSeek, Goedel, Kimina. Use the exact shared registry and splits under runs/revision_20261107_v1/secondary/miniF2F-T0.6/inputs/<model>. Do not regenerate or rebalance folds; audit counts and registry identities. Keep this extension separate from the six main model/regime cells.
A separate Holm family of 3 models * 4 contrasts * 2 metrics = 24 hypotheses; not pooled with the primary 48.

## Validation and provenance
Before fitting: input hashes, cohort counts, disjoint outer/inner groups, exact row/split consistency, finite features, unchanged labels, D first-step zeros, D-only dimension=2, excluded-feature invariance, equality of S/SW matrices to original ablation, equality of D columns to MD suffix, normalized probabilities, numerical gradient smoke check.
Save each fold's inner fits/NLL, selected lambda, preprocessing, named feature columns, trained coefficients, predictions and convergence diagnostics, manifest with protocol SHA, source/input/output SHA, commit/dirty status, versions and Slurm ID.
Report numbers are rendered exclusively from metrics.json. Each report/table is generated on Slurm. Save CSV, bootstrap arrays, manifests, source snapshots and Russian/English TODO B2 insertion text.
Existing artifacts remain read-only. Local copy and checksum verification only. No publishing and no repository visibility changes.
