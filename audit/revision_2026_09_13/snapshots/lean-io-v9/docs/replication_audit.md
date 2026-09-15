> **SUPERSEDED — see `audit/REVIEW.md`.**
>
> An independent re-audit refuted several claims below. They are left in place because a report
> that quietly rewrites itself is worse than one that is wrong in public, but do not read them as
> current:
>
> * **P4's "declining ξ̂" was Hill, not ξ.** `analyse_p4` computed every field named `gamma_*`
>   from the Hill estimator, which is non-negative by construction. The paper's order parameter
>   `ξ = max(γ, 0)` is zero at 92.5–99.8 % of checkpoints on every run; `ρ(step, ξ) ≈ −0.07`, not
>   −0.83. Both P4 claims — the transient peak and the monotone decline — are withdrawn.
> * **A shuffled-label null reproduces the decline** (mean `ρ = −0.754` against −0.827 for real
>   grokking), so it is not evidence of circuit formation.
> * **"At p = 0 the estimators correctly go negative, i.e. bounded tail" is wrong.** `Z_t` is
>   chi-distributed there: unbounded support, Gumbel domain, true `γ = 0`. The negative estimates
>   are finite-sample bias.
> * **"The p = 0.02 undershoot is caused by short traces" is wrong.** Trace lengths of 16, 64,
>   256 and 1024 at equal total steps give the same answer. The cause is the `k` selector landing
>   on a pathological point (1.99 % → 0.153 against a true 0.2517).
> * **"All numbers here are reproducible from 28b5f7c" is false.** 13 of 29 recorded digests no
>   longer match, and every GPU run carried `commit: null` because the GPU nodes run git 1.8.3.1,
>   which has no `-C` option.

# One Big Jump: what the pipeline has actually established

An account of the experimental code written for the ICLR 2027 submission, the results it has
produced, and the failures found by checking its output rather than its tests. Written to be
reviewable without reading the code.

Published as a page: https://claude.ai/code/artifact/6f57da34-8270-4f0e-9109-f953051d1c2a

State as of 8 September 2026, repository at 28b5f7c.

## 1. The paper's claim

The distribution of step-to-step deviations in a transformer's residual stream, measured along a
reasoning trajectory, is an order parameter for whether the model is running an algorithm or
improvising. Fit a tail index to the deviation magnitudes and report `xi = 1/alpha`:

- `H_alg` -- algorithmic computation gives `xi = 0`, a light tail, no step dominating;
- `H_heur` -- heuristic search gives `xi > 0`, a heavy tail, one big jump carrying the trajectory.

The mechanism is a Kesten recurrence `E_t = a_t E_{t-1} + B_t`, whose tail index solves
`(1-p) rho^alpha + p kappa^alpha = 1`. Five predictions P1-P5 are meant to be tested on real
models.

This document concerns the experimental section only.

## 2. What was built

~9,800 lines across 40 modules, 478 tests, from an essentially empty repository.

| Package | What it does |
|---|---|
| `stats/` | Hill, Dekkers-Einmahl-de Haan moment estimator, GPD MLE via Grimshaw's profile reparameterisation, Danielsson double-bootstrap choice of `k`, extremal index by three methods, trace-level bootstrap |
| `simulation/` | The Kesten recurrence and the paper's Figure 1, regenerated rather than traced |
| `lean/` | Drives a Lean 4 + Mathlib REPL for exact per-step labels: which tactic first fails. Segmentation, absorbing labels, sharding, resume |
| `models/` | Forward hooks on decoder blocks, token alignment by character offset, three deviation statistics with Ledoit-Wolf shrinkage, sampling backends, the grokking transformer |
| `experiments/` | P1-P5 as separate testable analyses, plus the driver |
| `reporting/` | Figures and Tables 1, 2 and B.3, generated from the metrics files so they cannot drift |

Every run writes a manifest: resolved config, git commit, dirty flag, package versions, hardware,
and a digest per output file.

## 3. What holds up

**Figure 1 reproduces.** Closed-form alpha = 3.9734 / 2.7992 / 1.8193 against the paper's
3.97 / 2.80 / 1.82. The estimators recover the truth on simulated data:

| p | xi theory | xi reported | Hill | Moment | GPD | theta | top-1 |
|---|---|---|---|---|---|---|---|
| 0.00 | 0.0000 | 0.0000 | 0.0788 | -0.1033 | -0.1064 | 1.000 | 0.984 |
| 0.02 | 0.2517 | 0.1522 | 0.2610 | 0.1522 | 0.1390 | 0.268 | 0.903 |
| 0.05 | 0.3572 | 0.3109 | 0.3472 | 0.3109 | 0.2927 | 0.596 | 0.846 |
| 0.10 | 0.5497 | 0.5375 | 0.5221 | 0.5375 | 0.5445 | 0.496 | 0.680 |
| 0.15 | 0.8483 | 0.8415 | 0.8500 | 0.8415 | 0.8471 | 0.210 | 0.646 |
| 0.20 | 1.4825 | 1.5309 | 1.5356 | 1.5309 | 1.5354 | 0.187 | 0.200 |

