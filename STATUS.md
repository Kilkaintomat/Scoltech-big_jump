# Status

Updated after the 2026-09-08 revision against the supplied paper draft and the Zhores archive.

The paper's experimental programme is **not complete**. Working estimators, a simulation and
modular-addition training exist; these are not a replication of all experiments in Sections 5
and B. The previous claim that the remaining work was only to run the GPU pipeline is withdrawn.

Read the [revision report](audit/revision_2026_09_08/REPORT.md),
[generated measurements](audit/revision_2026_09_08/server-diagnostics/MEASUREMENTS.md) and
[validation record](audit/revision_2026_09_08/VALIDATION.md).
The [previous status](audit/revision_2026_09_08/STATUS-before.md) is retained as historical evidence;
its P4 interpretation and claims of completeness are superseded.

| Component | Implemented and checked | Still needed |
|---|---|---|
| Statistical core | Hill, signed moment, GPD, threshold selection, trace/prompt bootstrap, extremal index; numerical and regression tests | Full stability bands and secondary threshold selection in the production analysis; calibrated inference under dependence |
| Figure 1 / Kesten | Simulation, closed-form checks, fresh diagnostic threshold sweep | An immutable publication run with reconciled protocol choices and verified artifact digests |
| Lean labels | Native local Lean/Mathlib/REPL integration; absorbing labels; sampled-goal guard | Install and validate Mathlib/REPL on Zhores; broader syntax and timeout/recovery coverage |
| Model sampling | Hugging Face and vLLM adapters; seed/revision forwarding; saved expected statement and generation IDs | Regenerate legacy samples lacking original IDs/context; validate actual prover template and pinned weights |
| Activation extraction | Exact saved IDs/context where alignment is verifiable; whitening; problem-disjoint calibration; shard reading | A real prover end-to-end pilot and complete activation dataset; coverage checks for non-roundtripping tokenizers |
| P1–P3 | Analysis modules and surrogate/integration tests; fixes for ties, missing evidence and resampling metadata | Measurements on kernel-labelled model trajectories, stratified by model, temperature and task family |
| P4 | Archived modular-addition and shuffled-label training; corrected Fourier projection and excluded training loss | Rerun corrected mechanistic measurements, freeze frequencies from final weights, test a prespecified transition criterion |
| P5 | Identified exponential rate fit and independent extremal-index input | Controlled deduction lengths, uncertainty calibration and a guard for incompatible recovered tolerance |
| Other draft experiments | No complete implementation found | Synthetic deduction and code tasks; two-hop composition; recurrent-depth experiment; Tracr/ngram controls; supervised hidden-state baseline |
| Reporting/provenance | Manifests, source digests, generated tables/figures; P4 report corrected | Enforce digest verification before publication; unique run directories; submission-side provenance where GPU nodes lack git |

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

Cluster validation uses Slurm and the existing container environment. Local live Lean tests do
not establish that the remote Lean installation is ready. Exact test results and job evidence
are recorded in [VALIDATION.md](audit/revision_2026_09_08/VALIDATION.md).

Before a paper run: settle the protocol, freeze this reviewed source/config/model revision,
validate a small real-prover pilot, then run into a new output directory with complete manifests.
