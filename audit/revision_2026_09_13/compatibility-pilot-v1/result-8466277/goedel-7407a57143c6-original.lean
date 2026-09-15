set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_algebra_160
  (n x : ℝ)
  (h₀ : n + x = 97)
  (h₁ : n + 5 * x = 265) :
  n + 2 * x = 139 := by
  have h₂ : x = 42 := by
    have h₂₁ : x = 42 := by
      -- Subtract the first equation from the second to eliminate n
      have h₂₂ : (n + 5 * x) - (n + x) = 265 - 97 := by linarith
      -- Simplify the equation to find x
      ring_nf at h₂₂ ⊢
      linarith
    exact h₂₁
  
  have h₃ : n = 55 := by
    have h₃₁ : n = 55 := by
      -- Substitute x = 42 into the first equation to find n
      have h₃₂ : n + x = 97 := h₀
      rw [h₂] at h₃₂
      linarith
    exact h₃₁
  
  have h₄ : n + 2 * x = 139 := by
    rw [h₃, h₂]
    <;> norm_num
    <;> linarith
  
  exact h₄

#print axioms mathd_algebra_160
