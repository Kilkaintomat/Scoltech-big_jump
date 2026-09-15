import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_211 :
  Finset.card (Finset.filter (λ n => 6 ∣ (4 * ↑n - (2 : ℤ))) (Finset.range 60)) = 20 := by
  decide
#print axioms mathd_numbertheory_211
