# Data schema

Every P1-P5 test reads one long table, whatever produced the traces: the Lean 4 kernel over a
prover's output, a symbolic checker over a chain of thought, or the Kesten surrogate of
Theorem 5. Having one schema is what lets the same test code be validated where the answer is
known in closed form and then run unchanged on real traces.

Defined and enforced in [`src/onebigjump/experiments/dataset.py`](../src/onebigjump/experiments/dataset.py).

## The deviations table

One row per `(trace, step, layer, statistic)`.

| Column | Type | Meaning |
|---|---|---|
| `trace_id` | str | one sampled proof or trajectory; **the resampling unit** |
| `prompt_id` | str | the problem. Several traces share one; then prompts are the resampling unit |
| `model` | str | model identifier, or `kesten` for the surrogate |
| `layer` | int | read-out block `l`. The paper uses `floor(Lambda/4)`, `floor(Lambda/2)`, `floor(3Lambda/4)` |
| `statistic` | str | `raw`, `whitened` or `innovation` -- the three of equation 1 |
| `t` | int | step index, 0-based |
| `L` | int | length of this trace in steps |
| `z` | float | the step deviation `Z_t`, `Z^w_t` or `Z^inn_t` |
| `valid` | bool | `v_t`. **Absorbing**: never rises back to 1 after a 0 |
| `t_star` | int or NaN | first rejected step; NaN on a verified trace |
| `outcome` | str | `verified` or `refuted` |
| `surprisal` | float | mean negative token log-probability of the step; the P2 baseline. NaN where unavailable |

### Invariants, checked by `validate_table`

1. every column above is present;
2. `z >= 0` and `t >= 0`;
3. no duplicate `t` within a `(trace_id, layer, statistic)`;
4. **labels are absorbing** -- `v_t` may fall from 1 to 0 but never rise.

The fourth is the one that matters. Section 2 defines labels to be absorbing because a false
lemma propagates, and every result that conditions on `t*` -- P1's subsets, P2's localisation,
P3's overshoot -- assumes it. A table that violates it is rejected rather than analysed.

### Subsets

`subset(df, name)` selects the rows of Table 1:

| Name | Rows |
|---|---|
| `verified` | every step of a verified trace |
| `refuted_pre` | steps strictly before `t*`. **The diagnostic one**: a heavier tail here than on verified traces means the model was off-manifold before the kernel noticed |
| `refuted_post` | steps at and after `t*` |
| `refuted_all` | every step of a refuted trace |

## Labelled Lean traces

JSONL, one `ProofTrace` per line, from
[`src/onebigjump/lean/schemas.py`](../src/onebigjump/lean/schemas.py). Written by
`onebigjump lean-verify` to `<out_dir>/traces.jsonl`.

| Field | Meaning |
|---|---|
| `trace_id`, `problem_id`, `model_id`, `temperature`, `sample_index` | provenance of the sample |
| `header`, `proof_text` | the theorem statement up to `:= by`, and the whole sampled proof |
| `steps[]` | one `StepLabel` per tactic |
| `outcome` | `verified`, `refuted`, `parse_error`, `timeout`, `repl_failure` |
| `t_star` | first rejected step, or null |
| `whole_proof_ok` | whether the whole proof compiled -- **must agree with the step replay** |

### Step status vocabulary

Appendix B.2 distinguishes these cases and so does the schema; collapsing them loses information
the analysis needs.

| Status | Meaning |
|---|---|
| `ok` | elaborated against the state left by tactics `1..t-1` |
| `error` | did not; a genuine `t*` |
| `timeout` | the elaborator did not finish. Reported separately, per B.2 |
| `sorry` | the goal was closed by `sorry`, which compiles but is not a proof |
| `unsolved_goals` | the proof ended with goals remaining -- a failure of the *last* step |
| `unreached` | a step after `t*`. Its label is 0, but it was never run, and counting it as an observed failure would fabricate data |

`parse_error` traces are **discarded, not labelled**: a proof that does not parse has no step
structure, and inventing rows for it would put unlabelled steps into a labelled analysis.

## Residual-stream trajectories

Produced by `models.extract_trajectory`, one `Trajectory` per `(trace, layer)`:

| Field | Shape | Meaning |
|---|---|---|
| `states` | `(L+1, d)` | `X_0` at the last prompt token, then `X_t` at the last token of each step |
| `surprisal` | `(L,)` | mean negative token log-probability per step |
| `layer`, `d_model`, `n_steps` | | |

Increments are `xi_t = X_t - X_{t-1}`, and the three statistics of equation 1 follow from them.

### Calibration

`(mu, Sigma)` and `(A_hat, c_hat)` are fitted on **verified traces of a disjoint problem split**
and applied unchanged. Fitting them on the traces they are applied to would leak the label into
the statistic and make part of P1's separation an artefact of the fit.

Stored as `.npz` with `mean`, `whitener`, `ridge_a`, `ridge_c` and the settings that produced
them, alongside a JSON summary carrying `increments_per_dim` -- the diagnostic that says whether
the whitening is determined at all. Below roughly two increments per dimension it is not, and
`fit_calibration` refuses rather than returning a statistic with no spread left.

## Run manifests

Every run writes `<out_dir>/manifest.json`: the resolved config, the seed, the git commit and
whether the tree was dirty, package versions, hardware, wall time, a SHA-256 of every output, the
headline metrics, and any recorded deviation from the paper's protocol. See
[`reproducibility.md`](reproducibility.md).
