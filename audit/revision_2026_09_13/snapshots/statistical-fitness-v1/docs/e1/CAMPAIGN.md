# Three-prover full-scale Lean collection, 2026-09-09

Authorized by the user after the audit. The scope is the three Lean provers in Section 5.1:
DeepSeek-Prover-V2-7B, Goedel-Prover-V2-8B and AI-MO/Kimina-Prover-Distill-8B.
Synthetic deduction and training experiments are separate, currently incomplete programmes.

The E1 model-independent definitions, task splits, native Lean pin, exclusion rules and
verification semantics apply. miniF2F is the first full-population benchmark; ProofNet and
PutnamBench are not silently included without compatibility preparation. Model and tokenizer
revisions are resolved before generation, stored in models/*/pin.json and file-digested.
The exact populations and count of every shard are generated in population.json.

Main collection: all eligible calibration and evaluation problems outside development,
8 attempts at each of T={0.6,1.0}, 8192 new tokens, top_p=1, top_k=-1. The fixed three source
elaboration failures in the completed Lean smoke are excluded with their original evidence.
No model outcome affects inclusion or sampling budget. Tasks are sharded by SHA256 ID into
8 disjoint parts; sharding does not change an attempt's random seed.
Each model uses its author's chat template. DeepSeek/Goedel use the documented proof-plan
request. Kimina uses its author's math/Lean system message and formal-statement request,
with the dataset's informal statement when present. The common sampling settings deliberately
control the comparison; these are not reproductions of each model card's pass@32 result.

Layers are AFTER blocks floor(Lambda/4), floor(Lambda/2), floor(3Lambda/4), with zero-based
module indices one lower. Each temperature/model/layer has its own transform, fitted on
verified calibration tasks only. The main minimum remains 20 verified calibration tasks and
200 increments. Unavailable whitening is explicit; it is not fitted on evaluation data.
Main generation, verification and extraction are sharded, then complete ID sets are checked
before transforms and statistics. State capture remains float32, model weights bfloat16.

## Explicit amendment to the E1 release gate

Separate full data acquisition from scientific inference/publication. Acquisition may start
automatically after the real model's complete development pilot passes: exact attempt accounting,
live Lean false-proof/timeout/statement tests, zero unexplained whole/replay disagreements,
original-token alignment, and independent residual-forward validation.
Every alignable labelled pilot trace must be extracted, or the gate fails.
A stratified packet of at least 12 actual pilot traces is saved for manual review.
Manual review and simulation-based coverage/FPR calibration remain mandatory before any
supported scientific claim/publication, but do not block verifier-independent main sampling.
The gate never tests P1/P2/P3 directions or requires successful whitening.
All generated exclusion/truncation category counts are retained; the fixed token cap is not
tuned after seeing success rates.

## Full-population analysis and its limits

P1-P3 are measured separately in all temperature/layer/statistic cells. Report all three
signed estimators, xi=max(gamma,0), k-selection/KS diagnostics, task and tail-task counts.
Main uncertainty resamples complete tasks, retaining every attempt. The primary k selector
is rerun for each of 500 task resamples with 200 inner bootstrap resamples. P1's direct
signed-moment difference is computed jointly, and P2's jump-minus-surprisal effect is paired.
P3 independently resamples verified calibration tasks and evaluation tasks, refits tau,
and compares positive-excess GPD with the same resample's pooled at/post GPD. q=0.001 is
reported but uninterpretable without its larger exceedance requirements.
Ordinary 95% and Bonferroni intervals over the 9 primary model-by-prediction cells are saved.
Full feasible Hill curves get pointwise task-bootstrap bands at fixed tail fractions.
No interval is supplied below 20 independent tasks or below 90% finite resamples.

These intervals are descriptive variance approximations, conditional on fixed whitening.
The complete confirmatory E1 analysis still needs simulation calibration, task-refitted
transform sensitivities, and the task-stratified positional null. Their absence is recorded
and prohibits a supported claim. The per-family and first-increment estimates are exploratory.
Low samples, failed fits, incompatible signs, and negative results are retained.
No inference result is written into paper_outputs by this campaign.
