"""Cheap supplementary main analysis, launched only after complete measurement."""
from pathlib import Path
import argparse,os,time
import numpy as np
import pandas as pd
from onebigjump.e1.artifacts import read_json,write_once,finish,digest,verify_manifest
from onebigjump.e1.campaign import require_collection_gate
from onebigjump.readiness.finite_sample import localization_effects,threshold_rates

parser=argparse.ArgumentParser()
parser.add_argument("output",type=Path)
parser.add_argument("root",type=Path)
parser.add_argument("--phase",choices=["pilot","main"],default="main")
a=parser.parse_args()
source=Path(os.environ["E1_SNAPSHOT"])/"source-manifest.json"
config_path=a.root/a.phase/"protocol.json"
config=read_json(config_path)
measurement=a.root/a.phase/"measurement/manifest.json"
verify_manifest(measurement)
inputs=[source,config_path,measurement,Path(__file__)]
if a.phase=="main":
    # The collection protocol/source remain the original ones; the new source is an analysis amendment.
    gate=a.root/"main/collection-gate/manifest.json"
    verify_manifest(gate)
    previous=[Path(p) for p in read_json(gate)["inputs"] if p.endswith("source-manifest.json")]
    assert len(previous)==1
    require_collection_gate(a.root,previous[0])
    inputs.append(gate)
table=pd.read_parquet(measurement.parent/"deviations.parquet",
    filters=[("temperature","==",config["primary_temperature"]),("layer","==",config["primary_layer"])])
table=table[table.primary_eligible]
assert not set(table.loc[table.role=="calibration","prompt_id"]) & set(table.loc[table.role=="evaluation","prompt_id"])
started=time.monotonic()
cells={}
for statistic in ["raw","whitened","innovation"]:
    cell=table[table.statistic==statistic]
    cal=cell[(cell.role=="calibration") & (cell.outcome=="verified")]
    evaluation=cell[cell.role=="evaluation"]
    tau=float(np.quantile(cal.z,.99)) if len(cal) else None
    cells[statistic]={
        "P2":localization_effects(evaluation),
        "P2_drop_first":localization_effects(evaluation,True),
        "finite_threshold":threshold_rates(evaluation,tau) if tau is not None else None,
        "threshold_tasks":int(cal.prompt_id.nunique()),"threshold_steps":len(cal),
        "tau":tau,"transform_threshold_reuse":statistic!="raw"}
result={"phase":a.phase,"model_id":config["model_id"],"cells":cells,"primary_unchanged":True,
    "scope":"post-pilot supplementary task-mean analysis; conditional on fixed transforms",
    "disjoint_whitening":"separate existing control campaign; this runner does not refit transforms",
    "analysis_seconds":time.monotonic()-started}
if a.phase=="pilot":
    previous=read_json(Path(__file__).parent/"analysis/metrics.json")
    expected=previous["models"][a.root.name]["cells"]
    assert all(cells[key]==expected[key] for key in cells)
    result["pilot_integration_equal"]=True
metrics=write_once(a.output/"metrics.json",result)
finish(a.output,stage="finite-task-supplementary-sidecar",context={"source":digest(source)},
    inputs=inputs,outputs=[metrics],metrics={"cells":len(cells),"phase":a.phase,"primary_unchanged":True})
print("SIDECAR_COMPLETE",a.root.name,a.phase,flush=True)
