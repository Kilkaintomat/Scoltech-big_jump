import Mathlib
import Aesop
#check Mathlib.Meta.NormNum.Result
example : True := by trivial
set_option maxHeartbeats 400000
example : True := by
  run_tac do
    let budget := (← getOptions).getNat `maxHeartbeats 0
    unless budget == 400000 do throwError "wrong heartbeat budget {budget}"
  trivial
