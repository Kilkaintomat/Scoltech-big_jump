# E1: first real Lean P1–P3 campaign

Protocol v0, fixed before pilot generation. Run `e1_20260908T171727Z`, branch
`experiment/e1-20260908`, base commit `5302b9f8435c0e653c4a0c5eeacd50fb25e3df07`.
The final protocol and executable source snapshot will be frozen after technical pilot checks
and before any main evaluation generation/analysis. Pilot observations are development data.
All execution is on Zhores compute nodes through Slurm. Historical results are inputs to the
previous audit only; no historical completion is used for activation measurements.

## Population, versions, and splits

Model/tokenizer: `deepseek-ai/DeepSeek-Prover-V2-7B`, revision
`a8d9e14432b2e8dd9df2a4d4e70f1ba9bc8d9b7b` for both. Original cached files have individual
SHA256 digests. 30 decoder blocks, width 4096. Generation uses vLLM 0.8.5.post1, extraction
uses Transformers 4.51.3 / PyTorch 2.6.0, bfloat16 weights and float32 captured states.
Container and dependency versions are captured on the executing node.

Benchmark source: `cat-searcher/minif2f-lean4`, commit
`70a1249ce240667f6bcdd1ccd62f847f0e065d57`. Original test/validation each contain 244 rows.
The original files, all IDs and row digests are retained. 18 test and 13 validation rows contain
only commented-out unported statements; they remain in the source inventory and are excluded
before generation as `source_has_no_live_declaration`. This reproduces the historical 226/231
counts transparently; it is a subset of this Lean port, not all of canonical miniF2F.

Split seed 20260908. Sort ALL validation IDs by SHA256 of `seed:development:problem_id`;
first 40 are development, the remaining 204 calibration. Test is evaluation. Technical source
exclusions do not reassign a problem between splits. Choose 20 eligible development IDs in the
same deterministic order for the pilot; first 10 are pilot calibration, remaining 10 pilot
evaluation. The entire development set is excluded from main calibration/evaluation.
Canonical IDs are the source IDs. Exact lexical duplicate statements (ignoring declaration
name and comments) and duplicate IDs are checked; any cross-split lexical duplicate is excluded
from both sides before generation and reported. This is not a semantic-equivalence detector.
Trusted statement elaboration is checked before generation; incompatibilities are counted by ID,
not silently removed. Family is the source ID prefix (mathd_algebra and mathd_numbertheory are
kept separate); aggregate estimates describe this explicit mixture, not a universal tail.

The test split has already been used during earlier development. E1 is a frozen analysis of a
reused benchmark, not an untouched confirmatory test set; model-training contamination is unknown.

## Generation and verification

Pilot: 20 development problems × 2 attempts × temperatures {0.6, 1.0} = 80 planned attempts.
Main: 8 attempts per eligible calibration/evaluation problem per temperature. Exact eligible
counts, expected tokens/runtime/storage and jobs are written after pilot and before submission.
No outcome-dependent stopping or additional attempts. Each attempt has a deterministic seed
from its split, canonical ID, temperature and index; attempts are generated without Lean feedback.

Use the model author's chat template and request a proof plan followed by a complete fenced Lean
proof. The fixed user content includes `import Mathlib`, `import Aesop`, the original necessary
`open` directives and the original statement with a `sorry` placeholder. Only the documented
big-operator binder compatibility rewrite `in` → `∈` is applied before freezing the statement.
Both original and normalized statements are retained. Sampling: top_p=1, top_k=-1, max_new_tokens
8192, stop at EOS (retained), no verifier stopping, no text truncation. A length-limited attempt
is a generation-truncation category even if a formal fragment happens to compile.

Lean 4.34.0-rc2 (commit `6a10ac8c22beadecabdbb0919c2b50214762f91d`), Mathlib
`85e3a25e006c35636f0e53b0e9296caca2685bc0`, REPL
`5d5c49d13dfc0c1d2df43a27c3e56e02ad81b9c3`. One trusted base environment, no imported benchmark
solutions. Per-step wall timeout 60s, whole-proof 180s, startup 900s, maxHeartbeats 400000.
Timeouts/resource failures are distinct technical outcomes; restart/drain is tested for isolation.
Generated headers must lexically match the original; generated preambles may only repeat trusted
lines. Only the proof body is compiled under trusted directives/original statement. Audit kernel
axiom dependencies: reject sorryAx or newly introduced axioms. Whole-proof and replay responses
are preserved independently. Unexplained disagreements block the main run.

