set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem amc12_2001_p5 :
  Finset.prod (Finset.filter (λ x => ¬ Even x) (Finset.range 10000)) (id : ℕ → ℕ) = (10000!) / ((2^5000) * 5000!) := by 
  decide +kernel

#print axioms amc12_2001_p5
