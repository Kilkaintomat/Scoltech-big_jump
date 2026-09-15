from pathlib import Path
import json,os
from onebigjump.lean import LeanREPL,discover
from segmenter_v2 import SegmenterV2
O=Path(__file__).parent
case={"name":"replay_source_with_goal_and_comment_corrected","header":"example (a c : ℝ) (h : 9 * (7 * a / 4) = 20 * c) : 63 * a = 80 * c := by","body":"\n  ring_nf at h ⊢\n  -- explanation\n  nlinarith\n"}
with LeanREPL(discover(),imports="import Mathlib\nimport Aesop",startup_attempts=1,default_timeout_s=60) as repl:
 s=SegmenterV2(repl);r=s.inspect(case["header"],case["body"]);s.replay_frontier(r)
checks={"whole_ok":r["whole_elaboration_ok"],"two_points":len(r["points"])==2,"both_source_replays_succeed":all(x["status"]=="ok" for x in r["context_replays"]),"exact_source_used":all(x["replay_source"]=="exact_AST_slice" for x in r["context_replays"])}
r["case"]=case;r["checks"]=checks;r["job"]=os.environ["SLURM_JOB_ID"]
(O/"corrected-fixture.json").write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(checks),flush=True)
if not all(checks.values()):raise RuntimeError("corrected fixture failed")