One outer tactic line plus its indented continuation/bullets is a step; semicolon/combinator and
structured `have`/`calc` blocks stay intact. Comments and strings are handled lexically. Unsupported
segmentation is explicit. Categories: verified; localized tactic failure; terminal unsolved goals;
sorry/invalid proof; parse error; context/statement mismatch; timeout/resource; generation
truncation; unsupported segmentation; infrastructure failure; alignment/extraction failure.
Primary refuted traces include ONLY localized tactic failures. Article B.2 sensitivity additionally
includes terminal unsolved goals and localized timeouts/holes when a full step sequence exists.
After t*, every label is zero and every subsequent step is `unreached`. Activations may still be
read at these originally generated positions; they are not additional executed kernel failures.

## Measurements

Read residual states AFTER blocks 7, 15, 22 (1-based); actual module indices 6, 14, 21. The primary
cell is temperature 0.6, after block 15, whitened increment. Other temperatures/layers/statistics
are secondary. Never pool temperatures. X0 is the last prompt token; Xt is the last original token
covering the final non-comment byte of step t. Byte-BPE pieces reconstruct the saved completion
exactly without re-encoding it. Unicode byte splits and noncanonical BPE segmentation are allowed;
unverifiable/overlapping step tokens are explicit alignment exclusions. Boundary crossings are
saved. The first increment includes the intervening informal reasoning; retain it in primary
analysis, exclude Z1 in a prespecified sensitivity. Surprisal averages realized formal-step token
negative log probabilities with the causal one-token shift, using the same full context.

Raw norms need no fit. Whitening uses verified traces of the predetermined calibration problems
ONLY, separately per temperature/layer: centered sample covariance, fixed 0.1 shrinkage towards
isotropic trace(S)/d, numerical eigenvalue floor 1e-8 × mean eigenvalue. Innovation uses ridge=1,
fitted only there; it remains diagnostic. Main minimum: 20 verified calibration tasks and 200
increments; report n/d and eigenvalue/shrinkage diagnostics. This explicitly permits an
underdetermined regularized covariance, unlike the old generic 2d guard. Results are conditional
on that regularized transform; sensitivity shrinkages 0.05 and 0.2, and task-refitted whitening
sensitivity at the primary cell, must reveal instability. Pilot may fit with 2 verified tasks
and 8 increments solely to exercise plumbing; pilot inferential claims remain inconclusive.

Independent real-prover forward checks use original IDs and fixed positions, compare selected
hooks to an independent forward with output_hidden_states, tolerance atol=1e-5, rtol=1e-5 for the
same bfloat16 computation. If a different numerical path is needed, report its separate error
and declare the tolerance change before main. Compare vLLM/HF next-token log probabilities on
fixed development examples; no claim of bitwise equality across backends.

## Statistics and decision rules

The resampling unit is ALWAYS the independent task, retaining all attempts and steps together.
There is no fallback to attempt bootstrap under 20 tasks. Every bootstrap estimate reselects k
with the primary double-bootstrap rule (n1=n^0.9, 200 inner resamples); secondary KS and k-sensitivity
are recorded. Main task bootstrap: 500 repetitions, fixed seed; report failed fits/valid fraction.
Intervals remain conditional on fitted activation transformations unless the transformation is
explicitly refitted. Pointwise estimator-vs-k bands are not simultaneous bands.

Report signed Hill, moment and GPD gamma and xi=max(gamma,0) separately. Hill cannot support
nonpositive gamma. Finite-sample negative moment is not proof of bounded support/algorithmicity;
three-estimator agreement is not a universal light-tail test. Insufficient samples and failed
fits are retained. Shape interpretation requires at least 200 positive steps, selected k≥20,
20 contributing tasks overall AND in the tail, ≥90% finite bootstrap replicates; stability is
reported over k/2 to 2k and the full feasible k grid. Unstable signs/ranges produce inconclusive
shape interpretation, regardless of a visually appealing curve.

