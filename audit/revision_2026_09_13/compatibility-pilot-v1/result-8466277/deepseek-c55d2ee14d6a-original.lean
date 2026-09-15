set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem algebra_absapbon1pabsapbleqsumabsaon1pabsa
  (a b : ℝ) :
  abs (a + b) / (1 + abs (a + b)) ≤ abs a / (1 + abs a) + abs b / (1 + abs b) := by
  have h₀ : abs (a + b) ≤ abs a + abs b := by
    exact?
    <;>
    linarith [abs_add a b]
    <;>
    linarith [abs_add a b]
    <;>
    linarith [abs_add a b]
  
  have h₁ : abs (a + b) / (1 + abs (a + b)) ≤ (abs a + abs b) / (1 + abs a + abs b) := by
    have h₁ : 0 ≤ abs a := abs_nonneg a
    have h₂ : 0 ≤ abs b := abs_nonneg b
    have h₃ : 0 ≤ abs a + abs b := by linarith
    have h₄ : 0 ≤ 1 + abs a + abs b := by linarith
    have h₅ : 0 ≤ 1 + abs (a + b) := by positivity
    have h₆ : 0 ≤ (1 + abs a + abs b) * (1 + abs (a + b)) := by positivity
    -- Use the division inequality to compare the fractions
    rw [div_le_div_iff] <;>
    (try positivity) <;>
    (try nlinarith [h₀]) <;>
    nlinarith [abs_add a b, abs_nonneg (a + b), abs_nonneg a, abs_nonneg b,
      abs_add a b, abs_nonneg (a + b), abs_nonneg a, abs_nonneg b]
  
  have h₂ : (abs a + abs b) / (1 + abs a + abs b) ≤ abs a / (1 + abs a) + abs b / (1 + abs b) := by
    have h₃ : 0 ≤ abs a := abs_nonneg a
    have h₄ : 0 ≤ abs b := abs_nonneg b
    have h₅ : 0 ≤ 1 + abs a + abs b := by linarith
    have h₆ : 0 < 1 + abs a := by positivity
    have h₇ : 0 < 1 + abs b := by positivity
    have h₈ : 0 < (1 + abs a) * (1 + abs b) := by positivity
    field_simp
    rw [div_le_div_iff] <;>
      nlinarith [sq_nonneg (abs a - abs b), sq_nonneg (abs a - 1), sq_nonneg (abs b - 1),
        mul_nonneg h₃ h₄, mul_nonneg h₃ (sq_nonneg (abs a - abs b)),
        mul_nonneg h₄ (sq_nonneg (abs a - abs b)), mul_nonneg (sq_nonneg (abs a - 1)) h₄,
        mul_nonneg (sq_nonneg (abs b - 1)) h₃]
  
  have h₃ : abs (a + b) / (1 + abs (a + b)) ≤ abs a / (1 + abs a) + abs b / (1 + abs b) := by
    have h₄ : abs (a + b) / (1 + abs (a + b)) ≤ (abs a + abs b) / (1 + abs a + abs b) := h₁
    have h₅ : (abs a + abs b) / (1 + abs a + abs b) ≤ abs a / (1 + abs a) + abs b / (1 + abs b) := h₂
    have h₆ : abs (a + b) / (1 + abs (a + b)) ≤ abs a / (1 + abs a) + abs b / (1 + abs b) := by
      linarith
    exact h₆
  
  exact h₃

#print axioms algebra_absapbon1pabsapbleqsumabsaon1pabsa
