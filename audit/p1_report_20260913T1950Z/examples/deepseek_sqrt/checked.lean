import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_algebra_433
  (f : ℝ → ℝ)
  (h₀ : ∀ x, f x = 3 * Real.sqrt (2 * x - 7) - 8) :
  f 8 = 1 := by
  have h₁ : f 8 = 3 * Real.sqrt (2 * (8 : ℝ) - 7) - 8 := by
    rw [h₀]
    <;> norm_num
  
  have h₂ : f 8 = 1 := by
    rw [h₁]
    have h₃ : Real.sqrt (2 * (8 : ℝ) - 7) = 3 := by
      rw [Real.sqrt_eq_iff_sq_eq] <;>
      norm_num
      <;>
      nlinarith [Real.sqrt_nonneg 9, Real.sq_sqrt (show 0 ≤ 9 by norm_num)]
    rw [h₃]
    <;> norm_num
    <;>
    linarith
  
  rw [h₂]
  <;> norm_num
