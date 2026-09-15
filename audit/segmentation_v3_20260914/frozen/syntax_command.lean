open Lean Elab Command
partial def objSyntax (stx : Syntax) : Json :=
  Json.mkObj [
    ("kind", toJson stx.getKind.toString),
    ("start", toJson (stx.getPos?.map (fun p => p.byteIdx))),
    ("end", toJson (stx.getTailPos?.map (fun p => p.byteIdx))),
    ("original", toJson (match stx.getHeadInfo with | .original .. => true | _ => false)),
    ("args", Json.arr (stx.getArgs.map objSyntax))]
elab "#obj_ast " s:str : command => do
  match Parser.runParserCategory (← getEnv) `term s.getString with
  | .ok stx => logInfo ("OBJAST:" ++ (objSyntax stx).compress)
  | .error err => logInfo ("OBJAST_ERROR:" ++ err)
