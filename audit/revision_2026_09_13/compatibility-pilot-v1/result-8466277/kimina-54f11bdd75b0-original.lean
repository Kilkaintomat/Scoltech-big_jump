set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_296
  (n : ℕ)
  (h₀ : 2 ≤ n)
  (h₁ : ∃ x, x^3 = n)
  (h₂ : ∃ t, t^4 = n) :
  4096 ≤ n := by
  rcases h₁ with ⟨x, hx⟩
  rcases h₂ with ⟨t, ht⟩
  by_contra h
  push_neg at h
  have h3 : x ≤ 15 := by
    by_contra h4
    push_neg at h4
    have h4' : x ≥ 16 := by omega
    have h5 : x^3 ≥ 4096 := by
      have h6 : x ≥ 16 := h4'
      have h7 : x^3 ≥ 16^3 := by
        apply Nat.pow_le_pow_of_le_left
        all_goals linarith
      norm_num at h7 ⊢
      linarith
    have h8 : n < 4096 := by linarith
    have h9 : x^3 < 4096 := by linarith [hx, h8]
    linarith
  have h4 : t ≤ 7 := by
    by_contra h5
    push_neg at h5
    have h5' : t ≥ 8 := by omega
    have h6 : t^4 ≥ 4096 := by
      have h7 : t ≥ 8 := h5'
      have h8 : t^4 ≥ 8^4 := by
        apply Nat.pow_le_pow_of_le_left
        all_goals linarith
      norm_num at h8 ⊢
      linarith
    have h8 : n < 4096 := by linarith
    have h9 : t^4 < 4096 := by linarith [ht, h8]
    linarith
  interval_cases t <;> interval_cases x <;> omega

#print axioms mathd_numbertheory_296
