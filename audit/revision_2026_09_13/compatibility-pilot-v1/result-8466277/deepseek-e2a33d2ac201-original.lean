set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem mathd_numbertheory_764
  (p : ℕ)
  (h₀ : Nat.Prime p)
  (h₁ : 7 ≤ p) :
  ∑ k ∈ Finset.Icc 1 (p-2), ((k: ZMod p)⁻¹ * ((k: ZMod p) + 1)⁻¹) = 2 := by
  have h_main : ∑ k ∈ Finset.Icc 1 (p-2), ((k: ZMod p)⁻¹ * ((k: ZMod p) + 1)⁻¹) = 2 := by
    haveI := Fact.mk h₀
    rcases p with (_ | _ | _ | _ | _ | _ | _ | _ | _ | _ | p) <;> simp_all [ZMod.nat_cast_self, Finset.sum_range_succ, Nat.Prime]
    <;>
    (try contradiction) <;>
    (try norm_num) <;>
    (try
      {
        simp_all [Finset.sum_Icc_succ_top, Nat.cast_add, Nat.cast_one, Nat.cast_sub, Nat.cast_zero]
        <;>
        ring_nf
        <;>
        norm_num
        <;>
        field_simp [Nat.cast_ne_zero]
        <;>
        norm_num
        <;>
        ring_nf
        <;>
        norm_num
        <;>
        omega
      }) <;>
    (try
      {
        rfl
      }) <;>
    (try
      {
        simp_all [Finset.sum_Icc_succ_top, Nat.cast_add, Nat.cast_one, Nat.cast_sub, Nat.cast_zero]
        <;>
        ring_nf
        <;>
        norm_num
        <;>
        field_simp [Nat.cast_ne_zero]
        <;>
        norm_num
        <;>
        ring_nf
        <;>
        norm_num
        <;>
        omega
      }) <;>
    (try
      {
        norm_num at *
        <;>
        omega
      }) <;>
    (try
      {
        simp_all [Finset.sum_Icc_succ_top, Nat.cast_add, Nat.cast_one, Nat.cast_sub, Nat.cast_zero]
        <;>
        ring_nf
        <;>
        norm_num
        <;>
        field_simp [Nat.cast_ne_zero]
        <;>
        norm_num
        <;>
        ring_nf
        <;>
        norm_num
        <;>
        omega
      })
    <;>
    (try
      {
        simp_all [Finset.sum_Icc_succ_top, Nat.cast_add, Nat.cast_one, Nat.cast_sub, Nat.cast_zero]
        <;>
        ring_nf
        <;>
        norm_num
        <;>
        field_simp [Nat.cast_ne_zero]
        <;>
        norm_num
        <;>
        ring_nf
        <;>
        norm_num
        <;>
        omega
      })
    <;>
    (try
      {
        norm_num at *
        <;>
        omega
      })
  exact h_main

#print axioms mathd_numbertheory_764
