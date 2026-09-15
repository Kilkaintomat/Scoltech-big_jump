import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem aimeI_2000_p7
  (x y z : ℝ)
  (m : ℚ)
  (h₀ : 0 < x ∧ 0 < y ∧ 0 < z)
  (h₁ : x * y * z = 1)
  (h₂ : x + 1 / z = 5)
  (h₃ : y + 1 / x = 29)
  (h₄ : z + 1 / y = m)
  (h₅ : 0 < m) :
  ↑m.den + m.num = 5 := by
  rcases h₀ with ⟨hx, hy, hz⟩
  have eq1 : x * z + 1 = 5 * z := by
    have hz' : z ≠ 0 := by linarith
    field_simp at h₂
    nlinarith
  have eq2 : y * x + 1 = 29 * x := by
    have hx' : x ≠ 0 := by linarith
    field_simp at h₃
    nlinarith
  have eq3 : z * y + 1 = m * y := by
    have hy' : y ≠ 0 := by linarith
    field_simp at h₄
    nlinarith
  have eq4 : x * (1 + y) = 5 := by
    nlinarith [eq1]
  have eq5 : y * (1 + z) = 29 := by
    nlinarith [eq2]
  have eq6 : z * (1 + x) = m := by
    nlinarith [eq3]
  have eq7 : (x * (1 + y)) * (y * (1 + z)) * (z * (1 + x)) = (5 : ℝ) * (29 : ℝ) * (m : ℝ) := by
    rw [eq4, eq5, eq6]
  have eq8 : (x * (1 + y)) * (y * (1 + z)) * (z * (1 + x)) = (1 + x) * (1 + y) * (1 + z) := by
    have hxyz : x * y * z = 1 := h₁
    nlinarith [hxyz, mul_pos hx hy, mul_pos hx hz, mul_pos hy hz]
  rw [eq8] at eq7
  have eq9 : (1 + x) * (1 + y) * (1 + z) = 145 * (m : ℝ) := by
    nlinarith [eq7]
  have eq11 : x + x * y = 5 := by
    nlinarith [eq4]
  have eq12 : y + y * z = 29 := by
    nlinarith [eq5]
  have eq13 : z + z * x = m := by
    nlinarith [eq6]
  have eq14 : (x + x * y) + (y + y * z) + (z + z * x) = (5 : ℝ) + (29 : ℝ) + (m : ℝ) := by
    linarith [eq11, eq12, eq13]
  have eq15 : x + y + z + (x * y + x * z + y * z) = 34 + (m : ℝ) := by
    nlinarith [eq14]
  have hm : m = (1 / 4 : ℚ) := by
    have h6 : (m : ℝ) = (1 / 4 : ℝ) := by
      nlinarith [eq9, eq15]
    exact_mod_cast h6
  rw [hm]
  native_decide

#print axioms aimeI_2000_p7
