import argparse
from stage_support import *
from artifact_bridge import finish_artifact
from onebigjump.e1.artifacts import identity
def main():
 p=argparse.ArgumentParser();p.add_argument("model");args=p.parse_args();start("portable_runtime");model=args.model;folder=OUT/"audit_cli"/model
 selection=OUT/"lean_audit"/(model+"-selected.json");selected=read(selection);context=read(folder/"results.identity.json")
 with (folder/"results.jsonl").open(encoding="utf-8") as f:rows=[json.loads(line) for line in f]
 assert {r["trace_id"] for r in rows}=={r["item"]["trace_id"] for r in selected}
 for r in rows:
  payload={k:v for k,v in r.items() if k!="row_sha256"};assert identity(payload)==r["row_sha256"]
  for stem in ["source","detail"]:
   if r.get(stem+"_path"):assert digest(r[stem+"_path"])==r[stem+"_sha256"]
 metrics=read(folder/"metrics.json");assert metrics["completed"]==len(rows)
 if (folder/"manifest.json").exists():check_manifest(folder/"manifest.json");return
 finish_artifact(folder,stage="stratified-independent-Lean-CLI-audit",context={"original_journal_context":context,"original_slurm_array":"8467348","finalization_only":True},
  inputs=[selection,OUT/"lean_audit"/model/"manifest.json",HERE/"audit_cli-source-manifest.json",HERE/"portable_runtime-source-manifest.json"],
  outputs=[folder/"metrics.json",folder/"results.jsonl",folder/"results.identity.json",*[Path(r["detail_path"]) for r in rows],*[Path(r["source_path"]) for r in rows if r.get("source_path")]],metrics=metrics)
 print("CLI AUDIT CERTIFICATE FINALIZED",model,flush=True)
if __name__=="__main__":main()
