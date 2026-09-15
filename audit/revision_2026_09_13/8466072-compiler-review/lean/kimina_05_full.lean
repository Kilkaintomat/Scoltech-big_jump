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
  ring

#print axioms algebra_2rootspoly_apatapbeq2asqp2ab
