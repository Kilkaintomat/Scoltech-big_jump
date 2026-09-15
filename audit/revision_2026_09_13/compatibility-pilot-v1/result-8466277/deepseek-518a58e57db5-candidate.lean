set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_668
  (l r :  ZMod 7)
  (h₀ : l = (2 + 3)⁻¹)
  (h₁ : r = 2⁻¹ + 3⁻¹) :
  l - r = 1 := by
  have h₂ : l = 3 := by
    rw [h₀]
    norm_num [ZMod.natCast_self]
    <;> rfl
  
  have h₃ : r = 2 := by
    rw [h₁]
    norm_num [ZMod.natCast_self]
    <;> rfl
  
  have h₄ : l - r = 1 := by
    rw [h₂, h₃]
    <;> rfl
  
  exact h₄

#print axioms mathd_numbertheory_668
