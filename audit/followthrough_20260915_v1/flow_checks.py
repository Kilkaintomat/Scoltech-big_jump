import ast,importlib.util
from stage_support import *
from artifact_bridge import verify_any
from flow import status_of
from p5_analyze import rate_compare
start("flow")
assert status_of({},[],{}, {})["state"]=="NOT_SUBMITTED"
assert status_of({},[{"id":"1"}],{"1":["1","PENDING","0","4h","Priority","x","ais-gpu"]},{})["state"]=="ACTIVE"
assert status_of({},[{"id":"1"}],{},{"1":["1","COMPLETED","0:0","1h","a","b"]})["state"]=="COMPLETED"
assert status_of({"indices":[0,1]},[{"id":"2","indices":[0,1]},{"id":"3","indices":[1]}],{},{"2_0":["2_0","COMPLETED"],"2_1":["2_1","TIMEOUT"],"3_1":["3_1","COMPLETED"]})["state"]=="COMPLETED"
for value in [False,True]:
 cal=[{"length":L,"verified":value} for L in [3,4,5] for i in range(3)]
 ev=[{"length":L,"verified":value} for L in [3,4,5] for i in range(2)]
 result=rate_compare(cal,ev,10,333)
 assert result["brier_improvement"]==0 and result["brier_improvement_ci975"]==[0.,0.]
for path in HERE.glob("*.py"):ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
verify_any(OUT/"lean_audit/deepseek/manifest.json")
atomic(OUT/"flow/checks.json",{"passed":True,"checks":["resume array accounting","no-action pending/completed classification","P5 all-success and all-failure boundaries","Python syntax of every stage","recursive mixed-schema artifact verification"],"environment":environment()})
print("FOLLOWTHROUGH INTEGRATION CHECKS PASSED",flush=True)