Two things to notice. At p = 0 the moment and GPD estimators correctly go negative (bounded tail)
while Hill returns 0.0788, because Hill cannot express a light tail -- which is why `xi` is taken
from the moment estimator. And at p = 0.02 the estimate undershoots badly: with a shock every
fifty steps, 64-step traces contain too few shocks to identify the tail. A real limitation to
state in the paper.

**The Lean verifier gives real labels.** Lean 4 v4.34.0-rc2, Mathlib pinned at 85e3a25e. A
10-trace pilot: 4 verified, 5 refuted, 1 parse error discarded. The kernel, not a heuristic,
decides which step is wrong.

**The benchmarks are installed and elaborate.** 1,086 problems, ~1 MB, committed so a run is
reproducible from the repository alone: miniF2F test/validation 226/231, ProofNet test/valid
179/178, PutnamBench test 272.

Sending each statement to the kernel with a `sorry` body took elaboration from 87% to 98%. Five
faults: three different statement terminators across the benchmarks; `sum x in S` deprecated and
now rejected (70 of 702 statements); `import` lines cannot be re-issued in a REPL command but the
`open` lines beside them must be kept; 38 miniF2F rows are entirely commented out; PutnamBench
writes `n !` and `u^T` without opening the scoped namespaces. The `open`-directive fix was
measured rather than assumed: it rescues 1 statement in 40 on PutnamBench and 0 in 30 on miniF2F.
Correct, and nearly worthless.

## 4. A withdrawn finding

**The transient spike in xi at the grokking transition does not survive.**

On Apple MPS, xi spiked sharply just before test accuracy jumped, coinciding with the turn in the
excluded-loss progress measure. I committed that under "the order parameter turns with the
circuit, not with the accuracy." On an A100 the spike is gone; on CPU float32 -- the reference
arithmetic -- it is also gone, and CPU agrees with CUDA.

| Backend | Seed | Grok step | Peak xi | Peak step | Lead | rho(step, xi) |
|---|---|---|---|---|---|---|
| MPS | 0 | 22800 | **0.1753** | 22700 | -100 | -0.428 |
| MPS | 1 | 23100 | **0.1801** | 22700 | -400 | -0.490 |
| MPS | 2 | 13000 | 0.0691 | 12100 | -900 | -0.714 |
| CUDA | 0 | 21100 | 0.0761 | 5800 | -15300 | -0.848 |
| CUDA | 1 | 20500 | 0.0673 | 100 | -20400 | -0.805 |
| CUDA | 2 | 14500 | 0.0733 | 4100 | -10400 | -0.829 |
| CPU fp32 | 0 | 18000 | 0.0679 | 100 | -17900 | -0.771 |

Every non-MPS run peaks between 0.067 and 0.076. MPS seeds 0 and 1 peak at 0.175 and 0.180, and
only those two land at the transition. MPS seed 2 behaves like the others -- which is why three
seeds on one backend did not catch it: two of three agreeing looked like replication.

**What survives:** the Spearman correlation between step and xi is strongly negative on every
backend and *more* so on the trustworthy ones (-0.85 / -0.81 / -0.83 CUDA, -0.77 CPU, against
-0.43 / -0.49 on the MPS runs carrying the spike). The order parameter declines monotonically as
the network moves from memorisation to a generalising circuit.

That is weaker in a specific way. The decline is **not localised at the transition**: across the
grokking step the median xi moves only 0.043 -> 0.038 (CUDA) and 0.046 -> 0.032 (CPU), not
separable from the global drift. So P4 supports "xi tracks algorithmic structure" but not "xi has
a signature at the phase transition." The second is the more interesting claim and there is
currently no evidence for it.

The decisive control was one CPU job (Slurm 8461874, 28 min), worth running precisely because it
could only embarrass me.

## 5. A tokenizer that silently destroyed its own output

The first full sampling run against DeepSeek-Prover-V2-7B completed, wrote 3,616 completions, and
reported no error. All of them were garbage. Under `transformers` 5.16.1 that model's byte-level
BPE tokenizer loads without a byte decoder:

    probe   : theorem foo (x : R) : 1 = 1 := by\n  norm_num
    5.16.1  -> theoremfoo(x:):1=1:=bynorm_num
    4.51.3  -> theorem foo (x : R) : 1 = 1 := by\n  norm_num

Missing from the broken line: every space, the newline, the indentation, and the real-numbers
symbol. Lean is written in Unicode, so this deletes mathematical content, not just formatting.

