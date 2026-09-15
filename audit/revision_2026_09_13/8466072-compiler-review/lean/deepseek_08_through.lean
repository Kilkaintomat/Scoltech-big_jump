import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem amc12a_2003_p25
  (a b : ℝ)
  (f : ℝ → ℝ)
  (h₀ : 0 < b)
  (h₁ : ∀ x, f x = Real.sqrt (a * x^2 + b * x))
  (h₂ : {x | 0 ≤ f x} = f '' {x | 0 ≤ f x}) :
  a = 0 ∨ a = -4 := by
  have h_main : a = 0 ∨ a = -4 := by
    have h₃ := Set.ext_iff.1 h₂ 0
    have h₄ := Set.ext_iff.1 h₂ (-1)
    have h₅ := Set.ext_iff.1 h₂ 1
    have h₆ := Set.ext_iff.1 h₂ (b)
    have h₇ := Set.ext_iff.1 h₂ (-b)
    have h₈ := Set.ext_iff.1 h₂ (2)
    have h₉ := Set.ext_iff.1 h₂ (-2)
    have h₁₀ := Set.ext_iff.1 h₂ (b / 2)
    have h₁₁ := Set.ext_iff.1 h₂ (-b / 2)
    have h₁₂ := Set.ext_iff.1 h₂ (4)
    have h₁₃ := Set.ext_iff.1 h₂ (-4)
    norm_num [h₁, h₀, Real.sqrt_eq_zero_of_nonpos, le_of_lt, Set.mem_setOf_eq, Set.mem_image,
      Real.sqrt_nonneg, Real.sqrt_nonneg] at *
    <;>
    (try {
      nlinarith
    }) <;>
    (try {
      left
      nlinarith [sq_sqrt (show (0 : ℝ) ≤ b by linarith), Real.sqrt_nonneg b]
    }) <;>
    (try {
      right
      nlinarith [sq_sqrt (show (0 : ℝ) ≤ b by linarith), Real.sqrt_nonneg b]
    }) <;>
    (try {
      cases' le_total 0 (a * 2 + b) with h h <;>
      cases' le_total 0 (a * (-2 : ℝ) + b) with h₁ h₁ <;>
      simp_all [Real.sqrt_eq_zero_of_nonpos, le_of_lt, sq, mul_neg, mul_one, mul_add,
        mul_sub, sub_mul, sub_neg_eq_add, add_assoc] <;>
      nlinarith [Real.sqrt_nonneg (a * (2 : ℝ) ^ 2 + b * 2),
        Real.sqrt_nonneg (a * (-2 : ℝ) ^ 2 + b * (-2 : ℝ)),
        Real.sqrt_nonneg (a * (4 : ℝ) ^ 2 + b * 4),
        Real.sqrt_nonneg (a * (-4 : ℝ) ^ 2 + b * (-4 : ℝ)),
        Real.sqrt_nonneg (a * (b / 2 : ℝ) ^ 2 + b * (b / 2 : ℝ)),
        Real.sqrt_nonneg (a * (-b / 2 : ℝ) ^ 2 + b * (-b / 2 : ℝ)),
        Real.sq_sqrt (show 0 ≤ (a * (2 : ℝ) ^ 2 + b * 2) by nlinarith),
        Real.sq_sqrt (show 0 ≤ (a * (-2 : ℝ) ^ 2 + b * (-2 : ℝ)) by nlinarith),
        Real.sq_sqrt (show 0 ≤ (a * (4 : ℝ) ^ 2 + b * 4) by nlinarith),
        Real.sq_sqrt (show 0 ≤ (a * (-4 : ℝ) ^ 2 + b * (-4 : ℝ)) by nlinarith),
        Real.sq_sqrt (show 0 ≤ (a * (b / 2 : ℝ) ^ 2 + b * (b / 2 : ℝ)) by nlinarith),
        Real.sq_sqrt (show 0 ≤ (a * (-b / 2 : ℝ) ^ 2 + b * (-b / 2 : ℝ)) by nlinarith)]
    }) <;>
    (try {
      nlinarith [sq_nonneg (a + 4), sq_nonneg (a - 4), sq_nonneg (b - 8),
        Real.sqrt_nonneg (a * (2 : ℝ) ^ 2 + b * 2),
        Real.sqrt_nonneg (a * (-2 : ℝ) ^ 2 + b * (-2 : ℝ)),
        Real.sqrt_nonneg (a * (4 : ℝ) ^ 2 + b * 4),
        Real.sqrt_nonneg (a * (-4 : ℝ) ^ 2 + b * (-4 : ℝ)),
        Real.sqrt_nonneg (a * (b / 2 : ℝ) ^ 2 + b * (b / 2 : ℝ)),
        Real.sqrt_nonneg (a * (-b / 2 : ℝ) ^ 2 + b * (-b / 2 : ℝ))]
    }) <;>
    (try {
      cases' le_total 0 (a + 4) with h h <;>
      cases' le_total 0 (a - 4) with h₁ h₁ <;>
      simp_all [Set.ext_iff, Real.sqrt_eq_zero_of_nonpos, le_of_lt] <;>
      norm_num <;>
      (try {
        nlinarith [sq_sqrt (show (0 : ℝ) ≤ b by linarith), Real.sqrt_nonneg b]
      }) <;>
      (try {
        ring_nf at * <;>
        nlinarith [sq_sqrt (show (0 : ℝ) ≤ b by linarith), Real.sqrt_nonneg b]
      })
    })
    <;>
    (try {
      aesop
    })
    <;>
    (try {
      nlinarith
    })
    <;>
    (try {
      nlinarith [Real.sqrt_nonneg (a * (2 : ℝ) ^ 2 + b * 2),
        Real.sqrt_nonneg (a * (-2 : ℝ) ^ 2 + b * (-2 : ℝ)),
        Real.sqrt_nonneg (a * (4 : ℝ) ^ 2 + b * 4),
        Real.sqrt_nonneg (a * (-4 : ℝ) ^ 2 + b * (-4 : ℝ)),
        Real.sqrt_nonneg (a * (b / 2 : ℝ) ^ 2 + b * (b / 2 : ℝ)),
        Real.sqrt_nonneg (a * (-b / 2 : ℝ) ^ 2 + b * (-b / 2 : ℝ))]
    })
    <;>
    (try {
      aesop
    })
    <;>
    (try {
      nlinarith [sq_nonneg (a + 4), sq_nonneg (a - 4), sq_nonneg (b - 8)]
    })
    <;>
    (try {
      aesop
    })
    <;>
    (try {
      nlinarith
    })
    <;>
    (try {
      aesop
    })
    <;>
    (try {
      nlinarith [sq_nonneg (a + 4), sq_nonneg (a - 4), sq_nonneg (b - 8)]
    })
    <;>
    (try {
      aesop
    })
  all_goals sorry
