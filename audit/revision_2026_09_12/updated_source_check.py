import hashlib
import json
import os
from pathlib import Path
root=Path('/beegfs/home/denis.rakhmankin/onebigjump')
source=Path(os.environ['E1_SNAPSHOT'])
record=json.loads((source/'source-manifest.json').read_text())
assert all(hashlib.sha256((root/Path(p).relative_to(source)).read_bytes()).hexdigest()==h for p,h in record['outputs'].items()), 'working tree changed during validation'
