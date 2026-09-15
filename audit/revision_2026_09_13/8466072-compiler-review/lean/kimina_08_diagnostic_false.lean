import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators
open Real
open Nat
open Topology
example : (1 : Nat) = 2 := by
  native_decide
