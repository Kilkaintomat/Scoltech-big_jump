# Status

Updated during the additive 2026-09-11 readiness campaign on Zhores.

Current protocol: [readiness and limitations](docs/e1/READINESS_20260911.md).
Current run status and audit: [expansion report](audit/readiness_2026_09_11/REPORT.md).
The previous three-prover collection remains active and protected.

The paper's experimental programme is **not complete**. Working estimators, a simulation and
modular-addition training exist; these are not a replication of all experiments in Sections 5
and B. The previous claim that the remaining work was only to run the GPU pipeline is withdrawn.

Read the [9 September revision report](audit/revision_2026_09_09/REPORT.md) and
[generated validation record](audit/revision_2026_09_09/VALIDATION.md). The real DeepSeek-Prover
pilot pipeline is implemented; launch receipts live under runs/e1_20260908T171727Z/pilot/.
Its descriptive analysis cannot establish the paper's predictions.

The earlier [revision report](audit/revision_2026_09_08/REPORT.md),
[generated measurements](audit/revision_2026_09_08/server-diagnostics/MEASUREMENTS.md) and
[validation record](audit/revision_2026_09_08/VALIDATION.md) remain historical evidence.
The [previous status](audit/revision_2026_09_08/STATUS-before.md) is retained as historical evidence;
its P4 interpretation and claims of completeness are superseded.

| Component | Implemented and checked | Still needed |
|---|---|---|
| Statistical core | Hill, signed moment, GPD, threshold selection, trace/prompt bootstrap, extremal index; numerical and regression tests | Full stability bands and secondary threshold selection in the production analysis; calibrated inference under dependence |
| Figure 1 / Kesten | Simulation, closed-form checks, fresh diagnostic threshold sweep | An immutable publication run with reconciled protocol choices and verified artifact digests |
| Lean labels | Pinned Lean/Mathlib/REPL validated on Zhores; absorbing labels; trusted statement guard; sequences/bullets and timeout recovery; runtime staged on node storage | Inspect exclusions on actual generated proofs; main benchmark compatibility beyond the pilot |
| Model sampling | Three real prover pilots complete; independent attempt seeds, original token IDs and pinned weights; protected main collection active | Complete the 20,016-attempt population; audit every denominator and exclusion |
| Activation extraction | Three prover pilots measured with exact saved IDs, independent hooks and problem-disjoint calibration | Complete main activation datasets; retain every exclusion; test transform stability |
| P1–P3 | Kernel-labelled pilot measurements and full main analysis; pilot scientifically inconclusive | Main results, Monte Carlo calibration, task positional null, whitening refits and independent label review |
| P4 | Durable paired training, final-frequency measurement and predetermined transition comparison implemented and tested | Complete five seed pairs and conditional tail reanalysis; assess replication before enlarging |
| P5 | Controlled deduction population/checker and gated model pipeline; identified rate fit with explicit limitations | Pilot gate, main measurements, dependence-calibrated held-out prediction and tolerance intervention |
| Other draft experiments | No complete implementation found | Synthetic deduction and code tasks; two-hop composition; recurrent-depth experiment; Tracr/ngram controls; supervised hidden-state baseline |
| Reporting/provenance | Manifests, source digests, generated tables/figures; P4 report corrected | Enforce digest verification before publication; unique run directories; submission-side provenance where GPU nodes lack git |

## Three-model Lean campaign (2026-09-09)

The user authorized full-population Lean runs for all three provers. The additional campaign
runner supports pinned DeepSeek/Goedel/Kimina, isolated model/temperature calibration, exact
shard accounting and main-population descriptive task-bootstrap P1-P3 analysis.
See [the explicit protocol amendment](docs/e1/CAMPAIGN.md) and generated submission/population
receipts under runs/lean_all_20260909/. Generation and extraction use 8 task shards per model.
A technical development-pilot gate precedes main collection; manual review and simulation
calibration remain necessary for any supported scientific claim. The original E1 pilot and
its frozen outputs are preserved. This is the Lean miniF2F campaign, not completion of the
synthetic deduction/training/controls programme or of additional benchmarks.

## Interpretation of existing results

