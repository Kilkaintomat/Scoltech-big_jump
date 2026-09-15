set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem aime_1984_p15
  (x y z w : ℝ)
  (h₀ : (x^2 / (2^2 - 1)) + (y^2 / (2^2 - 3^2)) + (z^2 / (2^2 - 5^2)) + (w^2 / (2^2 - 7^2)) = 1)
  (h₁ : (x^2 / (4^2 - 1)) + (y^2 / (4^2 - 3^2)) + (z^2 / (4^2 - 5^2)) + (w^2 / (4^2 - 7^2)) = 1)
  (h₂ : (x^2 / (6^2 - 1)) + (y^2 / (6^2 - 3^2)) + (z^2 / (6^2 - 5^2)) + (w^2 / (6^2 - 7^2)) = 1)
  (h₃ : (x^2 / (8^2 - 1)) + (y^2 / (8^2 - 3^2)) + (z^2 / (8^2 - 5^2)) + (w^2 / (8^2 - 7^2)) = 1) :
  x^2 + y^2 + z^2 + w^2 = 36 := by
  have h₄ : x^2 + y^2 + z^2 + w^2 = 36 := by
    norm_num at h₀ h₁ h₂ h₃ ⊢
    <;>
    (try ring_nf at h₀ h₁ h₂ h₃ ⊢) <;>
    (try nlinarith [sq_nonneg (x - 6), sq_nonneg (y + 4), sq_nonneg (z - 2), sq_nonneg (w - 6)]) <;>
    (try nlinarith [sq_nonneg (x + 6), sq_nonneg (y - 4), sq_nonneg (z + 2), sq_nonneg (w + 6)])
    <;>
    nlinarith [sq_nonneg (x - 2), sq_nonneg (y - 4), sq_nonneg (z + 2), sq_nonneg (w - 6),
      sq_nonneg (x + 2), sq_nonneg (y + 4), sq_nonneg (z - 2), sq_nonneg (w + 6),
      sq_nonneg (x - 6), sq_nonneg (y + 4), sq_nonneg (z + 2), sq_nonneg (w - 2)]
  exact h₄

#print axioms aime_1984_p15
