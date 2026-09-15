from pathlib import Path
import os, json, hashlib, csv, time, shutil
import numpy as np
import torch
from scipy import stats
from onebigjump.models.grokking import make_data, build_model, key_frequencies, progress_measures, fourier_circuit_logits
from onebigjump.experiments.p4_grokking import _tail_fast
from onebigjump.stats import hill, moment, sorted_positive_desc
from onebigjump.stats.gpd import gpd_from_order_statistics
torch.set_num_threads(4)
ROOT=Path('/beegfs/home/denis.rakhmankin/onebigjump')
OUT=ROOT/'audit/p4_audit_20260914'
SNAP=ROOT/'audit/readiness_2026_09_11/snapshots/expansion-v1-20260911T024740Z'
RUN=ROOT/'runs/expansion_20260911/p4'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,np.ndarray): return clean(x.tolist())
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.floating,float)): return float(x) if np.isfinite(x) else None
    if isinstance(x,np.bool_): return bool(x)
    return x
def write(name,x): (OUT/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2),encoding='utf-8')
def csvwrite(name,rows):
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
checks=[]; inputs={}; rows=[]; series={}; tails=[]; config={}; windows=[]; start=time.monotonic()
source=read(SNAP/'source-manifest.json')
write('source-manifest-shape.json',{'keys':list(source)})
source_map=source.get('outputs',source.get('files',{}))
for rel in ['src/onebigjump/readiness/p4.py','src/onebigjump/models/grokking.py','src/onebigjump/experiments/p4_grokking.py','src/onebigjump/stats/gpd.py','src/onebigjump/stats/hill.py','src/onebigjump/stats/moment.py','src/onebigjump/stats/thresholds.py','src/onebigjump/stats/bootstrap.py','src/onebigjump/config.py','tests/unit/test_grokking.py','tests/unit/test_readiness.py']:
    p=SNAP/rel
    if not (OUT/'sources'/p.name).exists(): shutil.copyfile(p,OUT/'sources'/p.name)
    inputs[str(p)]=digest(p)
    checks.append({'check':'source_sha','file':rel,'recorded':source_map.get(str(p)),'actual':digest(p),'matches':source_map.get(str(p))==digest(p)})
