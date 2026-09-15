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
    interval_cases n <;> norm_num [Finset.sum_range_succ, abs_of_nonneg, abs_of_nonpos, le_of_lt] at h₁ ⊢
    <;>
    (try contradiction) <;>
    (try
      {
        have h₄ := h₀ 0
        have h₅ := h₀ 1
        have h₆ := h₀ 2
        have h₇ := h₀ 3
        have h₈ := h₀ 4
        have h₉ := h₀ 5
        have h₁₀ := h₀ 6
        have h₁₁ := h₀ 7
        have h₁₂ := h₀ 8
        have h₁₃ := h₀ 9
        have h₁₄ := h₀ 10
        have h₁₅ := h₀ 11
        have h₁₆ := h₀ 12
        have h₁₇ := h₀ 13
        have h₁₈ := h₀ 14
        have h₁₉ := h₀ 15
        have h₂₀ := h₀ 16
        have h₂₁ := h₀ 17
        have h₂₂ := h₀ 18
        have h₂₃ := h₀ 19
        norm_num [abs_lt] at *
        <;>
        (try contradiction) <;>
        (try linarith) <;>
        (try nlinarith) <;>
        (try
          {
            cases' le_total 0 (a 0) with h₂₄ h₂₄ <;>
            cases' le_total 0 (a 1) with h₂₅ h₂₅ <;>
            cases' le_total 0 (a 2) with h₂₆ h₂₆ <;>
            cases' le_total 0 (a 3) with h₂₇ h₂₇ <;>
            cases' le_total 0 (a 4) with h₂₈ h₂₈ <;>
            cases' le_total 0 (a 5) with h₂₉ h₂₉ <;>
            cases' le_total 0 (a 6) with h₃₀ h₃₀ <;>
            cases' le_total 0 (a 7) with h₃₁ h₃₁ <;>
            cases' le_total 0 (a 8) with h₃₂ h₃₂ <;>
            cases' le_total 0 (a 9) with h₃₃ h₃₃ <;>
            simp_all [abs_of_nonneg, abs_of_nonpos, abs_lt] <;>
            nlinarith
          })
      }) <;>
    (try
      {
        cases' le_total 0 (∑ k in Finset.range 19, a k) with h₃₄ h₃₄ <;>
        cases' le_total 0 (a 0) with h₃₅ h₃₅ <;>
        simp_all [abs_of_nonneg, abs_of_nonpos, abs_lt, Finset.sum_range_succ] <;>
        norm_num at * <;>
        (try contradiction) <;>
        (try nlinarith) <;>
        (try
          {
            nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
          })
      }) <;>
    (try
      {
        cases' le_total 0 (∑ k in Finset.range 19, a k) with h₃₆ h₃₆ <;>
        cases' le_total 0 (a 0) with h₃₇ h₃₇ <;>
        simp_all [abs_of_nonneg, abs_of_nonpos, abs_lt, Finset.sum_range_succ] <;>
        norm_num at * <;>
        nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
      })
    <;>
    (try
      {
        norm_num [abs_of_nonneg, abs_of_nonpos, abs_lt] at * <;>
        linarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
      })
    <;>
    (try
      {
        cases' le_total 0 (∑ k in Finset.range 19, a k) with h₃₈ h₃₈ <;>
        cases' le_total 0 (a 0) with h₃₉ h₃₉ <;>
        simp_all [abs_of_nonneg, abs_of_nonpos, abs_lt, Finset.sum_range_succ] <;>
        norm_num at * <;>
        nlinarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
      })
    <;>
    (try
      {
        norm_num [abs_of_nonneg, abs_of_nonpos, abs_lt] at * <;>
        linarith [h₀ 0, h₀ 1, h₀ 2, h₀ 3, h₀ 4, h₀ 5, h₀ 6, h₀ 7, h₀ 8, h₀ 9, h₀ 10, h₀ 11, h₀ 12, h₀ 13, h₀ 14, h₀ 15, h₀ 16, h₀ 17, h₀ 18, h₀ 19]
      })
  exact h_main

#print axioms aime_1988_p4
