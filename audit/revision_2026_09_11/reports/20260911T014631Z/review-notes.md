# Engineering review of actual pilot proofs

The packet `runs/lean_recovery_20260911/kimina/pilot/review/examples.json` was read during this
audit. This intermediate Kimina verification is preserved as diagnostic evidence; the final
campaign is `runs/lean_recovery_20260911_v2`, using the corrected Unicode-EOS parser.

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