P1: verified, all primary refuted, pre-failure, at-failure, post-failure, at+post pools. Primary
estimand is signed moment(refuted) − signed moment(verified), with direct task-bootstrap CI.
Companion Hill/GPD and pre-failure interpretation stay separate. Report trace/task/step/tail-task
counts, empty subsets, length/position strata and exclusion-of-first-step sensitivity.

P2: earliest argmax; top1/top3, rank, displacement; same-sample jump−surprisal paired top1 CI.
Report full generated sequences primarily, prefix-through-failure separately, L>1 and L>3
separately. No interpretation as prediction before executing the tactic. Within-trace permutation
is the article's descriptive exchangeability-dependent control. A second control permutes whole
score trajectories against independently observed t* across TASKS within family and exact length
strata; sparse strata are omitted with counts, never pooled ad hoc. 999 permutations.

P3: tau from verified calibration steps at q=0.01; sensitivities q={0.02,0.005}, q=0.001 only if
at least 100 calibration exceedances from 20 tasks. Independently resample calibration/evaluation
tasks and re-estimate tau. Report failure coverage, false exceedances in verified evaluation and
accepted prefixes, first-exceedance localization, all-failure ratios and conditioned ratios.
Fit GPD only to positive excesses. Compare signed overshoot gamma − P1(at+post) gamma by jointly
resampling evaluation tasks; non-significance does not establish equality. Primary P3 tail claims
require ≥20 calibration exceedances from ≥10 calibration tasks, ≥50 positive evaluation excesses
from ≥20 tasks, and ≥90% valid replicates; otherwise inconclusive. Threshold instability is explicit.

Primary P1/P2/P3 decisions form one family: conservative Bonferroni two-sided 98.3333% confidence
intervals for directional P1/P2 effects; ordinary 95% descriptive intervals are also reported.
Supported P1 requires primary direct effect lower bound >0, sufficient/stable measurement and
simulation checks; upper bound≤0 is not_supported, otherwise inconclusive. P2 uses the same rule
for paired top1 gain and also requires p<0.05/3 for the task-trajectory positional null. P3 is a
compatibility test, not an equality proof: report not_supported when a valid difference interval
excludes zero; otherwise inconclusive unless a separately preregistered equivalence margin exists
(no such margin is asserted here). Secondary cells/ablations are exploratory, without selecting a
favorable layer/temperature. Every claim maps to a statistic, measured outcome and allowed wording.

Simulation validation must exercise task clustering, adaptive k/tau and actual contrast procedures
on known heavy/light tails and failure positions independent of deviations; report coverage/FPR
and binomial Monte Carlo intervals. A failed calibration prevents a supported scientific claim;
it does not trigger tuning against evaluation observations. LR/Vuong outputs are descriptive unless
their dependence assumptions are separately calibrated.

## Gates, provenance and reporting

Pilot must account for all 80 attempts through generation→Lean→alignment→states→table→P1–P3.
Manually review at least 12 actual traces across observed categories plus every disagreement;
fixtures cover absent technical categories and are clearly identified. Main gate requires genuine
Lean smoke tests, no accepted false theorem/hole, no unexplained disagreement, exact step accounting,
real-model activation validation, complete category flow, digest-valid manifests and correct
inconclusive behavior. High unsupported/truncation rates require a documented technical decision;
low success alone is not a software bug.

Freeze source snapshots before execution; bind every journal to input/config/source digests,
per-attempt IDs and row digests. Resume rejects changed inputs, duplicate shards/IDs and corruption;
a torn final JSONL fragment is preserved in quarantine before truncating to the last complete row.
Completed stage outputs/manifests are immutable. Rendering verifies the full input/output manifest
graph, including model/container/source digests, and fails on mismatches. Reports are generated
from measured files; no numerical paper artifact is typed manually. Commit code/configs/splits,
compact metrics/manifests/reports; large completions, activations, model files remain on server.
