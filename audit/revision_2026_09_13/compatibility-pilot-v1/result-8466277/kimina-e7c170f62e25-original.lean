set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_algebra_405
  (S : Finset ℕ)
  (h₀ : ∀ x, x ∈ S ↔ 0 < x ∧ x^2 + 4 * x + 4 < 20) :
  S.card = 2 := by
  have h1 : S = {1, 2} := by
    ext x
    simp [h₀]
    constructor
    · -- Assume x ∈ S, prove x ∈ {1, 2}
      intro h
      rcases h with ⟨hx1, hx2⟩
      have h2 : x ≤ 4 := by
        by_contra h
        push_neg at h
        have h3 : x ≥ 5 := by omega
        have h4 : x ^ 2 + 4 * x + 4 ≥ 20 := by
          nlinarith
        linarith
      interval_cases x <;> tauto
    · -- Assume x ∈ {1, 2}, prove x ∈ S
      rintro (rfl | rfl)
      · -- x = 1
        constructor
        · norm_num
        · norm_num
      · -- x = 2
        constructor
        · norm_num
        · norm_num
  rw [h1]
  native_decide

#print axioms mathd_algebra_405
