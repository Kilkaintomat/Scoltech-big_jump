set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_233
  (b :  ZMod (11^2))
  (h₀ : b = 24⁻¹) :
  b = 116 := by 
  rw [h₀]
  decide +kernel

#print axioms mathd_numbertheory_233
