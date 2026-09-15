set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_447 :
  ∑ k ∈ Finset.filter (λ x => 3∣x) (Finset.Icc 1 49), (k % 10) = 78 := by 
  decide +kernel

#print axioms mathd_numbertheory_447
