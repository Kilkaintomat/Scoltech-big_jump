import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem induction_sum2kp1npqsqm1
  (n : ℕ) :
  ∑ k ∈ (Finset.range n), 2 * k + 3 = (n + 1)^2 - 1 := by