**Why nothing caught it.** The output was still a string, still contained `theorem`, still 3,616
records of about the right length. A crude "looks like Lean" filter passed 3,614 of 3,616. Only
the Lean kernel would have objected -- to *all* of them, which reads as a bad model or prompt
template, not a broken decoder.

Fixed in two parts: the version is pinned (`transformers>=4.40,<5`) with the reason written beside
the pin, and `assert_tokenizer_roundtrips` now checks a probe carrying indentation, a newline and
a non-ASCII character once per backend before the weights load -- because a pin only protects
environments we control. Side effect: 4.51.3 is what vLLM 0.8.5.post1 wants, so the fast backend
works again.

## 6. Manifests that claimed a clean checkout they never had

The manifest records `dirty: false` to mean "this figure came from a clean checkout." On the
cluster it recorded `dirty: false` for every run -- and the cluster tree was a copied directory
with no `.git`. `git status` returned nothing and `bool(None)` is `False`.

A run whose source version was entirely unknown was recorded as the strongest possible claim about
its own provenance -- a silent failure in the one direction this field must never fail, inside the
machinery whose purpose is making failures loud. An integration test caught it
(`assert man["environment"]["git"]["commit"]`) and I had left it red, reading it as a cluster
quirk rather than as a result about the results.

Three changes: `dirty` is `None`, never `False`, when git cannot be asked, and `reproducible`
requires an actual `False`; the cluster tree is a real clone, pushed over SSH to a bare repo there
since the GitHub repo is private and the cluster has no credentials; and because the Singularity
container has no `git` binary, the launcher reads the commit on the host and passes it in, labelled
`source: environment` -- an exported variable is weaker evidence than asking git.

Consequence: the P4 CUDA and CPU results in §4 predate the fix and carry a null commit. Config and
environment are recorded and the code path is unchanged, but commit-level provenance for those
numbers needs a re-run. They are cheap, 26 minutes each.

## 7. Running now

Sampling on the corrected stack: 226 miniF2F-test problems x 8 samples x 2 temperatures = 3,616
traces, with a tokenizer that round-trips and a manifest that carries a commit. Then:

1. **Verify** the sampled proofs through the Lean kernel for per-step labels. Blocked on the
   Mathlib cache finishing its build on the cluster.
2. **Extract** residual-stream trajectories for verified and refuted traces, aligned to the tactic
   boundaries the verifier labelled.
3. **Analyse** -- at which point P1, P2, P3 and P5 give numbers on real data for the first time.

The honest headline: the statistical machinery is validated, the labelling pipeline works, the
infrastructure runs -- and the paper's central experimental claims have not yet been tested on a
real model. P4 is the only prediction touched by real training, and §4 is what it gave.

## 8. Specified but not yet built

- **Hill plots on real data**, across all layers and all three deviation statistics. The
  identifiability criterion is read off these; without them the choice of `k` is unauditable.
- **Ablations** over layer, statistic, temperature and `k`. One configuration is currently
  reported with no evidence it was not chosen after the fact.
- **Split-half reliability** of xi. Cheap, and it bounds how much of any effect is noise.
- **Label-noise degradation** of the P2 localisation result -- the check that it is not an
  artefact of perfect labels.
- **Spectral measure** of the largest jumps (B.9): is the big jump a coherent direction or a
  magnitude spike?
- **Llama-3.1-8B (§5.2)**, gated on Hugging Face; needs licence acceptance and a token.

Added recently and not yet exercised on real data: ROC stored as a curve rather than a single AUC,
survival-curve figures for the three P3 overshoot variants, the P5 length-law figure with binomial
error bars and a residual panel, and Table B.3 assembled from the generation manifest and
verification summary so it cannot drift from the run.

## 9. Where I want scrutiny

1. **Is the P4 withdrawal complete enough?** I keep "xi declines monotonically" and drop "xi
   spikes at the transition." But the surviving claim rests on a Spearman correlation over a
   training run, where step and almost any smoothly-varying quantity will correlate. Real result,
   or a restatement of "the model gets more structured"? It probably needs a null: the same
   correlation on a run that never groks.
2. **Two of three MPS seeds agreed on a false result.** Seed replication could not distinguish a
   finding from a backend artefact. Should every headline number be produced on two backends, or
   is that overcorrecting from one bad experience?
3. **The tokenizer bug was found by reading output, not by any test.** The guard catches that
   specific failure. What is the general version -- which other stages currently produce output
   that would look plausible if it were completely wrong?
4. **P1's identification at low jump rates.** The simulation undershoots at p = 0.02 because
   64-step traces hold too few shocks. Real proof traces are short (the pilot averaged 1.7 steps).
   If trace length is the binding constraint, real-data P1 may be unidentifiable for the same
   reason -- better to know before running it than after.
5. **Are the negative results prominent enough?** The withdrawn P4 spike, the near-worthless
   directives fix, the p = 0.02 undershoot and the discarded sampling run are in commit messages
   and here. They are not yet in the paper draft.
