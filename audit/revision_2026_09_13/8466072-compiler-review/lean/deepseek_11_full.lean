import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem algebra_2rootspoly_apatapbeq2asqp2ab
  (a b : ℂ) :
  (a + a) * (a + b) = 2 * a^2 + 2 * (a * b) := by
  have h_main : (a + a) * (a + b) = 2 * a ^ 2 + 2 * (a * b) := by
    calc
      (a + a) * (a + b) = 2 * a * (a + b) := by
        ring_nf
        <;> simp [Complex.ext_iff, pow_two, mul_add, mul_comm, mul_left_comm, mul_assoc]
        <;> ring_nf
        <;> norm_num
        <;> aesop
      _ = 2 * a ^ 2 + 2 * (a * b) := by
        ring_nf
        <;> simp [Complex.ext_iff, pow_two, mul_add, mul_comm, mul_left_comm, mul_assoc]
        <;> ring_nf
        <;> norm_num
        <;> aesop
  exact h_main

#print axioms algebra_2rootspoly_apatapbeq2asqp2ab
