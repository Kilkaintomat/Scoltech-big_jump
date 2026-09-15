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
    have h₄ : ∑ k in Finset.range n, abs (a k) < 19 := by
      have h₅ : ∑ k in Finset.range n, abs (a k) < n := by
        have h₆ : ∀ k, k ∈ Finset.range n → abs (a k) < 1 := by
          intro k hk
          exact h₀ k
        have h₇ : ∑ k in Finset.range n, abs (a k) < n := by
          calc
            ∑ k in Finset.range n, abs (a k) ≤ ∑ k in Finset.range n, (1 : ℝ) := by
              apply Finset.sum_le_sum
              intro i hi
              have h₈ : abs (a i) < 1 := h₆ i hi
              have h₉ : abs (a i) ≤ 1 := by linarith [abs_nonneg (a i)]
              linarith
            _ = n := by simp [Finset.sum_const, Finset.card_range]
            _ = (n : ℝ) := by norm_cast
            _ < n := by
              norm_cast
              <;>
              (try omega) <;>
              (try linarith) <;>
              (try
                {
                  have h₈ : n ≤ 19 := by linarith
                  interval_cases n <;> norm_num at * <;> linarith
                })
              <;>
              (try
                {
                  omega
                })
        exact h₇
      have h₈ : (n : ℝ) ≤ 19 := by
        norm_cast
        <;>
        (try omega) <;>
        (try linarith) <;>
        (try
          {
            have h₉ : n ≤ 19 := by linarith
            interval_cases n <;> norm_num at * <;> linarith
          })
      have h₉ : ∑ k in Finset.range n, abs (a k) < (n : ℝ) := by exact_mod_cast h₅
      have h₁₀ : (n : ℝ) ≤ 19 := by exact_mod_cast h₈
      linarith
    have h₅ : ∑ k in Finset.range n, abs (a k) ≥ 19 := by
      have h₆ : ∑ k in Finset.range n, abs (a k) = 19 + abs (∑ k in Finset.range n, a k) := h₁
      have h₇ : abs (∑ k in Finset.range n, a k) ≥ 0 := abs_nonneg _
      linarith
    linarith
  exact h_main

#print axioms aime_1988_p4
