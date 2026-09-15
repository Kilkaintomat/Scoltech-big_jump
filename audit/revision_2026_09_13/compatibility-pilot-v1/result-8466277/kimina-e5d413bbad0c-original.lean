set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem amc12a_2021_p7
  (x y : ℝ) :
  1 ≤ ((x * y) - 1)^2 + (x + y)^2 := by
  nlinarith [sq_nonneg (x * y - 1), sq_nonneg (x + y), sq_nonneg (x - y), sq_nonneg (x * y), sq_nonneg (x), sq_nonneg (y)]

#print axioms amc12a_2021_p7
