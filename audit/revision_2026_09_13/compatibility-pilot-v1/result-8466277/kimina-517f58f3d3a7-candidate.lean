set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_32
  (S : Finset ℕ)
  (h₀ : ∀ (n : ℕ), n ∈ S ↔ n ∣ 36) :
  ∑ k ∈ S, k = 91 := by
  have h1 : S = {1, 2, 3, 4, 6, 9, 12, 18, 36} := by
    ext n
    simp [h₀]
    constructor
    · -- Assume n ∈ S, so n divides 36
      intro h
      have h2 : n ∣ 36 := h
      have h3 : n ≤ 36 := by
        exact Nat.le_of_dvd (by norm_num) h2
      interval_cases n <;> tauto
    · -- Assume n ∈ {1, 2, 3, 4, 6, 9, 12, 18, 36}, so n divides 36
      rintro (rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl)
      all_goals
        norm_num
  rw [h1]
  decide +kernel

#print axioms mathd_numbertheory_32
