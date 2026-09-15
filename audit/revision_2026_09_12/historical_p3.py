import os
from pathlib import Path
import numpy as np
from scipy import stats
from onebigjump.e1.artifacts import digest, finish, verify_manifest, write_once
from onebigjump.e1.stages import rows

base=Path('/beegfs/home/denis.rakhmankin/onebigjump')
source=Path(os.environ['E1_SNAPSHOT'])/'source-manifest.json'
root=base/'runs/expansion_20260911/calibration/coupled_overshoot'
manifests=sorted(root.glob('*/manifest.json'))
records=[]
for manifest in manifests:
    verify_manifest(manifest)
    records.extend(rows(manifest.parent/'replicates.jsonl'))
assert len(records)==200 and len({r['trace_id'] for r in records})==200
cutoff=float(stats.genpareto.ppf(.99,.25))
result={'cutoff':cutoff,'groups':{},'exploratory':True,'original_results_unchanged':True}
for name,sample in [('all',records),('below_support',[r for r in records if r['P3_sample']['tau']<cutoff]),('above_support',[r for r in records if r['P3_sample']['tau']>=cutoff])]:
    n=len(sample); k=sum(r['P3']['covers_truth'] for r in sample)
    result['groups'][name]={'datasets':n,'covered':k,'coverage':k/n if n else None,
        'mean_point_bias':float(np.mean([r['P3_sample']['gpd']['gamma']-.25 for r in sample])) if n else None,
        'monte_carlo_ci95':[float(stats.beta.ppf(.025,k,n-k+1)) if k else 0.,float(stats.beta.ppf(.975,k+1,n-k)) if k<n else 1.] if n else None}
folder=base/'audit/revision_2026_09_12/historical-p3'
path=write_once(folder/'metrics.json',result)
finish(folder,stage='historical-p3-support-diagnosis',context={'source':digest(source)},inputs=[source,Path(__file__),*manifests],outputs=[path],metrics=result)
print(result,flush=True)
