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
  have h₂ : n ≥ 20 := by
    by_contra! h
    have h₃ : n ≤ 19 := by linarith
    have h₄ : ∀ k, k ∈ Finset.range n → abs (a k) < 1 := by
      intro k hk
      exact h₀ k
    have h₅ : ∑ k in Finset.range n, abs (a k) < (n : ℝ) := by
      have h₅₁ : ∑ k in Finset.range n, abs (a k) < (n : ℝ) := by
        calc
          (∑ k in Finset.range n, abs (a k)) ≤ ∑ k in Finset.range n, (1 : ℝ) := by
            apply Finset.sum_le_sum
            intro i hi
            have h₆ : abs (a i) < 1 := h₄ i hi
            have h₇ : abs (a i) ≤ 1 := by linarith [abs_nonneg (a i), abs_lt.mp h₆]
            exact by linarith
          _ = (n : ℝ) := by simp [Finset.sum_const, Finset.card_range]
          _ = (n : ℝ) := by simp
          <;> norm_cast
          <;> simp_all [Finset.sum_const]
          <;> linarith
      exact_mod_cast h₅₁
    have h₆ : (∑ k in Finset.range n, abs (a k)) ≥ 0 := by
      apply Finset.sum_nonneg
      intro i _
      exact abs_nonneg (a i)
    have h₇ : 19 + abs (∑ k in Finset.range n, a k) = ∑ k in Finset.range n, abs (a k) := by
      linarith
    have h₈ : abs (∑ k in Finset.range n, a k) ≤ ∑ k in Finset.range n, abs (a k) := by
      exact?
    have h₉ : (n : ℝ) ≤ 19 := by
      have : n ≤ 19 := by omega
      norm_cast
      <;> omega
    have h₁₀ : (n : ℝ) < 20 := by linarith
    have h₁₁ : (n : ℝ) ≤ 19 := by linarith
    have h₁₂ : ∑ k in Finset.range n, abs (a k) ≥ 0 := by linarith
    have h₁₃ : 19 + abs (∑ k in Finset.range n, a k) = ∑ k in Finset.range n, abs (a k) := by linarith
    have h₁₄ : abs (∑ k in Finset.range n, a k) ≤ ∑ k in Finset.range n, abs (a k) := by linarith
    have h₁₅ : ∑ k in Finset.range n, (abs (a k) : ℝ) < (n : ℝ) := by exact_mod_cast h₅
    have h₁₆ : n ≤ 19 := by linarith
    interval_cases n <;> norm_num [Finset.sum_range_succ, abs_of_nonneg, abs_of_nonpos, abs_le] at h₁₃ h₁₄ h₁₅ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ ⊢ <;>
    (try contradiction) <;>
    (try linarith) <;>
    (try
      {
        cases' le_total 0 (∑ k in Finset.range n, a k) with h h <;>
        simp_all [abs_of_nonneg, abs_of_nonpos, Finset.sum_range_succ, Finset.sum_range_zero, Finset.sum_range_one] <;>
        norm_num <;>
        (try { nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19] }) <;>
        (try { nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19] })
      }) <;>
    (try
      {
        norm_num [Finset.sum_range_succ, abs_of_nonneg, abs_of_nonpos] at * <;>
        nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
      })
    <;>
    norm_num at *
    <;>
    linarith
  
  linarith

#print axioms aime_1988_p4
