# Engineering review of actual pilot proofs

The packet `runs/lean_recovery_20260911/kimina/pilot/review/examples.json` was read during this
audit. This intermediate Kimina verification is preserved as diagnostic evidence; the final
campaign is `runs/lean_recovery_20260911_v3`, reusing the corrected v2 Unicode-EOS parsing and Lean labels.

Findings from the inspected source, axiom audit and recorded Lean replies:

- `algebra_2rootspoly_apatapbeq2asqp2ab` is accepted by both the whole-proof kernel check and
  replay. The multiline `ring_nf <;> simp <;> ring` expression remains one source segment.
- `aimeI_2000_p7` samples fail at the recorded rational/real `exact_mod_cast` step. Earlier
  steps remain valid and subsequent generated steps are marked unreached, preserving absorption.
- `aime_1988_p4` examples contain a generated big-operator `in` binder that the pinned Lean
  environment rejects. These are dialect/parse exclusions; no generated proof is rewritten to
  make it pass. This is a limitation of interpreting success rates in the chosen Lean version.
- Truncated `amc12a_2003_p25` examples lack a closed final Lean block. They remain generation
  truncations without an invented first failing tactic.
- `mathd_numbertheory_211` examples use `native_decide`. Whole-proof and replay both succeed,
  but the axiom audit includes a new theorem-local `_native.native_decide.ax_1`. The frozen
  policy rejects new axioms, so these are `sorry_invalid_proof` policy exclusions, not literal
  `sorry` tokens and not a failed Lean compilation. The allowed axiom set is unchanged.

All original DeepSeek/Goedel disagreement records were inspected before patching: the isolated
`<;>` continuation was rejected by replay even though the complete proof compiled. Rejoining
the operator and operands fixes the segmentation without changing generated source bytes.

This engineering review does not replace the independent review and simulation calibration
required for supported scientific claims. The development measurements remain inconclusive.

## Final acquisition review

Final packets under `runs/lean_recovery_20260911_v3/{deepseek,goedel,kimina}/pilot/review/`
contain 15, 15 and 12 records respectively, including all six original disagreements. Category
records, Lean replies, absorbing status sequences and focused source windows were inspected.
All six former disagreement cases now pass both checks with no changed proof body. In particular,
DeepSeek's complex-polynomial case and both models' `mathd_algebra_35` continuations retain their
multiline combinators. Goedel's unknown `div_lt_iff`, no-progress `field_simp` and failed rewrites
remain localized failures. Substituted theorem statements and obsolete `in` syntax remain
explicit exclusions. No observed exclusion was repaired by changing a generated proof.

The first actual Kimina tail fits also exposed gamma below -1 at the GPD support endpoint.
The final revision retains these raw diagnostic values, sets convergence false, and prevents
failed fits from becoming point estimates, bootstrap replicates or model-comparison evidence.
It does not replace them with a fitted value favourable to either hypothesis.
