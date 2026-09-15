import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem amc12a_2009_p9
  (a b c : ℝ)
  (f : ℝ → ℝ)
  (h₀ : ∀ x, f (x + 3) = 3 * x^2 + 7 * x + 4)
  (h₁ : ∀ x, f x = a * x^2 + b * x + c) :
  a + b + c = 2 := by
  have h_a : a = 3 := by
    have h₂ := h₀ 0
    have h₃ := h₀ 1
    have h₄ := h₀ (-1)
    have h₅ := h₀ (-2)
    have h₆ := h₀ 2
    have h₇ := h₀ (-3)
    have h₈ := h₀ 3
    have h₉ := h₀ (-4)
    have h₁₀ := h₀ 4
    have h₁₁ := h₀ (-5)
    have h₁₂ := h₀ 5
    have h₁₃ := h₀ (-6)
    have h₁₄ := h₀ 6
    have h₁₅ := h₀ (-7)
    have h₁₆ := h₀ 7
    have h₁₇ := h₁ 0
    have h₁₈ := h₁ 1
    have h₁₉ := h₁ (-1)
    have h₂₀ := h₁ (-2)
    have h₂₁ := h₁ 2
    have h₂₂ := h₁ (-3)
    have h₂₃ := h₁ 3
    have h₂₄ := h₁ (-4)
    have h₂₅ := h₁ 4
    have h₂₆ := h₁ (-5)
    have h₂₇ := h₁ 5
    have h₂₈ := h₁ (-6)
    have h₂₉ := h₁ 6
    have h₃₀ := h₁ (-7)
    have h₃₁ := h₁ 7
    norm_num [h₁, h₀] at *
    <;>
    (try ring_nf at *) <;>
    (try nlinarith) <;>
    (try linarith) <;>
    (try nlinarith)
    <;>
    (try linarith)
  
  have h_b : b = -11 := by
    have h₂ := h₀ 0
    have h₃ := h₀ 1
    have h₄ := h₀ (-1)
    have h₅ := h₀ (-2)
    have h₆ := h₀ 2
    have h₇ := h₀ (-3)
    have h₈ := h₀ 3
    have h₉ := h₀ (-4)
    have h₁₀ := h₀ 4
    have h₁₁ := h₀ (-5)
    have h₁₂ := h₀ 5
    have h₁₃ := h₀ (-6)
    have h₁₄ := h₀ 6
    have h₁₅ := h₀ (-7)
    have h₁₆ := h₀ 7
    have h₁₇ := h₁ 0
    have h₁₈ := h₁ 1
    have h₁₉ := h₁ (-1)
    have h₂₀ := h₁ (-2)
    have h₂₁ := h₁ 2
    have h₂₂ := h₁ (-3)
    have h₂₃ := h₁ 3
    have h₂₄ := h₁ (-4)
    have h₂₅ := h₁ 4
    have h₂₆ := h₁ (-5)
    have h₂₇ := h₁ 5
    have h₂₈ := h₁ (-6)
    have h₂₉ := h₁ 6
    have h₃₀ := h₁ (-7)
    have h₃₁ := h₁ 7
    norm_num [h₁, h₀, h_a] at *
    <;>
    (try ring_nf at *) <;>
    (try nlinarith) <;>
    (try linarith) <;>
    (try nlinarith)
    <;>
    (try linarith)
  
  have h_c : c = 10 := by
    have h₂ := h₀ 0
    have h₃ := h₀ 1
    have h₄ := h₀ (-1)
    have h₅ := h₀ (-2)
    have h₆ := h₀ 2
    have h₇ := h₀ (-3)
    have h₈ := h₀ 3
    have h₉ := h₀ (-4)
    have h₁₀ := h₀ 4
    have h₁₁ := h₀ (-5)
    have h₁₂ := h₀ 5
    have h₁₃ := h₀ (-6)
    have h₁₄ := h₀ 6
    have h₁₅ := h₀ (-7)
    have h₁₆ := h₀ 7
    have h₁₇ := h₁ 0
    have h₁₈ := h₁ 1
    have h₁₉ := h₁ (-1)
    have h₂₀ := h₁ (-2)
    have h₂₁ := h₁ 2
    have h₂₂ := h₁ (-3)
    have h₂₃ := h₁ 3
    have h₂₄ := h₁ (-4)
    have h₂₅ := h₁ 4
    have h₂₆ := h₁ (-5)
    have h₂₇ := h₁ 5
    have h₂₈ := h₁ (-6)
    have h₂₉ := h₁ 6
    have h₃₀ := h₁ (-7)
    have h₃₁ := h₁ 7
    norm_num [h₁, h₀, h_a, h_b] at *
    <;>
    (try ring_nf at *) <;>
    (try nlinarith) <;>
    (try linarith) <;>
    (try nlinarith)
    <;>
    (try linarith)
  
  have h_sum : a + b + c = 2 := by
    rw [h_a, h_b, h_c]
    <;> norm_num
    <;> linarith
  
  exact h_sum

#print axioms amc12a_2009_p9
