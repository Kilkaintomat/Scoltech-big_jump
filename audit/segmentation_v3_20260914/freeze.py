from pathlib import Path
import hashlib,json,os,shutil,subprocess
from campaign_worker import read,atomic_json
from onebigjump.e1.artifacts import digest,environment
O=Path(__file__).parent;REPO=O.parents[1]
RUN=Path("/gpfs/gpfs0/denis.rakhmankin/onebigjump-runs/segmentation_20260914_v3")
gate=read(O/"quality-gate.json")
if not gate["passed"]:raise RuntimeError("quality gate not passed")
for f,h in gate["source"]["files"].items():
    if digest(Path(f))!=h:raise RuntimeError("code changed after passed quality gate")
if digest(O/"repl-observer")!=gate["source"]["observer_binary_sha256"]:raise RuntimeError("observer changed after test")
F=O/"frozen";F.mkdir(exist_ok=True)
names=["segmenter.py","segmenter_v2.py","segmenter_fast.py","syntax_command.lean","export_observations.py",
       "campaign_annotation.py","campaign_worker.py","prepare_inputs.py","gather.py","run_shard.sbatch","repl-observer"]
for name in names:
    src=O/name;dst=F/name
    if dst.exists():
        if digest(dst)!=digest(src):raise RuntimeError("immutable frozen source differs: "+name)
    else:shutil.copyfile(src,dst);dst.chmod(0o555 if name=="repl-observer" or name.endswith(".sbatch") else 0o444)
deps=REPO/"audit/revision_2026_09_13/snapshots/lean-io-v9"
files={str(p):digest(p) for p in F.iterdir() if p.is_file() and p.name!="repl-observer"}
files.update({str(p):digest(p) for p in (deps/"src/onebigjump").rglob("*.py")})
source={"files":files,"observer_binary_sha256":digest(F/"repl-observer"),
        "lean_sources":{str(p):digest(p) for p in (O/"repl/REPL").rglob("*.lean")},
        "quality_gate_sha256":digest(O/"quality-gate.json"),"runtime_base":"runs/repl_runtime_20260913_sealed",
        "git_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(),
        "dirty":bool(subprocess.check_output(["git","status","--porcelain"],cwd=REPO,text=True).strip()),
        "environment":environment()}
RUN.mkdir(parents=True,exist_ok=True)
atomic_json(RUN/"source-manifest.json",source)
config={"schema":"obj-segmentation-v3","models":["deepseek","goedel","kimina"],"n_shards_per_model":8,"n_tasks":24,
        "expected_attempts":20016,"concurrent_tasks":2,"observer_timeout_s":300,"replay_budget_s":300,
        "shard_wall_budget_s":72000,"slurm_cpus_per_task":8,"slurm_memory_gb":24,
        "source_dir":str(F),"generation":False,"model_forward":False,
        "scope":"new source segmentation, semantic annotations, original-token positions and summary; preserve original verdicts",
        "primary_statistical_tests":False,"created_by_job":os.environ["SLURM_JOB_ID"]}
atomic_json(RUN/"config.json",config)
alias=REPO/"runs/segmentation_20260914_v3"
if not alias.exists():alias.symlink_to(RUN,target_is_directory=True)
print("FROZEN",str(RUN),flush=True)