summary=read(RUN/'summary/metrics.json')
shutil.copy2(RUN/'summary/metrics.json',OUT/'original-paired-summary.json')
inputs[str(RUN/'summary/manifest.json')]=digest(RUN/'summary/manifest.json')
for seed in range(5):
    for arm in ['real','null']:
        tag=f'{arm}-{seed}'; folder=RUN/tag; mf=folder/'measurement'
        manifest=read(mf/'manifest.json')
        c=read(folder/'training/manifest.json')['metrics']['config']; config[tag]=c
        cps=[read(p) for p in sorted(mf.glob('step-*.json'))]; series[tag]=cps
        inputs[str(mf/'manifest.json')]=digest(mf/'manifest.json')
        mismatches=[]
        for p in sorted(mf.glob('step-*.json')):
            # Manifest paths are canonicalized on compute nodes.
            expected=manifest['outputs'].get(str(p.resolve()))
            if expected != digest(p): mismatches.append(str(p))
        checks.append({'check':'all_scalar_digests','tag':tag,'checked':len(cps),'mismatches':mismatches})
        m=read(mf/'metrics.json'); ref=m['primary_transition']['reference_step']
        def sustained(key,th):
            return next((c['step'] for i,c in enumerate(cps[:-4]) if all(x[key]>=th for x in cps[i:i+5])),None)
        row={'arm':arm,'seed':seed,'n_checkpoints':len(cps),'n_inputs':cps[0]['n'],'k_fast':cps[0]['k'],'ref90':ref,'train99':sustained('train_acc',.99),'test10':sustained('test_acc',.1),'test50':sustained('test_acc',.5),'test99':sustained('test_acc',.99)}
        for field in ['train_acc','test_acc','train_loss','test_loss','hill','moment','gpd','restricted_loss','excluded_loss','median_deviation']:
            vals=np.array([x[field] if x[field] is not None else np.nan for x in cps])
            row.update({field+'_first':vals[0],field+'_last':vals[-1],field+'_min':np.nanmin(vals),field+'_max':np.nanmax(vals)})
            if field in ['moment','gpd']: row[field+'_n_positive']=int(np.sum(vals>0))
        row['xi_moves_legacy']=m['legacy_exploratory']['xi_moves']
        row['xi_exceeds_noise_fraction']=m['legacy_exploratory']['xi_exceeds_noise_fraction']
        row['sharpest_drop_legacy']=m['legacy_exploratory']['sharpest_drop_step']
        rows.append(row)
        for p in sorted((folder/'tail').glob('step-*.json')):
            t=read(p); e=t['estimate']
            tr={'arm':arm,'seed':seed,'step':t['step'],'k':e['k'],'hill':e['hill'],'moment':e['moment'],'gpd':e['gpd'],'identified':e['identification']['identified'],'decades':e['identification']['decades'],'favours':e['comparison']['favours'],'unstable':e['k_selection']['stability']['unstable']}
            for name in ['hill','moment','gpd']:
                b=e['bootstrap'][name]
                for field in ['n_valid','n_resamples','ci_low','ci_high']: tr[name+'_'+field]=b[field]
            tails.append(tr)
        print('read',tag,len(cps),'ref',ref,flush=True)
    # Original same-seed pairing, including initial model tensors and data partition.
    d0=make_data(seed=seed); d1=make_data(seed=seed,shuffle_labels=True)
    w0=torch.load(RUN/f'real-{seed}/training/step-000000.pt',map_location='cpu',weights_only=False)
    w1=torch.load(RUN/f'null-{seed}/training/step-000000.pt',map_location='cpu',weights_only=False)
    checks.append({'check':'paired_initialization_and_data','seed':seed,
        'weights_equal':all(torch.equal(w0['model'][k],v) for k,v in w1['model'].items()),
        'initial_optimizer_equal':w0['optimizer']==w1['optimizer'],
        'train_indices_equal':torch.equal(w0['train_indices'],w1['train_indices']) and torch.equal(d0.train_idx,d1.train_idx),
        'test_indices_equal':torch.equal(w0['test_indices'],w1['test_indices']) and torch.equal(d0.test_idx,d1.test_idx),
        'disjoint':len(set(d0.train_idx.tolist()) & set(d0.test_idx.tolist()))==0,
        'n_train':len(d0.train_idx),'n_test':len(d0.test_idx),
        'label_histogram_equal':torch.equal(torch.bincount(d0.targets),torch.bincount(d1.targets)),
        'config_diff':[k for k in config[f'real-{seed}']['grokking'] if config[f'real-{seed}']['grokking'][k]!=config[f'null-{seed}']['grokking'][k]]})
    ref=summary['pairs'][seed]['real_reference_step']
    for arm in ['real','null']:
        cps=series[f'{arm}-{seed}']
        for key in ['hill','moment','gpd','restricted_loss','excluded_loss','test_acc']:
            before=[c[key] for c in cps if ref-500<=c['step']<ref]; after=[c[key] for c in cps if ref<c['step']<=ref+500]
            a,b=float(np.median(before)),float(np.median(after))
            windows.append({'seed':seed,'arm':arm,'ref':ref,'metric':key,'before':a,'after':b,'delta':b-a})
            expected=summary['pairs'][seed][arm][key]
            checks.append({'check':'paired_summary_arithmetic','seed':seed,'arm':arm,'metric':key,'matches':abs(b-a-expected)<1e-12})
