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
    have h₄ : n ≤ 19 := by linarith
    have h₅ : ∑ k in Finset.range n, abs (a k) < n := by
      have h₅₁ : ∀ k, k ∈ Finset.range n → abs (a k) < 1 := by
        intro k hk
        exact h₀ k
      have h₅₂ : ∑ k in Finset.range n, abs (a k) < n := by
        calc
          ∑ k in Finset.range n, abs (a k) < ∑ k in Finset.range n, (1 : ℝ) := by
            exact Finset.sum_lt_sum (fun i hi => by linarith [h₅₁ i hi]) ⟨0, Finset.mem_range.mpr (by
              have h₅₃ : n ≤ 19 := by linarith
              have h₅₄ : 0 < n := by
                by_contra h₅₄
                simp_all [Finset.sum_range_zero]
                <;> norm_num at * <;> nlinarith
              omega), by
              simp_all [abs_lt]
              <;> nlinarith [h₀ 0]⟩
          _ = n := by
            simp [Finset.sum_const, Finset.card_range]
            <;> ring_nf
            <;> field_simp
            <;> linarith
      exact h₅₂
    have h₆ : (19 : ℝ) + abs (∑ k in Finset.range n, a k) ≥ 19 := by
      have h₆₁ : abs (∑ k in Finset.range n, a k) ≥ 0 := abs_nonneg _
      linarith
    have h₇ : ∑ k in Finset.range n, abs (a k) = 19 + abs (∑ k in Finset.range n, a k) := by
      exact h₁
    have h₈ : (n : ℝ) ≤ 19 := by
      norm_cast
      <;> linarith
    have h₉ : ∑ k in Finset.range n, abs (a k) < (n : ℝ) := by
      exact_mod_cast h₅
    have h₁₀ : (19 : ℝ) + abs (∑ k in Finset.range n, a k) ≥ 19 := by
      exact h₆
    have h₁₁ : ∑ k in Finset.range n, abs (a k) < (n : ℝ) := by
      exact_mod_cast h₅
    have h₁₂ : (n : ℝ) ≤ 19 := by
      exact_mod_cast h₈
    have h₁₃ : ∑ k in Finset.range n, abs (a k) ≥ 19 := by
      linarith
    have h₁₄ : (n : ℝ) > 19 := by
      linarith
    have h₁₅ : n > 19 := by
      norm_cast at h₁₄ ⊢
      <;> linarith
    linarith
  exact h_main

#print axioms aime_1988_p4
