import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem aime_1988_p4
  (n : ℕ)
  (a : ℕ → ℝ)
  (h₀ : ∀ n, abs (a n) < 1)
  (h₁ : ∑ k ∈ Finset.range n, (abs (a k)) = 19 + abs (∑ k ∈ Finset.range n, a k)) :
  20 ≤ n := by
  by_contra h
  push_neg at h
  have h2 : n ≤ 19 := by
    omega
  have h3 : ∑ k in Finset.range n, abs (a k) < (n : ℝ) := by
    have h4 : ∀ k ∈ Finset.range n, abs (a k) < 1 := by
      intro k hk
      specialize h₀ k
      simpa using h₀
    have h5 : ∑ k in Finset.range n, abs (a k) < ∑ k in Finset.range n, (1 : ℝ) := by
      apply Finset.sum_lt_sum
      · -- Show that for all k in range n, abs (a k) ≤ (1 : ℝ)
        intro k hk
        have h6 : abs (a k) < 1 := h4 k hk
        linarith
      · -- Show that there exists k in range n such that abs (a k) < (1 : ℝ)
        use 0
        constructor
        · -- Show that 0 is in range n
          simp
          all_goals omega
        · -- Show that abs (a 0) < (1 : ℝ)
          have h6 : abs (a 0) < 1 := h4 0 (by simp; all_goals omega)
          simpa using h6
    have h6 : ∑ k in Finset.range n, (1 : ℝ) = (n : ℝ) := by
      simp
    linarith [h5, h6]
  have h7 : (n : ℝ) ≤ (19 : ℝ) := by
    have hn : (n : ℝ) ≤ (19 : ℝ) := by
      exact_mod_cast (show n ≤ 19 by omega)
    linarith
  have h8 : ∑ k in Finset.range n, abs (a k) ≥ (19 : ℝ) := by
    have h9 : ∑ k in Finset.range n, abs (a k) = 19 + abs (∑ k in Finset.range n, a k) := by
      linarith [h₁]
    have h10 : abs (∑ k in Finset.range n, a k) ≥ 0 := abs_nonneg (∑ k in Finset.range n, a k)
    linarith
  linarith [h3, h8, h7]

#print axioms aime_1988_p4
