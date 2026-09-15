"""Build the pinned REPL while restoring scoped activations without answer constants."""

import os
import shutil
import subprocess
from pathlib import Path

from onebigjump.e1.artifacts import digest, finish, write_once

base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
project = base / "lean_workspace/repl"
previous = base / "runs/repl_runtime_20260912_sealed"
folder = base / "runs/repl_runtime_20260913_scopes"
folder.mkdir(parents=True, exist_ok=False)
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
text = (previous / "Snapshots.lean").read_text(encoding="utf-8")
old = """    let s := match env? with
    | none => s
    | some env => { s with env }"""
new = """    let s ← match env? with
    | none => pure s
    | some env => do
      -- Keep the pre-command constants: the theorem being proved must remain unavailable.
      -- Restore only scoped activations, including `open scoped` (not in openDecls).
      -- Each extension is activated from its own ContextInfo scope to avoid importing
      -- completed declarations, simp lemmas, or future command state.
      let mut replayEnv := env
      for ext in ← scopedEnvExtensionsRef.get do
        let captured := ext.ext.getState (asyncMode := .local) ctx.env
        if let scope :: _ := captured.stateStack then
          for ns in scope.activeScopes.toList do
            replayEnv := ext.activateScoped replayEnv ns
      pure { s with env := replayEnv }"""
assert text.count(old) == 1
(project / "REPL/Snapshots.lean").write_text(text.replace(old, new), encoding="utf-8")
shutil.copy2(previous / "Frontend.lean", project / "REPL/Frontend.lean")
for name in ["Snapshots.lean", "Frontend.lean"]:
    shutil.copy2(project / "REPL" / name, folder / name)
config = {
    "repair": "restore each scoped extension's active namespaces from ContextInfo; keep pre-command constants",
    "base_runtime_sha256": digest(previous / "manifest.json"),
    "base_repl_revision": "5d5c49d13dfc0c1d2df43a27c3e56e02ad81b9c3",
    "lean_version": subprocess.check_output(["lean", "--version"], cwd=project, text=True).strip(),
    "build_command": ["lake", "build", "repl"],
    "slurm_job_id": os.environ["SLURM_JOB_ID"],
}
config_path = write_once(folder / "config.json", config)
subprocess.run(["lake", "build", "repl"], cwd=project, check=True)
shutil.copy2(project / ".lake/build/bin/repl", folder / "repl")
(folder / "repl").chmod(0o555)
finish(
    folder,
    stage="lean-scoped-runtime-build",
    context={"source": digest(source)},
    inputs=[source, Path(__file__), previous / "manifest.json"],
    outputs=[folder / "repl", folder / "Snapshots.lean", folder / "Frontend.lean", config_path],
    metrics=config,
)
print("SCOPED_RUNTIME_BUILT", folder, flush=True)
