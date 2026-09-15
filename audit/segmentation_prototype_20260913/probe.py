from pathlib import Path
import json,time
from onebigjump.lean import LeanREPL,discover
O=Path(__file__).parent
cases={
 'nested':"example (a b c : Nat) (h1 : a = b) (h2 : b = c) : a = c := by\n  have h : a = c := by\n    rw [h1]\n    exact h2\n  exact h",
 'branch':"example (P Q : Prop) (p : P) (q : Q) : P ∧ Q := by\n  constructor\n  · exact p\n  · exact q",
 'first':"example : True := by\n  first | exact False.elim (by assumption) | trivial",
 'failure':"example : True := by\n  have h : True := by\n    skip\n    exact bad_missing_name\n  exact h",
}
with LeanREPL(discover(),imports="import Mathlib\nimport Aesop",default_timeout_s=90) as repl:
 init=repl.command((O/'syntax_command.lean').read_text(encoding='utf-8'),timeout_s=90)
 (O/'probe-init.json').write_text(json.dumps(init,ensure_ascii=False,indent=2),encoding='utf-8')
 print('INIT',json.dumps(init,ensure_ascii=False),flush=True)
 for name,code in cases.items():
  ast=repl._exchange({'cmd':'#obj_ast '+json.dumps(code,ensure_ascii=False),'env':init.get('env')},timeout_s=90)
  reply=repl._exchange({'cmd':code,'env':repl._base_env,'infotree':'original','allTactics':True},timeout_s=90)
  (O/('probe-'+name+'.json')).write_text(json.dumps(dict(source=code,ast=ast,reply=reply),ensure_ascii=False,indent=2),encoding='utf-8')
  print('PROBE',name,'ast',str(ast)[:120],'tactics',len(reply.get('tactics',[])),'tree',len(reply.get('infotree',[])),flush=True)
