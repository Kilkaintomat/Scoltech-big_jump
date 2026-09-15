from pathlib import Path
p = Path('/beegfs/home/denis.rakhmankin/onebigjump/lean_workspace/repl/REPL/Frontend.lean')
s = p.read_text()
old = 'let (env, messages) ← processHeader header opts messages inputCtx'
new = '\n'.join([
    old,
    '    for msg in messages.toList do',
    '      let message ← msg.data.toString',
    '      IO.eprintln ("HEADER DIAGNOSTIC: " ++ message)',
])
assert old in s
p.write_text(s.replace(old, new))
