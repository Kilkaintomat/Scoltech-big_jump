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
  have h_main : (a + a) * (a + b) = 2 * a^2 + 2 * (a * b) := by
    ring_nf
    <;>
    simp [mul_add, add_mul, mul_comm, mul_left_comm, mul_assoc, pow_two, Complex.ext_iff, Complex.mul_re, Complex.mul_im, Complex.add_re, Complex.add_im]
    <;>
    norm_num
    <;>
    ring_nf
    <;>
    simp_all [Complex.ext_iff, pow_two, mul_add, add_mul, mul_comm, mul_left_comm, mul_assoc]
    <;>
    norm_num
    <;>
    ring_nf
    <;>
    simp_all [Complex.ext_iff, pow_two, mul_add, add_mul, mul_comm, mul_left_comm, mul_assoc]
    <;>
    norm_num
    <;>
    linarith
  exact h_main

#print axioms algebra_2rootspoly_apatapbeq2asqp2ab
