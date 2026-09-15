from pathlib import Path
import os,time,json,collections
from onebigjump.e1 import artifacts as a
BASE=Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE=BASE/"audit/revision_2026_09_13/speedup-v2"
SOURCE=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
TARGET=BASE/"runs/lean_reverification_20260913_local/goedel/main/verification/shard-000-of-008/manifest.json"
inputs=[Path(p) for p in a.read_json(TARGET)["inputs"] if p.endswith("manifest.json")]
original=a.digest
measurements=[]
for method in ("separate_sets","shared_set"):
    counters={"calls":0,"bytes":0};paths=collections.Counter()
    def counted(path):
        counters["calls"]+=1;counters["bytes"]+=Path(path).stat().st_size
        paths[str(Path(path).resolve())]+=1
        return original(path)
    a.digest=counted;started=time.monotonic();seen=set()
    try:
        for p in inputs:
            a.verify_manifest(p,None if method=="separate_sets" else seen)
    finally:
        elapsed=time.monotonic()-started;a.digest=original
    measurements.append({"method":method,"seconds":elapsed,**counters,"unique_paths":len(paths),"root_count":len(inputs)})
    print("MEASURED",measurements[-1],flush=True)
metrics={"measurements":measurements,"speedup":measurements[0]["seconds"]/measurements[1]["seconds"],
         "read_reduction":measurements[0]["bytes"]/measurements[1]["bytes"],
         "same_unique_file_population":measurements[0]["unique_paths"]==measurements[1]["unique_paths"],
         "scope":"one integrity-DAG benchmark; baseline ran first, cache warming can affect timing; no claim of equal whole-pipeline acceleration",
         "persistent_digest_cache":False,"all_digests_checked":True}
assert metrics["same_unique_file_population"]
out=HERE/"io-benchmark"
m=a.write_once(out/"metrics.json",metrics)
a.finish(out,stage="manifest-shared-dag-benchmark",context={"source":a.digest(SOURCE)},inputs=[SOURCE,Path(__file__),TARGET],outputs=[m],metrics=metrics)
print("IO_BENCHMARK_COMPLETE",json.dumps(metrics),flush=True)
