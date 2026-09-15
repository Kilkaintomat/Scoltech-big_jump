/-
Copyright (c) 2023 Kim Morrison. All Rights Reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Kim Morrison
-/
import REPL.Lean.InfoTree
import REPL.Lean.ContextInfo

/-!
# Exporting an `InfoTree` as Json

-/

namespace Lean.Elab

structure InfoTreeNode (α : Type) where
  kind : String
  node : Option α
  children : List Json
deriving ToJson

deriving instance ToJson for Lean.Position

structure Syntax.Range where
  synthetic : Bool
  start : Lean.Position
  finish : Lean.Position
deriving ToJson

structure Syntax.Json where
  pp : Option String
  -- raw : String
  range : Range
  kind: String
  argKinds: Array String
deriving ToJson

def _root_.Lean.Syntax.argKinds (stx : Syntax) : Array String :=
  stx.getArgs.map fun s => s.getKind.toString

def _root_.Lean.Syntax.toRange (stx : Syntax) (ctx : ContextInfo) : Syntax.Range :=
  let pos    := stx.getPos?.getD 0
  let endPos := stx.getTailPos?.getD pos
  { start := ctx.fileMap.toPosition pos
    finish := ctx.fileMap.toPosition endPos
    synthetic := match stx.getHeadInfo with
    | .original .. => false
    | _ => true }

def _root_.Lean.Syntax.toJson (stx : Syntax) (ctx : ContextInfo) (lctx : LocalContext) : IO Syntax.Json := do
  return {
    pp := match (← ctx.ppSyntax lctx stx).pretty with
      | "failed to pretty print term (use 'set_option pp.rawOnError true' for raw representation)" => none
      | pp => some pp
    -- raw := toString stx
    kind := stx.getKind.toString
    argKinds := stx.argKinds
    range := stx.toRange ctx }

structure TacticInfo.Json where
  name : Option Name
  stx : Syntax.Json
  goalsBefore : List String
  goalsAfter : List String
  goalIdsBefore : List String
  goalIdsAfter : List String
  rootGoalsBefore : Lean.Json
  rootGoalsAfter : Lean.Json
deriving ToJson

-- Root assignment summaries are observations in the original elaboration, not kernel certificates.
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

-- Note: this is not responsible for converting the children to Json.
def TacticInfo.toJson (i : TacticInfo) (ctx : ContextInfo) (roots : List MVarId) : IO TacticInfo.Json := do
  return {
    name := i.name?
    stx :=
    { pp := Format.pretty (← i.pp ctx),
      -- raw := toString i.info.stx,
      kind := i.stx.getKind.toString,
      argKinds := i.stx.argKinds,
      range := i.stx.toRange ctx },
    goalsBefore := (← i.goalState ctx).map Format.pretty,
    goalsAfter := (← i.goalStateAfter ctx).map Format.pretty
    goalIdsBefore := i.goalsBefore.map fun g => g.name.toString
    goalIdsAfter := i.goalsAfter.map fun g => g.name.toString
    rootGoalsBefore := ← rootGoalSummary ctx i.mctxBefore roots
    rootGoalsAfter := ← rootGoalSummary ctx i.mctxAfter roots }

structure CommandInfo.Json where
  elaborator : Option Name
  stx : Syntax.Json
deriving ToJson

def CommandInfo.toJson (info : CommandInfo) (ctx : ContextInfo) : IO CommandInfo.Json := do
  return {
    elaborator := match info.elaborator with | .anonymous => none | n => some n,
    stx := ← info.stx.toJson ctx {} }

structure TermInfo.Json where
  elaborator : Option Name
  stx : Syntax.Json
  expectedType? : Option String
  expr : String
  isBinder : Bool
deriving ToJson

def TermInfo.toJson (info : TermInfo) (ctx : ContextInfo) : IO TermInfo.Json := do
  return {
    elaborator := match info.elaborator with | .anonymous => none | n => some n,
    stx := ← info.stx.toJson ctx info.lctx,
    expectedType? := ← info.expectedType?.mapM fun ty => do
      pure (← ctx.ppExpr info.lctx ty).pretty
    expr := (← ctx.ppExpr info.lctx info.expr).pretty
    isBinder := info.isBinder }

structure InfoTree.HoleJson where
  goalState : String
deriving ToJson

partial def InfoTree.toJson (t : InfoTree) (ctx? : Option ContextInfo) (rootGoals : List MVarId := []) : IO Json := do
  match t with
  | .context ctx t => t.toJson (ctx.mergeIntoOuter? ctx?) rootGoals
  | .node info children =>
    let roots := match info with
      | .ofTacticInfo i => if rootGoals.isEmpty then i.goalsBefore else rootGoals
      | _ => rootGoals
    if let some ctx := ctx? then
      let node : Option Json ← match info with
      | .ofTermInfo    info => some <$> (do pure <| Lean.toJson (← info.toJson ctx))
      | .ofCommandInfo info => some <$> (do pure <| Lean.toJson (← info.toJson ctx))
      | .ofTacticInfo  info => some <$> (do pure <| Lean.toJson (← info.toJson ctx roots))
      | _                   => pure none
      return Lean.toJson (InfoTreeNode.mk info.kind node (← children.toList.mapM fun t' => t'.toJson ctx roots))
    else throw <| IO.userError "No `ContextInfo` available."
  | .hole mvarId =>
    if let some ctx := ctx? then
     return Lean.toJson (InfoTree.HoleJson.mk (← ctx.runMetaM {} (do Meta.ppGoal mvarId)).pretty)
    else throw <| IO.userError "No `ContextInfo` available."

end Lean.Elab
