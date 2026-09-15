"""Exercise E1 stage handoffs with explicitly synthetic, temporary data only."""
import os
import shutil
import tempfile
from pathlib import Path
import numpy as np
from onebigjump.e1.artifacts import Journal, digest, finish, identity, read_json, write_once, verify_manifest
from onebigjump.e1.generation import planned_requests
from onebigjump.e1.measurement import measure
from onebigjump.e1.analysis import analyze

original = Path("/beegfs/home/denis.rakhmankin/onebigjump/runs/e1_20260908T171727Z")
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
rng = np.random.default_rng(913)
for excluded in (False, True):
    with tempfile.TemporaryDirectory(prefix="e1-synthetic-fixture-") as temp:
        root = Path(temp)
        shutil.copytree(original / "inputs", root / "inputs")
        config = read_json(original / "pilot/protocol.json")
        config.update(layers=[0], primary_layer=0, temperatures=[0.6], model_id="SYNTHETIC-TEST-FIXTURE")
        config["statistics"].update(inner_bootstrap=10, permutations=9)
        write_once(root / "pilot/protocol.json", config)
        requests = planned_requests(root, "pilot", config)
        g = root / "pilot/generation/shard-000-of-001"
        v = root / "pilot/verification"
        e = root / "pilot/extraction"
        with Journal(g/"samples.jsonl", {"fixture":True}) as gen, Journal(v/"labels.jsonl", {"fixture":True}) as labels, Journal(e/"trajectories.jsonl", {"fixture":True}) as states:
            bundles=[]
            for i, r in enumerate(requests):
                row={k: value for k,value in r.items() if k!="problem"}
                row["completion_token_ids"]=[1]*12
                gen.append(row, identity(r))
                failed=r["role"]=="evaluation" and r["attempt_index"]==1
                category="parse_error" if excluded else ("localized_tactic_failure" if failed else "verified")
                tstar=4 if failed and not excluded else None
                steps=[] if excluded else [{"valid": not failed or t<4, "status": ("ok" if not failed or t<4 else ("error" if t==4 else "unreached"))} for t in range(12)]
                label={"trace_id":r["trace_id"],"category":category,"t_star":tstar,"steps":steps,"unexplained_disagreement":False}
                labels.append(label,identity(row))
                record={**row,"category":category,"task_family":"synthetic","extraction_status":"excluded_by_verification" if excluded else "extracted"}
                if not excluded:
                    path=e/(str(i)+".npz")
                    np.savez(path,states_0=rng.normal(size=(13,8)).cumsum(axis=0),surprisal=rng.exponential(size=12))
                    bundles.append(path)
                    record.update(states_path=str(path),states_sha256=digest(path))
                states.append(record,identity(label))
        gm=finish(g,stage="SYNTHETIC-TEST-generation",context={},inputs=[source],outputs=[g/"samples.jsonl",g/"samples.identity.json"],metrics={})
        vm=finish(v,stage="SYNTHETIC-TEST-verification",context={},inputs=[source,gm],outputs=[v/"labels.jsonl",v/"labels.identity.json"],metrics={})
        finish(e,stage="SYNTHETIC-TEST-extraction",context={},inputs=[source,vm],outputs=[e/"trajectories.jsonl",e/"trajectories.identity.json",*bundles],metrics={})
        measure(root,"pilot",source)
        analyze(root,"pilot",source)
        verify_manifest(root/"pilot/analysis/manifest.json")
        metrics=read_json(root/"pilot/analysis/metrics.json")
        assert metrics["planned_attempts"]==len(requests)
        assert metrics["scientific_decision"]=="inconclusive"
        assert all(cell["available"] != excluded for cell in metrics["cells"])
        assert all(cell["P1"]["verified"]["ci"] is None for cell in metrics["cells"])
        print("PIPELINE FIXTURE PASSED; all_excluded="+str(excluded),flush=True)
out=original/"checks"/("pipeline-fixture-"+os.environ["SLURM_JOB_ID"])
artifact=write_once(out/"result.json",{"passed":True,"synthetic_test_only":True,"scientific_result":False})
finish(out,stage="pipeline-software-test",context={},inputs=[source,Path(__file__)],outputs=[artifact],metrics={"passed":True})
