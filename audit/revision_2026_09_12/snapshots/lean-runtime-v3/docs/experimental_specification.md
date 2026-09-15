# Experimental specification

Derived from `onebigjumpdraft.pdf` ("ONE BIG JUMP: Heavy Tails in Residual-Stream Reasoning
Trajectories as an Order Parameter for Algorithmic Computation", ICLR 2027 submission, 23 pp.).
This document is the contract between the paper and this repository: every number the paper marks
as `[x.xx]`, `[Fill]`, `[Results]` must be produced by a run recorded here.

Section numbers below refer to the PDF.

---

## 1. Objects and definitions

### 1.1 Trajectory (Sec. 2)

A decoder-only transformer with residual-stream dimension `d` and `Λ` blocks processes a prompt `π`
and emits a trace of `L` steps `s_1, ..., s_L`, each a span of tokens:

- Lean 4: one tactic;
- chain of thought: one sentence;
- recurrent-depth block: one recurrence.

For a fixed read-out layer `ℓ`:

- `X_t ∈ R^d` — residual stream after block `ℓ` at the **last token of step `s_t`**;
- `X_0` — the same quantity at the **last prompt token**;
- `(X_t)_{0≤t≤L}` — the residual-stream reasoning trajectory;
- `ξ_t = X_t − X_{t−1}` — the increments.

Because the model is causal, teacher-forcing the sampled trace reproduces the states that produced
it, so trajectories are recorded *after* generation in a single forward pass.

Two further trajectory types (Appendix B) share the formalism:

- **depth-wise**: `h^(0), ..., h^(Λ)` for a fixed token, increments `h^(ℓ) − h^(ℓ−1) = f_ℓ(h^(ℓ−1))`
  (block outputs). Normalized by the **layer-wise median** to remove growth of residual norm with depth.
- **recurrent-depth** (Geiping et al., 2025): `X_{t+1} = X_t + F(X_t, e)`, so "step" = "layer".

### 1.2 Step deviations (Eq. 1)

    Z_t     = ‖ξ_t‖_2                            (raw)
    Z^w_t   = ‖Σ^{-1/2} (ξ_t − µ)‖_2             (whitened)
    Z^inn_t = ‖X_t − Â X_{t−1} − ĉ‖_2            (innovation)

- `(µ, Σ)` = mean and **shrinkage** covariance of increments, fitted on **verified traces of a
  disjoint problem split**.
- `(Â, ĉ)` = **ridge regression** of `X_t` on `X_{t−1}`, fitted on the same split.
- Whitening removes anisotropy and the massive-activation directions (Sun et al., 2024).
- Theory guarantee: if `ξ_t` is multivariate regularly varying with index `α`, then `Z_t` and `Z^w_t`
  (norms of nondegenerate affine images) are regularly varying with the **same** `α`
  (Basrak & Segers, 2009). `Z^inn_t` also involves the level `X_{t−1}` — **diagnostic only**, no guarantee.

### 1.3 Validity, absorption, `t*` (Sec. 2)

A verifier attaches labels `v_t ∈ {0,1}`. Labels are **absorbing**:

    t* = min{ t : v_t = 0 },     v_s = 0 for all s ≥ t*
    V_L = min_{t≤L} v_t = 1{ t* > L }

Traces are generated **to full length without verifier feedback**; verification is post hoc, so the
law of `(Z_t)` does not depend on the labels. This is a hard requirement on the pipeline.

### 1.4 Extremes (Sec. 2, Sec. 3)

- `F̄ ∈ RV_{−α}` iff `F̄(xy)/F̄(x) → y^{−α}` for all `y>0` as `x→∞`.
- Equivalent (Gnedenko): `F ∈ MDA(G_γ)` with **extreme value index** `γ = 1/α > 0`
  (Fréchet); `γ = 0` = Gumbel domain (Gaussian, exponential, Weibull-type); `γ < 0` needs bounded support.
- The property of the Gumbel domain actually used is **rapid variation**: `F̄(xy)/F̄(x) → 0` for all
  `y>1` (Lemma 7).
- **Order parameter** (this is the paper's `ξ`, and it is *not* `γ`):

      α* = sup{ s > 0 : E Z^s < ∞ } ∈ (0, ∞]
      ξ  = 1/α*

  Under `F̄ ∈ RV_{−α}`: `α* = α`, `ξ = γ`. Every rapidly varying or bounded law: `α* = ∞`, `ξ = 0`.
  So `ξ = max(γ, 0)` whenever `γ` is defined, and `ξ` is defined even when `F` is in no domain of attraction.
- `M_L = max_{t≤L} Z_t`, `S_L = Σ_{t≤L} Z_t`, `µ = E Z`, `x_F = sup{x : F̄(x) > 0}`.
- **Tail process** `(Θ_t)`, `Θ_0 = 1`: `L((Z_t/Z_0)_{|t|≤h} | Z_0 > x) → L((Θ_t)_{|t|≤h})`.
- **Extremal index** `θ ∈ (0,1]`: `P(M_L ≤ u_L) → e^{−θλ}` when `L F̄(u_L) → λ`.

**Notation warning.** The paper uses `ξ` for *two* different things: the increment `ξ_t = X_t − X_{t−1}`
(Sec. 2) and the order parameter `ξ = 1/α*` (Sec. 2, Sec. 3). In this repository the increment is
`delta_t` / `increment` and the order parameter is `xi` / `gamma`. Never overload.

### 1.5 The two hypotheses (Sec. 2)

Let `C ⊂ R^d` be the set of states encoding a valid derivation state, and `A : C → C` the rule map,
Lipschitz on `C`.

- **H_alg**: `X_t = A(X_{t−1}) + ε_t`, `sup_{x∈C} ‖A(x) − x‖ < ∞`, `‖ε_t‖` light-tailed.
  ⇒ `Z_t` rapidly varying or bounded support ⇒ **`ξ = 0`**.
- **H_heur**: `X_t = A_{K_t}(X_{t−1}) + ε_t`, `K_t` selects one of finitely many heuristics `A_k`,
  each agreeing with `A` on its support `S_k ⊂ C` but unconstrained off it.
  ⇒ `F̄ ∈ RV_{−α}` ⇒ **`ξ = 1/α > 0`**.

### 1.6 Coupling hypothesis (Hypothesis 1)

> There exist a read-out layer `ℓ`, a deviation statistic `Z` among Eq. 1 and a tolerance `τ > 0`
> such that, **up to and including the first rejected step**, `v_t = 1{ Z_t ≤ τ }`.

Under (C) + absorption: `{V_L = 0} = {M_L > τ}`; `t*` is the first exceedance; chain failure is
literally the sup-functional event. (C) is an idealization; Sec. 5 treats it as the **null of a
localization test**, with the token-surprisal baseline as the natural competitor.

### 1.7 Intermediate range (Remark 2)

Block outputs of a bounded (pre-norm) architecture have `x_F < ∞`, so the `u→∞` limits do not
literally distinguish the hypotheses. All limits are read over an **intermediate range**
`u ∈ [u_0, u_1]`, `u_1 ≪ x_F`, on which `F̄(uy)/F̄(u) = y^{−α}(1+o(1))` (resp. `= o(1)`) uniformly,
with `u_1/u_0 → ∞`. Estimators target this range. `ξ̂` is a **scale-dependent** quantity.

---

## 2. Theory results the code must reproduce or use

| # | Result | What the code needs it for |
|---|---|---|
| Prop. 1 | Overshoot dichotomy: `Q_u(y) = P(Z > uy \| Z > u) → y^{−α}` under RV; `→ 0` for `y>1` under rapid variation | P3 |
| Cor. 3 | Failure–length law `P(V_L=0) = 1 − e^{−θλ} + o(1) ≈ θ L F̄(τ_L)` | P5 |
| Thm. 4 | Localization: (i) `π_L(Θ)` limit under clustering; (ii) under extremal independence `P(N_τ=1\|V_L=0)→1`, `P(T^max=t*\|V_L=0)→1`, `P(t*=t\|V_L=0)→1/L`, overshoot `→y^{−α}`; (iii) chance level `E[1/L]`, estimated by within-trace permutation | P2 |
| Thm. 5 | Kesten recursion `E_t = a_t E_{t−1} + B_t`; `α` = unique root of `E a^α = 1`; two-heuristic closed form | Simulation, P4 interpretation |
| Thm. 6 | Hill on pooled traces: consistency (needs only `k→∞`, `k/n→0`, `L/k→0`), asymptotic normality `√k(γ̂^H_k − γ) ⇒ N(λ/(1−ρ), γ² σ²_cl)` | Estimation, bootstrap |

### 2.1 Kesten mechanism (Thm. 5) — the simulation target

    E_t = a_t E_{t−1} + B_t,   (a_t) iid > 0,   (B_t) iid ~ N(0, Σ) in R^d,   (a_t) ⊥ (B_t)

- (i) Unique stationary solution `E_t = Σ_{j≥0} a_t···a_{t−j+1} B_{t−j}` a.s. (requires `E log a < 0`).
- (ii) **Heavy tails.** If `P(a>1)>0` and `∃α>0` with `E a^α = 1`, `E a^α log⁺ a < ∞`,
  `E a^{α+δ} < ∞`, `log a` non-arithmetic ⇒ `P(‖E_t‖ > x) ~ c x^{−α}`, `c>0`, and
  **`P(Z_t > x) ~ c · E|a − 1|^α · x^{−α}`** where `Z_t = ‖E_t − E_{t−1}‖`.
- (iii) **Light tails.** If `a ≤ ρ < 1` a.s.: conditionally on `(a_s)_{s≤t}`, `E_t − E_{t−1}` is
  Gaussian with covariance `s_t² Σ`, `1 ≤ s_t² ≤ (2−ρ²)/(1−ρ²) =: s_ρ²`, and with `G ~ N(0,Σ)`

      P(Z_t > x) ≤ exp{ − (x/s_ρ − E‖G‖)_+² / (2‖Σ‖_op) }

  `F̄` rapidly varying, all moments finite, no `α>0` solves `E a^α = 1` ⇒ **H_alg**.
- (iv) **Order parameter.** `α* = sup{s>0 : E‖E_t‖^s < ∞}`, `ξ = 1/α*`. If `a ≤ 1` a.s. then `ξ=0`.
  Along mixtures `L(a) = (1−p)L_− + p L_+` (`L_−` on `(0,1]`, `L_+` on `(1,∞)`), `ξ` is **strictly
  increasing in `p`** on the range where `E log a < 0`.
- (v) **Two heuristics.** `a = ρ < 1` w.p. `1−p`; `a = κ > 1` w.p. `p`; `log ρ / log κ ∉ Q`. For

      0 < p < p_c = log(1/ρ) / log(κ/ρ)

  `α(p)` is the unique positive root of

      (1 − p) ρ^α + p κ^α = 1

  continuous, strictly decreasing; `α(p) ~ log(1/p)/log κ` as `p↓0`; `α(p) ↓ 0` as `p ↑ p_c`
  (Lyapunov exponent vanishes, error ceases to be stationary).

**Note (paper inconsistency).** Figure 1(c) caption writes the closed form as
`(1−p)ρ^α + pγ^α = 1`; Theorem 5(v) writes `(1−p)ρ^α + pκ^α = 1`. The `γ` in the caption is a
typo for `κ`. The code implements the Theorem 5(v) form.

### 2.2 Clustering / displacement prediction (Thm. 4 discussion)

In the Thm. 5 model, a jump at `t*` produced by an expansive step is followed by geometric relaxation

    Z_{t*+j} / Z_{t*} ≈ (1 − ρ) ρ^{j−1} κ / (κ − 1)

so the argmax stays at `t*` unless `ρκ < 1` (then the first relaxation step is larger) or a second
expansive step occurs within `⌈log κ / log(1/ρ)⌉` steps. Conditionally on the exceedance,

    a_{t*} = κ  w.p.  p(κ−1)^α / [ p(κ−1)^α + (1−p)(1−ρ)^α ],   a_{t*} = ρ  otherwise

in which case the window is `⌊log((κ−1)/(1−ρ)) / log(1/ρ)⌋`.

**Numeric target (must be reproduced by simulation):** at `ρ = 0.7`, `κ = 2.5`, `p = 0.05`
(so `α ≈ 2.80`) the two windows are **3 and 4 steps**, displacement probability
`0.83·0.14 + 0.17·0.19 ≈ 0.15`, predicted top-1 rate **0.85** before additive noise `B_t` and
finite-`τ` effects, against a **simulated 0.80** (top-3 **0.95**, chance level **0.016**).

---

## 3. Estimators (Sec. 4, Eq. 3)

Pooled order statistics `Z_(1) ≥ ... ≥ Z_(n)`, `n = m·L`, `k` upper order statistics.

    γ̂^H_k   = (1/k) Σ_{i=1}^{k} log( Z_(i) / Z_(k+1) )                        Hill
    M^(r)_k = (1/k) Σ_{i≤k} ( log Z_(i) / Z_(k+1) )^r
    γ̂^M_k   = M^(1)_k + 1 − (1/2) ( 1 − (M^(1)_k)² / M^(2)_k )^{−1}           moment (Dekkers+89)
    γ̂^GPD_k = argmax_γ max_{σ>0} ℓ_GPD( γ, σ ; { Z_(i) − Z_(k+1) }_{i≤k} )    GPD MLE

Properties the code must respect:

- Hill is MLE of `γ>0` for a Pareto tail, **most efficient under H_heur**, but **biased upward under
  H_alg** — it estimates `max(γ,0)` and *cannot return a nonpositive value*.
- Moment estimator is consistent for **every real `γ`**; GPD MLE for `γ > −1` (asymptotically normal
  for `γ > −1/2`). These two **can reject H_heur**: a CI for `γ` containing 0 is the H_alg outcome.
- **Report all three.** Agreement across a range of `k` = operational definition of a well-identified tail.

### 3.1 Threshold / `k` selection

- Primary: **double bootstrap** of Danielsson et al. (2001), `n1 = n^0.9`, **200 resamples**.
- Cross-check: **Kolmogorov–Smirnov criterion** of Clauset et al. (2009).
- **Always** show the full Hill plot `k ↦ γ̂^H_k` over `k ∈ [20, n/2]` with pointwise 95% bands.

### 3.2 Trace bootstrap

- Resample **traces** with replacement, recompute `γ̂^H` with the **same fraction `k/n`**.
- **500 resamples**. When several samples share a prompt, **resample prompts**, not samples.
- Resampling individual steps destroys cluster structure and underestimates variance by `σ²_cl`.
- Used as a **variance approximation only**: full-sample bootstrap of an intermediate order statistic
  is not consistent for its distribution and does not capture the bias `λ/(1−ρ)` (Hall, 1990). A
  consistent scheme resamples `m' → ∞`, `m'/m → 0`; `k` selection relies on subsampling for the same reason.

### 3.3 Model comparison

Fit excesses by **GPD, exponential and Weibull**; report **likelihood-ratio comparisons**, so that
`H_alg` is a **positive finding** (light-tailed fit beats Pareto fit), not merely the absence of a plateau.

### 3.4 Data structure assumption (Thm. 6)

Traces are i.i.d. sampling units. **No assumption** on within-trace dependence or within-trace
stationarity. Only assumption: the average marginal survival
`F̄(x) = L^{-1} Σ_{t≤L} P(Z_t > x)` is `RV_{−α}`.

Pooling across prompts has a price: if prompt-specific tails have indices `α_j`, the pooled tail is
`RV` with `α = min_j α_j` — pooled estimates target the **heaviest** component and can show mixture
curvature at finite `k`. **Therefore also report per-prompt-family estimates.**

Cluster variance:

    σ²_cl = lim_{x→∞} Var( Σ_{t≤L} g_x(Z_t) ) / ( γ² L F̄(x) ),   g_x(z) = log⁺(z/x) − γ 1{z > x}

`σ²_cl = 1` for independent steps; `σ²_cl > 1` when large steps cluster (Thm. 5 relaxation).

---

## 4. Predictions P1–P5 (Sec. 5)

Ordered from weakest to strongest assumptions.

### P1 — Tail separation
Step deviations of **refuted** traces have a heavier tail than **verified** ones:
**`γ̂_ref > γ̂_ver`**, and the excess is carried by the steps **at and after `t*`**.

Subsets to estimate separately:
1. `verified` (all steps of verified traces);
2. `refuted, t < t*` (pre-rejection segment) — **the diagnostic one**: a heavier pre-rejection tail
   than on verified traces would indicate the model was already "off-manifold" *before the kernel noticed*;
3. `refuted, t ≥ t*` (post-rejection segment).

Expected pattern stated in the paper: **verified ≈ pre-rejection < post-rejection**.

### P2 — Localization
Among refuted traces, `T^max = argmax_t Z_t` (smallest index attaining the max) coincides with `t*`
**far above** the chance level `E[1/L]` and **above** the token-surprisal baseline.

- Baseline: `argmin_t` mean token log-probability of the step (least likely step).
- Permutation null: shuffle step positions within each trace, **2000 permutations**.
- Report top-1 and top-3 hit rates **together with `E[1/L]` over the refuted traces** (the test
  conditions on `L`: shorter traces have higher chance level).
- Also report the **ROC of "jump size" as a per-step detector of the first rejection**, and compare
  to ICR-style supervised hidden-state probes as an **upper bound**.

### P3 — Overshoot
`τ` = the `(1−q)`-quantile of `Z` on **verified** traces, `q ∈ {1e-2, 1e-3}`.
Among refuted traces with `Z_{t*} > τ`: plot the empirical survival of `Z_{t*}/τ` on log–log axes,
fit a **GPD to `Z_{t*} − τ`**, report `γ̂` with a trace-bootstrap interval.
Under `H_heur` the fitted shape agrees with pooled `γ̂` (Table 1); under `H_alg` it is `≤ 0`.

### P4 — Order parameter across training
For a model that acquires a circuit during training, `γ̂` drops **abruptly** at the transition,
coinciding with the excluded-loss / restricted-loss progress measures of Nanda et al. (2023) and the
generalization jump of Wang et al. (2024).

### P5 — Length law
Fit `P(V_L = 1) = exp(−θ L F̄(τ))` by maximum likelihood in `(θ, τ)`, with `F̄` the **GPD tail fitted
on verified traces**; compare with an **unconstrained per-length fit by a likelihood-ratio test**.
The fitted tolerance dependence should be **polynomial** (`θ L τ^{−α} ℓ(τ)` under H_heur;
`o(τ^{−s})` for every `s>0` under H_alg).

Where tested: **P1–P3** on Lean 4 (5.1) and on synthetic deduction (5.2); **P4** on training runs (5.3);
**P5** on synthetic deduction with `L ∈ {3,...,12}` (Appendix B.4).

---

## 5. Experimental settings

### 5.1 Lean 4 proof traces (Sec. 5.1, B.1–B.3)

**Models (open-weight provers, activations accessible):**
- DeepSeek-Prover-V2-7B (Ren et al., 2025)
- Goedel-Prover-V2-8B (Lin et al., 2025)
- Kimina-Prover-8B (Wang et al., 2025)

**Benchmarks:** miniF2F-test, ProofNet, PutnamBench — `[list final benchmarks]`.

**Sampling:** `N = [x.xx]` whole proofs per problem, temperature `T ∈ {0.6, 1.0}`, vLLM for sampling;
activations recorded with the HuggingFace implementation in **bfloat16 with float32 accumulation of
the norms**.

**Step segmentation (Lean):** one tactic per line; tactic blocks joined by `;` or `<;>` and
structured blocks (`have`, `calc`, `cases` with bullets) segmented at the granularity at which the
REPL reports errors, so that **every segment receives a label**.

**Labels (B.2):** replay tactics one at a time in the Lean REPL in tactic mode.
`v_t = 1` if tactic `t` elaborates without error against the proof state left by tactics `1..t−1`
**and does not close the goal with `sorry`**. `t*` = first tactic with an error.
- `unsolved goals` at the end of a proof ⇒ recorded as a **failure of the last step**.
- Traces whose first error is a **parse error of the whole proof are discarded** (no step structure).
- **Time-outs are treated as failures at the offending step and reported separately.**
- Whole-proof verification and step replay agree on chain validity by construction.
- `[Report the number of traces in each category.]`

**Read-out:** forward hooks on decoder blocks, block output at the token positions ending each step;
`X_0` at last prompt token. Layers `ℓ ∈ {⌊Λ/4⌋, ⌊Λ/2⌋, ⌊3Λ/4⌋}`; full layer sweep as an ablation.
Token log-probabilities collected in the same pass (surprisal baseline for P2).

**CoT-mode provers:** informal reasoning before the formal proof is **not labeled**; only formal
tactics are steps; the informal segment is reported separately.

**Headline statistic for Tables 1–2:** `Z^w`, layer `Λ/2`.

### 5.2 Synthetic first-order deduction (Sec. 5.2)

PrOntoQA-style (Saparov & He, 2023): ontologies with known ground truth, chains of
`L ∈ {3, ..., 12}` modus ponens steps, symbolic checker labelling each generated step as
**valid instantiation of a rule / invalid inference / non-inference**.

Models: Llama-3.1-8B-Instruct, Qwen2.5-7B-Instruct, Qwen3-8B `[finalize model list]`.
Chain-of-thought prompting; one sentence per step, **final answer excluded**.
Same estimators, baselines and nulls. Varying `L` is what makes P5 testable.

### 5.3 Training dynamics (Sec. 5.3, B.5)

**Modular addition (Nanda et al., 2023).** One-layer transformer, `d = 128`, 4 heads, `p = 113`,
weight decay 1, full-batch AdamW, **40,000 steps**, checkpoints every **100 steps**. At each
checkpoint pool block-output norms over all `p²` inputs (train and held-out); compute `γ̂` together
with **excluded loss** and **restricted loss**.

**Two-hop composition (Wang et al., 2024).** Eight-layer transformer, in-distribution and OOD test
splits; depth-wise step deviations pooled over held-out inputs at each checkpoint.

**Recurrent depth (Geiping et al., 2025).** Prelude + recurrent block + coda; `d = 256`,
4 recurrent layers, `r ∈ {4, 8, 16, 32}` recurrences; trained on synthetic deduction;
`γ̂` of `‖X_{t+1} − X_t‖` as a function of training step and of test-time `r`. `[Hyperparameters.]`

### 5.4 Constructed controls (B.6)

- **Positive control for H_alg:** Tracr-compiled transformer (Lindner et al., 2023) implementing the
  deduction rule ⇒ bounded increments, **`γ̂^M < 0`**.
- **Positive control for H_heur:** an **n-gram lookup model** trained on the same traces.

### 5.5 Controls and ablations (B.7)

Stability across:
1. read-out layers;
2. the three deviation statistics of Eq. 1 — in particular **whitening**, which removes the
   massive-activation directions of Sun et al. (2024) that could otherwise dominate norms;
3. sampling temperature (controls mixing and hence clustering, per the Markov-chain view of Zekri et al., 2025);
4. choice of `k` (full Hill plots);
5. **split-half reliability** of `γ̂` across problem splits;
6. **label noise**: randomly relabel a fraction of steps and check that **P2 degrades linearly**.

`[Ablation table in the appendix.]`

---

## 6. Figures and tables to produce

| Artifact | Content | Status in paper |
|---|---|---|
| **Figure 1** | Heuristic-mixture model, `ρ=0.7`, `κ=2.5`, `d=8`, **3000 traces × 64 steps per setting**. (a) one trace per regime, `p=0` vs `p=0.05`, with `τ` line; (b) survival of `Z_t`, log–log, dotted slope `−α(p)`, `p ∈ {0, 0.02, 0.05, 0.10}` with `α = —, 3.97, 2.80, 1.82`; (c) `ξ = 1/α` vs `p ∈ [0, 0.20]`: closed form line, Hill + trace-bootstrap CI, moment estimator (must return `ξ≈0` at `p=0`); (d) overshoot `Z_{t*}/τ` survival, `τ` = 99.9% quantile, `n=185` (p=0) and `n=114` (p=0.05), Pareto asymptote `u^{−α}` | **Complete in paper** — reproduce exactly |
| **Table 1** | P1. Hill/moment/GPD `γ̂` on pooled step deviations (`Z^w`, layer `Λ/2`), 95% trace-bootstrap intervals, `k` by double bootstrap. Rows: 3 provers × {verified, refuted t<t*, refuted t≥t*}. Columns: `m` traces, `γ̂^H`, `γ̂^M`, `γ̂^GPD` | **All `[x.xx]`** |
| **Table 2** | P2. Per model: statistic (`Z^w, ℓ=Λ/2`), top-1, top-3, chance, surprisal top-1, permutation null (mean ± s.d.), `p` | **All `[x.xx]`** |
| **Fig. (P3)** | Survival of `Z_{t*}/τ` log–log + fitted GPD shapes | `[Figure and fitted shapes.]` |
| **Table (5.2)** | Analogue of Tables 1–2 on synthetic deduction + length-law fit | `[Table analogous to Tables 1–2; length-law fit.]` |
| **Fig. (P4)** | `γ̂`, train/test accuracy, progress measures vs training steps | `[Figure]` |
| **Table (B.3)** | model, params, `Λ`, `d`, benchmark, #problems, samples/problem, temperature, max tokens, #verified/#refuted traces, mean trace length | `[Table with: ...]` |
| **B.9** | Hill plots for all layers and statistics; ablation tables (temperature, whitening, layer, `k`); split-half reliability; label-noise experiment; spectral measure of largest jumps projected on the unembedding | `[...]` |

---

## 7. Complete list of placeholders in the paper

Every item below is a number this repository must produce.

| Location | Placeholder | What is needed |
|---|---|---|
| Abstract | `[Numbers to be filled in from the experiments in Section 5.]` | headline `γ̂_ref` vs `γ̂_ver`, top-1 localization rate vs chance, `γ̂` drop at grokking |
| Sec. 1, contribution 5 | `[Headline numbers.]` | same |
| Sec. 5.1 setup | `[list final benchmarks]` | which of miniF2F-test / ProofNet / PutnamBench are used |
| Sec. 5.1 setup | `N = [x.xx]` | samples per problem |
| Table 1 | `[Fill from tailflow output.]`, 3×3×(1+3×3) `[x.xx]` | `m`, `γ̂^H`, `γ̂^M`, `γ̂^GPD` + CIs |
| Sec. 5.1 P1 | `[Expected pattern: ...]` | confirm/refute verified ≈ pre-rejection < post-rejection |
| Table 2 | `[Fill.]`, 3×6 `[x.xx]` | top-1, top-3, chance, surprisal, perm-null mean±sd, `p` |
| Sec. 5.1 P2 | `[Report hit rates, permutation p-values, ROC ...]` | ROC/AUC of jump size as per-step detector; supervised probe upper bound |
| Sec. 5.1 P3 | `[Figure and fitted shapes.]` | GPD shape at `q ∈ {1e-2, 1e-3}` + CI |
| Sec. 5.2 | `[finalize model list]`, `[Table analogous to Tables 1–2; length-law fit.]` | full synthetic-deduction results |
| Sec. 5.3 | `[Figure: γ̂, train/test accuracy and progress measures ...]`, `[Results.]` | grokking figure; recurrent-depth results |
| Repro. statement | `[Add anonymized repository link.]` | anonymized repo URL |
| AI use statement | `[Required by ICLR 2027 ...]` | text |
| B.2 | `[Report the number of traces in each category.]` | verified / refuted / parse-error-discarded / timeout counts |
| B.3 | `[Table with: model, parameter count, Λ, d, benchmark, ...]` | full sampling table |
| B.4 | `[Result.]` (length law) | `(θ̂, τ̂)` + LR test vs unconstrained |
| B.5 | `[Hyperparameters.]` (recurrent depth) | full hyperparameter table |
| B.7 | `[Ablation table in the appendix.]` | six ablation axes |
| B.8 | `[GPU type and hours ...]` | compute accounting |
| B.9 | `[Hill plots ...; ablation tables ...; split-half ...; label noise ...; spectral measure ...]` | appendix figures |

---

## 8. Feasibility on the available hardware

Recorded here because it determines execution order; see `docs/system_report.md` for the audit.

The machine is an Apple M4 MacBook, 16 GB unified memory, **no CUDA, no Slurm**. Consequences:

| Stage | Feasible locally? | Note |
|---|---|---|
| Kesten simulation, Figure 1 | **Yes** | pure NumPy, CPU |
| Estimators + tests + bootstrap | **Yes** | CPU |
| Lean 4 + Mathlib + REPL step replay | **Yes** | elan user-space install; Mathlib cache download; CPU-bound |
| Modular-addition grokking (P4) | **Yes** | 1-layer, `d=128`, `p=113`; MPS or CPU |
| Two-hop composition (P4) | **Probably** | 8-layer small transformer; MPS |
| Recurrent-depth (P4) | **Probably** | `d=256`; MPS |
| Tracr control | **Yes** | CPU |
| Synthetic deduction on 7–8B models | **Marginal** | 8B in bf16 ≈ 16 GB; needs 4-bit or a smaller stand-in; vLLM is Linux+CUDA only |
| Lean prover traces from 7–8B provers | **No (as specified)** | generation + teacher-forced activation extraction over thousands of proofs is not tractable in 16 GB without CUDA |

**Order of execution** therefore: simulation and statistics first (fully reproduce Figure 1 and the
Thm. 4/5 numeric targets), then Lean toolchain and the labelling pipeline, then the grokking
experiments, then the model-dependent stages at whatever scale the hardware allows — with any
reduction in scale recorded explicitly, and never silently substituted for the paper's protocol.

**No result may be fabricated.** A negative or inconclusive outcome is a valid scientific result and
is to be reported as such.
