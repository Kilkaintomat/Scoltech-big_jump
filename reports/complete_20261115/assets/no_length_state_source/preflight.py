from ablation import *
def main():
 guard();checks={}
 for p in HERE.glob('*.py'):compile(p.read_text(encoding='utf8'),str(p),'exec')
 for mode in ['offline','stream']:
  rr=c.load('goedel','ProofNet',mode);small=rr[:18];checks[mode]={}
  for arm in ARMS:
   pp=prep(small,mode,arm);before=design(small,pp,arm);changed=copy.deepcopy(small)
   for r in changed:r['tokens']=r['tokens']*77+12345
   # Both test extraction and full refitting preprocessing ignore tactic token length.
   np.testing.assert_array_equal(before,design(changed,pp,arm))
   pp2=prep(changed,mode,arm);np.testing.assert_array_equal(before,design(changed,pp2,arm))
   if mode=='stream':
    r=copy.deepcopy(next(r for r in rr if r['K']>=4));X=design([r],pp,arm);s=copy.deepcopy(r);s['L']=99999;s['f']=None
    for k in ['q','w','tokens','types','state','prev','deltaX','z','u']:
     s[k]=s[k].copy();s[k][2:]='FUTURE' if k=='types' else 777
    np.testing.assert_array_equal(X[:2],design([s],pp,arm)[:2])
    for k in ['q','w','tokens','types','state','prev','deltaX','z','u']:s[k]=s[k][:2]
    s['K']=2;np.testing.assert_array_equal(X[:2],design([s],pp,arm))
   fit=c.train(small,before,mode,.1);assert all(np.isfinite(p['nll']) for p in c.predict(small,before,fit,mode,arm))
   checks[mode][arm]=dict(length_invariant_train_and_test=True,prefix_invariant=(mode=='stream'),columns=before.shape[1],gradient_max=fit['gradient_max'])
  for ds in ['ProofNet','Putnam']:
   rows=c.load('goedel',ds,mode);seen=[]
   for sp in splits(ds,mode)['outer']:
    assert not set(sp['train_groups'])&set(sp['test_groups'])
    seen.extend(r['trace_id'] for r in c.subset(rows,sp['test_groups']))
    for ins in sp['inner']:
     assert not set(ins['train_groups'])&set(ins['validation_groups'])
     assert (set(ins['train_groups'])|set(ins['validation_groups']))<=set(sp['train_groups'])
   assert len(seen)==len(set(seen))==len(rows),(ds,mode,'coverage')
 # Reproduce the saved PST fit exactly with its coefficients.
 old=c.read(ROOT/'runs/localizer_feature_ablation_20261113_v1/type_length_v2/goedel/0/result.json')
 rr=c.load('goedel','ProofNet','offline')
 tr=[r for r in rr if r['group'].removeprefix('ProofNet:') in old['train_groups']]
 te=[r for r in rr if r['group'].removeprefix('ProofNet:') in old['test_groups']]
 pp=prep(tr,'offline','PST');ps=c.predict(te,design(te,pp,'PST'),old['fits']['PST'],'offline','PST')
 ref=c.read(ROOT/'runs/localizer_feature_ablation_20261113_v1/type_length_v2/goedel/0/predictions.json');ref={r['trace_id']:r['PST'] for r in ref}
 err=max(float(np.max(abs(np.asarray(p['probability'])-ref[p['trace_id']]['probability']))) for p in ps)
 assert err<1e-9,err
 checks['historical_PST_prediction_error']=err
 dest=OUT/'preflight';dest.mkdir(exist_ok=True);c.save(dest/'checks.json',checks);manifest(dest,dict(passed=True));print('PREFLIGHT_PASS',json.dumps(checks),flush=True)
if __name__=='__main__':main()
