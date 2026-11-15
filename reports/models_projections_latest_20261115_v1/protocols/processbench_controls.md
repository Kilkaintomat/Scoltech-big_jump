# ProcessBench uniform and positional controls — protocol v1
Date 2026-11-15. Run rebuttal_22Kj_processbench_uniform_20261115_v1.
Only saved E15/E16 data. CPU work and tests through Slurm; no generation, forward, GPU jobs or public publication.

## Input provenance and population
E15 root: runs/reviewer_gaps_20261110_v1/E15.
Read its immutable manifest, metrics and extraction_manifest; read only scored PRM JSONs named and hashed there.
E15 stores PRM probabilities itself, while its 7B w/q are the immutable scores.json input explicitly referenced
and hashed by E15/manifest.json at experiments/NNG_B2_20260925/scores.json.
This referenced file is part of E15's original inputs, not a new benchmark or recomputation.
Reproduce the exact E15 join: old reader role=evaluation intersect scored PRM trace IDs;
verify group, zero-based first-error f, L, dataset and generator-family flag.
The localization denominator consists of all erroneous solutions, including L=1 if present.
Do not impose the L>=2 filter used only by the trained localizer.
E16 uses its own saved scores.json, role=evaluation and f!=None, with no extra filtering.
Join E15 PRM to E16 by trace ID and verify labels/length/groups. If some E16 PRM is unavailable, report coverage
rather than fabricate scores or silently restrict the other methods.
Saved native ProcessBench paragraphs define steps; labels are the first erroneous paragraph, not final-answer labels.
This is retrospective localization of a reader's traces and knows final L and that the solution is erroneous.

## Archive-reproduction gate
Before new baseline outcomes, reproduce E15 jump/surprisal/PRM point estimates for all seven slices, both archived
weightings and original 20000-replicate task-bootstrap CIs, using original common_v2.ratios_boot.
Primary weighting = equal original task, equal erroneous solutions within a task in the reported slice.
Pooled primary values must round to 20.29%,19.94%,52.15% respectively and agree with stored metrics to 1e-12.
Also reproduce E16 jump/surprisal, uniform and first-step metrics and archived CIs where available.
E15 seed=2026111015. E16 seeds=config.seed + original cell enumeration:
pooled,Qwen_family,other_generator,gsm8k,math,olympiadbench,omnimath.
If any primary archive reproduction fails, STOP baseline analysis, leave a diagnostic and identify the cause.

## Slices and estimates
Slice order in new tables: pooled,gsm8k,math,olympiadbench,omnimath,Qwen_family,other_generator.
Use archived dataset and same_family fields verbatim.
For task g with m_g erroneous solutions, rate = (1/G) sum_g (1/m_g) sum_i value_i.
Uniform value = 1/L_i, hence E[1/L], never 1/E[L].
First/last predict zero-based 0/L-1.
Jump/surprisal earliest argmax of saved w/q; PRM earliest argmin probability_correct.
No transformations, thresholds, label changes or tie randomization.

## Positional predictor
Exactly the modal-histogram part of
experiments/peak_error_distributions_20261111_v1/dist_core.py::oof_position_baseline.
Train separately in each requested slice, using erroneous solutions only.
Sorted unique original groups, default_rng(20261113).permutation, cyclic assignment i%5.
All attempts of a task stay together. Group weights 1/m_g, fixed within the slice.
Length bins 1–5,6–10,11–20,21–40,41+; np.digitize(L,[5,10,20,40],right=True).
For a heldout solution, use train groups in its length bin. If fewer than20 train groups, back off to all
train lengths. Weighted histogram of absolute one-based first-error positions.
Restrict support to 1..heldout L, add .5 per position, renormalize; choose earliest argmax.
No geometric predictor is added to the requested comparison; archived geometric calculation may run only
as an equivalence check for reuse of the historical code.
The same slice/trace IDs across reader sizes must yield the same OOF positional predictions.
Save per-trace OOF fold/prediction, histogram rules and donor group IDs/counts for audit.
No test outcome enters its own histogram. No hyperparameter selection on the new result.

## Bootstrap
Point estimates use equal-task weighting throughout, including E16; the old E16 Markdown Jump-exact table
used attempt weighting, so its rounded display need not equal the new equal-task table.
Retain original per-stage bootstrap population: E15 includes all evaluation task groups in the slice,
with zero localization denominator for correct-only groups, exactly as rawmetrics/ratios_boot;
E16 localization uses erroneous-evaluation groups only.
Rates use the original 20000-repeat procedure/seeds and percentile95 intervals.
Requested paired contrasts use10000 whole-task multinomial draws, frozen per-attempt predictions,
seed=2026111511+100*reader_index+slice_index. Apply identical sampled group multiplicity to both sides.
Contrasts: jump-uniform,jump-position_oof,jump-surprisal.
Groups with zero denominator do not enter the point or replicate ratio. CI unavailable if fewer than20
contributing erroneous task groups; preserve undefined draws and require >=95% finite replicates.
Positional histogram fits are not refit in bootstrap, matching the referenced report's conditional-OOF protocol.
Intervals are individual, exploratory; no unrequested multiplicity adjustment.
No accuracy uncertainty from sampling a random uniform prediction: uniform is its exact conditional expectation.

## Validation and output
Before estimating new outcomes, test earliest ties, length-bin boundaries, zero-based/one-based alignment,
unequal-attempt group weights, correct-only groups, and lack of train/test task overlap.
Compare reconstructed positional Hit and jump-position point with the archived baseline function for every slice.
Audit shared-reader populations and position predictions without forcing them to match.
Archive reproduction, rates/contrasts, per-trace predictions, splits, bootstrap arrays and manifests are saved.
REPORT_RU.md and RU/EN reviewer insertion are rendered solely from metrics. No manual result numbers.
Deliver locally and on Zhores; nothing is published to a public repository.
