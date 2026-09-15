import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem algebra_2rootspoly_apatapbeq2asqp2ab
  (a b : ℂ) :
  (a + a) * (a + b) = 2 * a^2 + 2 * (a * b) := by
  have h_main : (a + a) * (a + b) = 2 * a^2 + 2 * (a * b) := by
    -- Expand the left-hand side using the distributive property
    calc
      (a + a) * (a + b) = (2 * a) * (a + b) := by ring
      _ = 2 * a * a + 2 * a * b := by ring
      _ = 2 * a ^ 2 + 2 * (a * b) := by ring
      _ = 2 * a ^ 2 + 2 * (a * b) := by rfl
  exact h_main

#print axioms algebra_2rootspoly_apatapbeq2asqp2ab
