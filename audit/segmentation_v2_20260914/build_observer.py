from pathlib import Path
import shutil,subprocess,json,os,hashlib
ROOT=Path('/beegfs/home/denis.rakhmankin/onebigjump')
OUT=ROOT/'audit/segmentation_v2_20260914'
PROJECT=OUT/'repl'
base=ROOT/'lean_workspace/repl'
PROJECT.mkdir(exist_ok=True)
shutil.copytree(base/'REPL',PROJECT/'REPL',dirs_exist_ok=True)
for name in ['lakefile.toml','lean-toolchain','lake-manifest.json']:
 if (base/name).exists():shutil.copyfile(base/name,PROJECT/name)
for name in ['Snapshots.lean','Frontend.lean']:
 shutil.copyfile(ROOT/'runs/repl_runtime_20260913_sealed'/name,PROJECT/'REPL'/name)
p=PROJECT/'REPL/Lean/InfoTree.lean';original=p.read_text(encoding='utf-8')
a=original.index('partial def findAllInfoTactics');b=original.index('/-- Return all',a)
replacement="""partial def findAllInfoTactics (t : InfoTree) (ctx? : Option ContextInfo) (rootGoals : List MVarId := []) :
  List (Info × Option ContextInfo × List MVarId) :=
  match t with
  | .context ctx t => t.findAllInfoTactics (ctx.mergeIntoOuter? ctx?) rootGoals
  | .node info ts =>
    -- Propagate roots through the outer tactic sequence, including non-substantive wrappers.
    -- Previously roots were shadowed only inside tInfo and children received the empty list.
    let roots := match info with
      | .ofTacticInfo i => if rootGoals.isEmpty then i.goalsBefore else rootGoals
      | _ => rootGoals
    let tInfo := match info with
      | .ofTacticInfo i => if info.isOriginal && i.isSubstantive then [(info, ctx?, roots)] else []
      | _ => []
    tInfo ++ ts.toList.flatMap (fun t => t.findAllInfoTactics ctx? roots)
  | _ => []

"""
p.write_text(original[:a]+replacement+original[b:],encoding='utf-8')
p=PROJECT/'REPL/Lean/InfoTree/ToJson.lean';s=p.read_text(encoding='utf-8')
s=s.replace('  goalsAfter : List String\n','''  goalsAfter : List String
  goalIdsBefore : List String
  goalIdsAfter : List String
  rootGoalsBefore : Lean.Json
  rootGoalsAfter : Lean.Json
''')
marker='-- Note: this is not responsible'
helper="""-- Root assignment summaries are observations in the original elaboration, not kernel certificates.
def rootGoalSummary (ctx : ContextInfo) (mctx : MetavarContext) (roots : List MVarId) : IO Lean.Json := do
  try
    ctx.runMetaM {} <| Meta.withMCtx mctx do
      let rows ← roots.mapM fun g => do
        let e ← instantiateMVars (mkMVar g)
        let pending ← Meta.getMVars e
        pure <| Lean.Json.mkObj [
          ("id", toJson g.name.toString),
          ("assigned", toJson (← g.isAssigned)),
          ("pendingIds", toJson (pending.toList.map fun m => m.name.toString)),
          ("containsSorry", toJson e.hasSorry),
          ("containsMVar", toJson e.hasMVar)]
      pure <| Lean.Json.arr rows.toArray
  catch _ => pure <| Lean.Json.mkObj [("unavailable", toJson true)]

"""
s=s.replace(marker,helper+marker)
s=s.replace('def TacticInfo.toJson (i : TacticInfo) (ctx : ContextInfo) : IO TacticInfo.Json','def TacticInfo.toJson (i : TacticInfo) (ctx : ContextInfo) (roots : List MVarId) : IO TacticInfo.Json')
s=s.replace('    goalsAfter := (← i.goalStateAfter ctx).map Format.pretty }','''    goalsAfter := (← i.goalStateAfter ctx).map Format.pretty
    goalIdsBefore := i.goalsBefore.map fun g => g.name.toString
    goalIdsAfter := i.goalsAfter.map fun g => g.name.toString
    rootGoalsBefore := ← rootGoalSummary ctx i.mctxBefore roots
    rootGoalsAfter := ← rootGoalSummary ctx i.mctxAfter roots }''')
s=s.replace('partial def InfoTree.toJson (t : InfoTree) (ctx? : Option ContextInfo) : IO Json','partial def InfoTree.toJson (t : InfoTree) (ctx? : Option ContextInfo) (rootGoals : List MVarId := []) : IO Json')
s=s.replace('| .context ctx t => t.toJson (ctx.mergeIntoOuter? ctx?)','| .context ctx t => t.toJson (ctx.mergeIntoOuter? ctx?) rootGoals')
s=s.replace('    if let some ctx := ctx? then\n      let node', '''    let roots := match info with
      | .ofTacticInfo i => if rootGoals.isEmpty then i.goalsBefore else rootGoals
      | _ => rootGoals
    if let some ctx := ctx? then
      let node''')
s=s.replace('| .ofTacticInfo  info => some <$> (do pure <| Lean.toJson (← info.toJson ctx))','| .ofTacticInfo  info => some <$> (do pure <| Lean.toJson (← info.toJson ctx roots))')
s=s.replace("fun t' => t'.toJson ctx", "fun t' => t'.toJson ctx roots")
p.write_text(s,encoding='utf-8')
# A locally discharged child need not close the theorem; keep this status distinct from rejection.
p=PROJECT/'REPL/Main.lean';s=p.read_text(encoding='utf-8')
s=s.replace('| none => return "Error: Goal not assigned"','| none => return "Incomplete: root goal not assigned"')
s=s.replace('if pf.hasExprMVar then\n              return "Incomplete: contains metavariable(s)"','if pf.hasMVar || pft.hasMVar then\n              return "Incomplete: contains metavariable(s)"')
p.write_text(s,encoding='utf-8')
subprocess.run(['lake','build','repl'],cwd=PROJECT,check=True)
shutil.copyfile(PROJECT/'.lake/build/bin/repl',OUT/'repl-observer')
(OUT/'repl-observer').chmod(0o555)
manifest={'job':os.environ['SLURM_JOB_ID'],'base':'runs/repl_runtime_20260913_sealed','purpose':'isolated observer and root-propagation repair; not production verifier','files':{}}
for p in [*PROJECT.rglob('*.lean'),OUT/'repl-observer',Path(__file__)]:
 if '.lake' not in p.parts:manifest['files'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(OUT/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('OBSERVER_BUILT',flush=True)