write('configs.json',config); write('runs.json',rows); write('full-tail.json',tails); write('windows.json',windows); write('series.json',series)
csvwrite('runs.csv',clean(rows));csvwrite('windows.csv',clean(windows));csvwrite('full-tail.csv',clean(tails))
# Fixed, disclosed diagnostic grid: do not select the grid cell that supports P4.
sensitivity=[]; norm_errors=[]; max_manual={'hill':0.,'moment':0.}
for seed in range(5):
    ref=summary['pairs'][seed]['real_reference_step']
    for arm in ['real','null']:
        tag=f'{arm}-{seed}'; cache={}
        for cp in series[tag]:
            if not (ref-500<=cp['step']<=ref+500) or cp['step']==ref: continue
            step=cp['step']; p=RUN/tag/'measurement'/f'norms-{step:06d}.npz'
            if digest(p)!=cp['norms_sha256']: norm_errors.append(str(p))
            with np.load(p) as zf: z=zf['z']; tr=zf['train_idx']; te=zf['test_idx']
            x=sorted_positive_desc(z); k=cp['k']; logs=np.log(x[:k]/x[k])
            h=float(logs.mean()); m=float(h+1-.5/(1-h*h/np.mean(logs**2)))
            max_manual['hill']=max(max_manual['hill'],abs(h-cp['hill']))
            max_manual['moment']=max(max_manual['moment'],abs(m-cp['moment']))
            cache[step]=(z,tr,te)
        for split in ['all','train','test']:
            for frac in [.01,.025,.05,.10]:
                vals=[]
                for step,(z,tr,te) in cache.items():
                    v=z if split=='all' else z[tr if split=='train' else te]
                    if split=='all' and frac==.05:
                        cp=series[tag][step//100]; h,m,g,k=cp['hill'],cp['moment'],cp['gpd'],cp['k']
                    else: h,m,g,k=_tail_fast(v,k_frac=frac)
                    vals.append((step,h,m,g,k))
                row={'seed':seed,'arm':arm,'split':split,'fraction':frac,'k':vals[0][-1]}
                for i,key in enumerate(['hill','moment','gpd'],start=1):
                    a=np.array([v[i] for v in vals if v[0]<ref]); b=np.array([v[i] for v in vals if v[0]>ref])
                    row[key+'_before']=np.median(a);row[key+'_after']=np.median(b);row[key+'_delta']=np.median(b)-np.median(a)
                sensitivity.append(row)
        print('sensitivity',tag,round(time.monotonic()-start,1),flush=True)
checks.append({'check':'selected_norms_digests','checked':100,'mismatches':norm_errors})
checks.append({'check':'independent_moment_hill_arithmetic','max_abs_error':max_manual})
write('sensitivity.json',sensitivity);csvwrite('sensitivity.csv',clean(sensitivity))
# Sparse forward reconstruction. No fitting or training; final states and two transition points.
reproductions=[]; spectra=[]
for seed in range(5):
    for arm in ['real','null']:
        tag=f'{arm}-{seed}'; cfg=config[tag]['grokking']; data=make_data(seed=seed,shuffle_labels=arm=='null')
        model=build_model(seed=seed).eval()
        p=RUN/tag/'training/step-040000.pt'; state=torch.load(p,map_location='cpu',weights_only=False); model.load_state_dict(state['model'])
        expected=read(p.with_suffix('.pt.receipt.json'))
        checks.append({'check':'selected_checkpoint_digest','file':str(p),'matches':digest(p)==expected['sha256']})
        freqs=key_frequencies(model)
        emb=model.embed.weight[:113].detach().numpy(); wl=(model.unembed.weight@model.block.fc_out.weight).detach().numpy()
        powers={}
        for name,w in [('embedding',emb),('neuron_logit',wl)]:
            power=np.abs(np.fft.rfft(w,axis=0))**2; power=power.sum(axis=1); power[0]=0
            powers[name]={'top6':sorted((np.argsort(power[1:])[::-1][:6]+1).tolist()),'retained_power_share':float(power[freqs].sum()/power.sum()),'spectrum':power.tolist()}
        spectra.append({'tag':tag,'saved_frequencies':read(RUN/tag/'measurement/frequencies.json')['frequencies'],'recomputed_frequencies':freqs,'powers':powers})
        selected=[40000]
        if seed in [0,2,4] and arm=='real':
            ref=summary['pairs'][seed]['real_reference_step']; selected += [ref-300,ref+300]
        for step in selected:
            p=RUN/tag/'training'/f'step-{step:06d}.pt'
            state=torch.load(p,map_location='cpu',weights_only=False);model.load_state_dict(state['model'])
            if step!=40000: checks.append({'check':'selected_checkpoint_digest','file':str(p),'matches':digest(p)==read(p.with_suffix('.pt.receipt.json'))['sha256']})
            cp=series[tag][step//100]
            with torch.no_grad():
                parts=[]; lparts=[]
                for x in data.inputs.split(512):
                    parts.append(model.block_increment(x).numpy());lparts.append(model(x))
                inc=np.concatenate(parts); logits=torch.cat(lparts)
            z=np.linalg.norm(inc,axis=1); med=float(np.median(z)); zn=z/med
            with np.load(RUN/tag/'measurement'/f'norms-{step:06d}.npz') as zz: saved=zz['z']
            # Alternative exact sum-only projection is diagnostic; not substituted for the paper-style product basis.
            grid=logits.numpy().reshape(113,113,113); restricted,excluded=fourier_circuit_logits(grid,freqs)
            ce=lambda x,idx:float(torch.nn.functional.cross_entropy(torch.tensor(x.reshape(12769,113),dtype=torch.float32)[idx],data.targets[idx]))
            allidx=torch.arange(12769)
            spec=np.fft.fft2(grid,axes=(0,1)); mask=np.zeros((113,113),bool)
            for f in freqs:mask[f,f]=True;mask[-f,-f]=True
            mask[0,0]=True
            sumonly=np.fft.ifft2(spec*mask[:,:,None],axes=(0,1)).real
            acc=float((logits[data.test_idx].argmax(-1)==data.targets[data.test_idx]).float().mean())
            r={'tag':tag,'step':step,'norms_max_abs_error':float(np.max(np.abs(zn-saved))),'median_abs_error':abs(med-cp['median_deviation']),'test_acc_saved':cp['test_acc'],'test_acc_recomputed':acc,
               'restricted_saved':cp['restricted_loss'],'restricted_recomputed':ce(restricted,allidx),'restricted_test_only':ce(restricted,data.test_idx),
               'excluded_saved':cp['excluded_loss'],'excluded_recomputed':ce(excluded,data.train_idx),
               'restricted_sum_only_all':ce(sumonly,allidx),
               'test_acc':acc}
            reproductions.append(r); print('forward',tag,step,round(time.monotonic()-start,1),flush=True)
write('forward-reconstruction.json',reproductions);write('spectra.json',spectra)
# Mathematical identity and expected behavior of the Fourier mask, no learned parameters.
p=17;a=np.arange(p)[:,None];b=np.arange(p)[None,:]
terms={'sum':np.cos(2*np.pi*3*(a+b)/p),'difference':np.cos(2*np.pi*3*(a-b)/p),'mixed':np.cos(2*np.pi*(3*a+5*b)/p),'single':np.broadcast_to(np.cos(2*np.pi*3*a/p),(p,p)),'dc':np.ones((p,p))}
fourier=[]
for name,z in terms.items():
    r,e=fourier_circuit_logits(z[:,:,None],[3])
    fourier.append({'component':name,'restricted_retained_norm_ratio':np.linalg.norm(r)/np.linalg.norm(z),'excluded_retained_norm_ratio':np.linalg.norm(e)/np.linalg.norm(z)})
write('fourier-mask-controls.json',fourier)
write('checks.json',checks)
write('provenance.json',{'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'job':os.environ.get('SLURM_JOB_ID'),'source_snapshot':str(SNAP),'run_root':str(RUN),'script_sha256':digest(Path(__file__)),'inputs':inputs,'elapsed_s':time.monotonic()-start,'scope':'Read-only audit of stored runs; diagnostic threshold/split grid; sparse forward replay; no training, no confirmatory p-values.'})
print('DONE',round(time.monotonic()-start,1),flush=True)
