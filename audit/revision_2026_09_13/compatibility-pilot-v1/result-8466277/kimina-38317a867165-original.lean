set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_237 :
  (∑ k ∈ (Finset.range 101), k) % 6 = 4 := by
  native_decide

#print axioms mathd_numbertheory_237
