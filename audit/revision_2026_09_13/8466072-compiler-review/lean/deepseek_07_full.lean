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
  have h_main : 20 ≤ n := by
    by_contra! h
    have h₂ : n ≤ 19 := by linarith
    have h₃ : n ≤ 19 := by linarith
    interval_cases n <;> norm_num [Finset.sum_range_succ, abs_of_nonneg, abs_of_nonpos, le_of_lt] at h₁ ⊢ <;>
    (try {
      linarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
    }) <;>
    (try {
      cases' le_total 0 (∑ k in Finset.range 0, a k) with h₄ h₄ <;>
      cases' le_total 0 (∑ k in Finset.range 1, a k) with h₅ h₅ <;>
      cases' le_total 0 (∑ k in Finset.range 2, a k) with h₆ h₆ <;>
      cases' le_total 0 (∑ k in Finset.range 3, a k) with h₇ h₇ <;>
      cases' le_total 0 (∑ k in Finset.range 4, a k) with h₈ h₈ <;>
      cases' le_total 0 (∑ k in Finset.range 5, a k) with h₉ h₉ <;>
      cases' le_total 0 (∑ k in Finset.range 6, a k) with h₁₀ h₁₀ <;>
      cases' le_total 0 (∑ k in Finset.range 7, a k) with h₁₁ h₁₁ <;>
      cases' le_total 0 (∑ k in Finset.range 8, a k) with h₁₂ h₁₂ <;>
      cases' le_total 0 (∑ k in Finset.range 9, a k) with h₁₃ h₁₃ <;>
      cases' le_total 0 (∑ k in Finset.range 10, a k) with h₁₄ h₁₄ <;>
      cases' le_total 0 (∑ k in Finset.range 11, a k) with h₁₅ h₁₅ <;>
      cases' le_total 0 (∑ k in Finset.range 12, a k) with h₁₆ h₁₆ <;>
      cases' le_total 0 (∑ k in Finset.range 13, a k) with h₁₇ h₁₇ <;>
      cases' le_total 0 (∑ k in Finset.range 14, a k) with h₁₈ h₁₈ <;>
      cases' le_total 0 (∑ k in Finset.range 15, a k) with h₁₉ h₁₉ <;>
      cases' le_total 0 (∑ k in Finset.range 16, a k) with h₂₀ h₂₀ <;>
      cases' le_total 0 (∑ k in Finset.range 17, a k) with h₂₁ h₂₁ <;>
      cases' le_total 0 (∑ k in Finset.range 18, a k) with h₂₂ h₂₂ <;>
      simp_all [abs_of_nonneg, abs_of_nonpos, abs_of_neg, Finset.sum_range_succ] <;>
      norm_num <;>
      nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
    }) <;>
    (try {
      cases' le_total 0 (∑ k in Finset.range 0, a k) with h₄ h₄ <;>
      cases' le_total 0 (∑ k in Finset.range 19, a k) with h₅ h₅ <;>
      simp_all [abs_of_nonneg, abs_of_nonpos, abs_of_neg, Finset.sum_range_succ] <;>
      norm_num <;>
      nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
    })
    <;>
    (try {
      linarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
    })
    <;>
    (try {
      cases' le_total 0 (∑ k in Finset.range 0, a k) with h₄ h₄ <;>
      cases' le_total 0 (∑ k in Finset.range 19, a k) with h₅ h₅ <;>
      simp_all [abs_of_nonneg, abs_of_nonpos, abs_of_neg, Finset.sum_range_succ] <;>
      norm_num <;>
      nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
    })
    <;>
    (try {
      linarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
    })
  exact h_main

#print axioms aime_1988_p4
