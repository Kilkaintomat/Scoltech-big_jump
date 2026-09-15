set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
theorem amc12a_2020_p7
  (a : ℕ → ℕ)
  (h₀ : (a 0)^3 = 1)
  (h₁ : (a 1)^3 = 8)
  (h₂ : (a 2)^3 = 27)
  (h₃ : (a 3)^3 = 64)
  (h₄ : (a 4)^3 = 125)
  (h₅ : (a 5)^3 = 216)
  (h₆ : (a 6)^3 = 343) :
  ∑ k ∈ Finset.range 7, (6 * (a k)^2) - ↑(2 * ∑ k ∈ Finset.range 6, (a k)^2) = 658 := by
  have h_a0 : a 0 = 1 := by
    have h₇ : a 0 = 1 := by
      have h₇₁ : (a 0)^3 = 1 := h₀
      have h₇₂ : a 0 ≤ 1 := by
        by_contra h
        have : a 0 ≥ 2 := by omega
        have : (a 0)^3 ≥ 2^3 := by
          have : a 0 ≥ 2 := by omega
          have : (a 0)^3 ≥ 2^3 := by
            calc
              (a 0)^3 ≥ 2^3 := by
                exact Nat.pow_le_pow_left (by omega) 3
              _ = 2^3 := by rfl
          exact this
        nlinarith
      have h₇₃ : a 0 ≥ 1 := by
        by_contra h
        have : a 0 = 0 := by omega
        rw [this] at h₇₁
        norm_num at h₇₁
      interval_cases a 0 <;> norm_num at h₇₁ ⊢ <;> omega
    exact h₇
  
  have h_a1 : a 1 = 2 := by
    have h₇ : a 1 = 2 := by
      have h₇₁ : (a 1)^3 = 8 := h₁
      have h₇₂ : a 1 ≤ 2 := by
        by_contra h
        have : a 1 ≥ 3 := by omega
        have : (a 1)^3 ≥ 3^3 := by
          have : a 1 ≥ 3 := by omega
          have : (a 1)^3 ≥ 3^3 := by
            calc
              (a 1)^3 ≥ 3^3 := by
                exact Nat.pow_le_pow_left (by omega) 3
              _ = 3^3 := by rfl
          exact this
        nlinarith
      have h₇₃ : a 1 ≥ 1 := by
        by_contra h
        have : a 1 = 0 := by omega
        rw [this] at h₇₁
        norm_num at h₇₁
      interval_cases a 1 <;> norm_num at h₇₁ ⊢ <;> omega
    exact h₇
  
  have h_a2 : a 2 = 3 := by
    have h₇ : a 2 = 3 := by
      have h₇₁ : (a 2)^3 = 27 := h₂
      have h₇₂ : a 2 ≤ 3 := by
        by_contra h
        have : a 2 ≥ 4 := by omega
        have : (a 2)^3 ≥ 4^3 := by
          have : a 2 ≥ 4 := by omega
          have : (a 2)^3 ≥ 4^3 := by
            calc
              (a 2)^3 ≥ 4^3 := by
                exact Nat.pow_le_pow_left (by omega) 3
              _ = 4^3 := by rfl
          exact this
        nlinarith
      have h₇₃ : a 2 ≥ 1 := by
        by_contra h
        have : a 2 = 0 := by omega
        rw [this] at h₇₁
        norm_num at h₇₁
      interval_cases a 2 <;> norm_num at h₇₁ ⊢ <;> omega
    exact h₇
  
  have h_a3 : a 3 = 4 := by
    have h₇ : a 3 = 4 := by
      have h₇₁ : (a 3)^3 = 64 := h₃
      have h₇₂ : a 3 ≤ 4 := by
        by_contra h
        have : a 3 ≥ 5 := by omega
        have : (a 3)^3 ≥ 5^3 := by
          have : a 3 ≥ 5 := by omega
          have : (a 3)^3 ≥ 5^3 := by
            calc
              (a 3)^3 ≥ 5^3 := by
                exact Nat.pow_le_pow_left (by omega) 3
              _ = 5^3 := by rfl
          exact this
        nlinarith
      have h₇₃ : a 3 ≥ 1 := by
        by_contra h
        have : a 3 = 0 := by omega
        rw [this] at h₇₁
        norm_num at h₇₁
      interval_cases a 3 <;> norm_num at h₇₁ ⊢ <;> omega
    exact h₇
  
  have h_a4 : a 4 = 5 := by
    have h₇ : a 4 = 5 := by
      have h₇₁ : (a 4)^3 = 125 := h₄
      have h₇₂ : a 4 ≤ 5 := by
        by_contra h
        have : a 4 ≥ 6 := by omega
        have : (a 4)^3 ≥ 6^3 := by
          have : a 4 ≥ 6 := by omega
          have : (a 4)^3 ≥ 6^3 := by
            calc
              (a 4)^3 ≥ 6^3 := by
                exact Nat.pow_le_pow_left (by omega) 3
              _ = 6^3 := by rfl
          exact this
        nlinarith
      have h₇₃ : a 4 ≥ 1 := by
        by_contra h
        have : a 4 = 0 := by omega
        rw [this] at h₇₁
        norm_num at h₇₁
      interval_cases a 4 <;> norm_num at h₇₁ ⊢ <;> omega
    exact h₇
  
  have h_a5 : a 5 = 6 := by
    have h₇ : a 5 = 6 := by
      have h₇₁ : (a 5)^3 = 216 := h₅
      have h₇₂ : a 5 ≤ 6 := by
        by_contra h
        have : a 5 ≥ 7 := by omega
        have : (a 5)^3 ≥ 7^3 := by
          have : a 5 ≥ 7 := by omega
          have : (a 5)^3 ≥ 7^3 := by
            calc
              (a 5)^3 ≥ 7^3 := by
                exact Nat.pow_le_pow_left (by omega) 3
              _ = 7^3 := by rfl
          exact this
        nlinarith
      have h₇₃ : a 5 ≥ 1 := by
        by_contra h
        have : a 5 = 0 := by omega
        rw [this] at h₇₁
        norm_num at h₇₁
      interval_cases a 5 <;> norm_num at h₇₁ ⊢ <;> omega
    exact h₇
  
  have h_a6 : a 6 = 7 := by
    have h₇ : a 6 = 7 := by
      have h₇₁ : (a 6)^3 = 343 := h₆
      have h₇₂ : a 6 ≤ 7 := by
        by_contra h
        have : a 6 ≥ 8 := by omega
        have : (a 6)^3 ≥ 8^3 := by
          have : a 6 ≥ 8 := by omega
          have : (a 6)^3 ≥ 8^3 := by
            calc
              (a 6)^3 ≥ 8^3 := by
                exact Nat.pow_le_pow_left (by omega) 3
              _ = 8^3 := by rfl
          exact this
        nlinarith
      have h₇₃ : a 6 ≥ 1 := by
        by_contra h
        have : a 6 = 0 := by omega
        rw [this] at h₇₁
        norm_num at h₇₁
      interval_cases a 6 <;> norm_num at h₇₁ ⊢ <;> omega
    exact h₇
  
  have h_sum_main : ∑ k ∈ Finset.range 7, (6 * (a k)^2) - ↑(2 * ∑ k ∈ Finset.range 6, (a k)^2) = 658 := by
    simp [Finset.sum_range_succ, h_a0, h_a1, h_a2, h_a3, h_a4, h_a5, h_a6, Nat.mul_sub_left_distrib, Nat.mul_sub_right_distrib]
    <;> norm_num
    <;> rfl
    <;> rfl
  
  exact h_sum_main

#print axioms amc12a_2020_p7
