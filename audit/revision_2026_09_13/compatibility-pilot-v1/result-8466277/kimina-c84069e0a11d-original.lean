set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_127 :
  (∑ k ∈ (Finset.range 101), 2^k) % 7 = 3 := by
  native_decide

#print axioms mathd_numbertheory_127
