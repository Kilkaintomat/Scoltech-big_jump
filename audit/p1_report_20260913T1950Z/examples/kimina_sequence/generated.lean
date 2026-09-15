import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology

theorem numbertheory_aneqprodakp4_anmsqrtanp1eq2
  (a : ℕ → ℝ)
  (h₀ : a 0 = 1)
  (h₁ : ∀ n, a (n + 1) = (∏ k ∈ Finset.range (n + 1), (a k)) + 4) :
  ∀ n ≥ 1, a n - Real.sqrt (a (n + 1)) = 2 := by
  have ha1 : a 1 = 5 := by
    specialize h₁ 0
    simp [Finset.prod_range_succ, h₀] at h₁
    linarith
  have ha2 : a 2 = 9 := by
    specialize h₁ 1
    simp [Finset.prod_range_succ, h₀, ha1] at h₁
    linarith
  have ha3 : a 3 = 49 := by
    specialize h₁ 2
    simp [Finset.prod_range_succ, h₀, ha1, ha2] at h₁
    nlinarith
  have ha4 : a 4 = 2209 := by
    specialize h₁ 3
    simp [Finset.prod_range_succ, h₀, ha1, ha2, ha3] at h₁
    nlinarith
  have ha5 : a 5 = 4874049 := by
    specialize h₁ 4
    simp [Finset.prod_range_succ, h₀, ha1, ha2, ha3, ha4] at h₁
    nlinarith
  intro n hn
  have h4 : n ≥ 1 := hn
  have h5 := h₁ 4
  norm_num [Finset.prod_range_succ, h₀, ha1, ha2, ha3, ha4] at h5
  have h11 : a 4 - Real.sqrt (a 5) = 2 := h5
  nlinarith [Real.sqrt_nonneg (a 5), Real.sq_sqrt (show 0 ≤ (a 5 : ℝ) by linarith)]