The archived P4 models learn modular addition, but a transient in Hill alone is not a transition
in the paper's `xi`. Reanalysis of signed moment estimates and the shuffled-label control does
not establish the claimed mechanistic signal. The archived Fourier losses used an incorrect
projection/evaluation split and must be rerun from weights or training; scalar logs cannot repair
them. Negative finite-sample estimates alone do not prove bounded support or algorithmic computation.

The Kesten diagnostic preserves disagreement between estimators and across thresholds. Its
verified/refuted labels are defined by the deviation threshold, so it cannot independently
validate the latent-to-kernel coupling that the real Lean experiments are meant to test.

Historical P3 clustering observations and the P5 identifiability correction predate this
revision. They motivate protocol checks; they do not fill the missing model experiments.

## Current execution environment

The authoritative working tree is on Zhores. Per user instruction, all further edits and tests run on the server; the last local repeat was stopped and is not counted as a successful run.

Both checkouts started at `a3988f76ca27ff5ecc476a192b9d61797e861b65`. Zhores is reachable with the
existing `zhores` SSH alias; SSH/VPN configuration was not changed. The audit runs used an uncommitted
working tree and their diagnostic manifests correctly report that historical dirty state.

Cluster validation uses Slurm and the existing container. Lean now runs inside that same
container: a verified runtime archive on GPFS is unpacked onto node-local storage for each job.
This avoids observed BeeGFS read errors and slow network mmap reads. Exact current test results
and job evidence are recorded in [VALIDATION.md](audit/revision_2026_09_09/VALIDATION.md).

Before a paper run: settle the protocol, freeze this reviewed source/config/model revision,
validate a small real-prover pilot, then run into a new output directory with complete manifests.


## Recovery audit — 2026-09-11

The September 9 three-prover campaign stopped before main acquisition: DeepSeek/Goedel had
whole-proof/replay disagreements caused by multiline combinator segmentation; Kimina's final
Lean blocks were lost by Markdown fence parsing. The old snapshots and outputs are preserved.

The corrections and their scope are documented in `docs/e1/REVISION_20260911.md`.
Recovery uses original generated token IDs and unchanged protocol files in
`runs/lean_recovery_20260911_v2/`; new labels, activations and reports have separate GPFS directories.
The controller is in tmux `onebigjump-recovery`. Main acquisition requires passed full tests and
the complete real-model pilot gate. Scientific interpretation remains inconclusive.

Current generated audit reports: `audit/revision_2026_09_11/latest-report.txt` (report directory);
job state: `runs/lean_recovery_20260911_v2/queue.json`. These recorded metrics are authoritative for
completion counts; this status note is not a claim that main measurements have finished.


### 2026-09-11 final recovery lineage

Final source and campaign pointers are `audit/revision_2026_09_11/snapshot-path.txt` and
`runs/lean_recovery_20260911_v3/queue.json`. The live dispatcher is in tmux
`onebigjump-recovery`. The v3 campaign reuses all v2 pilot tokens, corrected Lean labels,
activation states and measurements, and recomputes pilot analysis after rejecting failed GPD
endpoint fits. Main acquisition waits for the final full-suite validation and technical gates.
The earlier recovery roots remain preserved diagnostics. The dated report pointer is
`audit/revision_2026_09_11/latest-report.txt`; it contains generated counts and statistics.
Pilot P1-P3 remain inconclusive; no supported article claims or paper_outputs were updated.

## Additive expansion, 2026-09-11

The protected three-prover collection is `runs/lean_recovery_20260911_v3`.
The separate `scripts/readiness/` controller and `src/onebigjump/readiness/` stages implement:
800 task-cluster Monte Carlo calibration datasets; positional and whitening sensitivities;
five paired modular-addition/random-label training seeds with durable optimizer checkpoints
and final-frequency remeasurement; and a controlled modus-ponens pilot with gated main collection.
See `docs/e1/READINESS_20260911.md` for fixed protocols and inferential limitations.
Live submission/completion state belongs to `runs/expansion_20260911/queue.json`; the presence of
code or a WAITING graph node does not mean that a result has been obtained.

The generic `SyntheticConfig` CLI remains unimplemented; the new controlled task has a dedicated
runner and does not claim to reproduce every synthetic/code setting in the draft. P5 length-fit
p-values are descriptive until task dependence and held-out prediction are addressed. Two-hop,
recurrent-depth, Tracr/ngram and supervised-probe experiments remain unvalidated and unlaunched.
