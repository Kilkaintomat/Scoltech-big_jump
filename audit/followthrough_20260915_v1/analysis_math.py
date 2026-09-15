import collections,math
import numpy as np
from scipy import linalg
def fit(x):
 mean=x.mean(0);c=x-mean
 _,s,v=linalg.svd(c/np.sqrt(len(x)-1),full_matrices=False,check_finite=False)
 return {"mean":mean,"vectors":v,"variances":s*s,"average":float(np.sum(s*s)/x.shape[1])}
def values(x,f,shrink=.1):
 out=np.empty(len(x))
 for lo in range(0,len(x),256):
  hi=min(lo+256,len(x));c=x[lo:hi]-f["mean"];p=c@f["vectors"].T;residual=c-p@f["vectors"]
  out[lo:hi]=np.sqrt(np.sum(p*p/((1-shrink)*f["variances"]+shrink*f["average"]),axis=1)+np.sum(residual*residual,axis=1)/(shrink*f["average"]))
 return out
def exact_distribution(group):
 # Rook polynomial for a permutation matrix with equal-position matching rectangles.
 n=len(group);jc=collections.Counter(r["j"] for r in group);fc=collections.Counter(r["f"] for r in group);rook=[1]
 for v in jc.keys()&fc.keys():
  part=[math.comb(jc[v],k)*math.comb(fc[v],k)*math.factorial(k) for k in range(min(jc[v],fc[v])+1)]
  acc=[0]*(len(rook)+len(part)-1)
  for a,x in enumerate(rook):
   for b,y in enumerate(part):acc[a+b]+=x*y
  rook=acc
 counts=[sum((-1)**(k-h)*math.comb(k,h)*rook[k]*math.factorial(n-k) for k in range(h,len(rook))) for h in range(n+1)]
 assert min(counts)>=0 and sum(counts)==math.factorial(n)
 return np.asarray([v/math.factorial(n) for v in counts],dtype=float)
def exact_position(rows):
 groups=collections.defaultdict(list)
 for r in rows:groups[(r["task_family"],r["L"])].append(r)
 use=[g for g in groups.values() if len(g)>=2];matched=[r for g in use for r in g];prob=np.array([1.])
 for g in use:prob=np.convolve(prob,exact_distribution(g))
 hits=sum(r["j"]==r["f"] for r in matched);n=len(matched)
 return {"matched_groups":n,"excluded_singletons":len(rows)-n,"hits":hits,"rate":hits/n if n else None,
  "null_mean":float(np.dot(prob,np.arange(len(prob)))/n) if n else None,"p_one_sided":float(prob[hits:].sum()) if n else None,
  "stratum_sizes":[len(g) for g in use],"selected_trace_ids":[r["trace_id"] for r in matched],"method":"exact integer rook-polynomial distribution, convolved across textbook-by-length strata"}
def equal_group(rows):
 problems=collections.defaultdict(list);pg={}
 for r in rows:problems[r["problem_id"]].append(r["jump_hit"]-r["surprisal_hit"]);pg[r["problem_id"]]=r["exercise_group"]
 groups=collections.defaultdict(list)
 for p,v in problems.items():groups[pg[p]].append(float(np.mean(v)))
 return {g:float(np.mean(v)) for g,v in groups.items()}
def bootstrap_group(groups,replicates,seed,alpha=.025):
 vals=np.asarray(list(groups.values()),dtype=float);n=len(vals)
 if n<20:return {"groups":n,"mean":float(vals.mean()) if n else None,"interval":None,"available":False}
 rng=np.random.default_rng(seed);samples=[]
 for lo in range(0,replicates,500):
  size=min(500,replicates-lo);samples.extend(vals[rng.integers(0,n,(size,n))].mean(1).tolist())
 return {"groups":n,"mean":float(vals.mean()),"interval":np.quantile(samples,[alpha/2,1-alpha/2]).tolist(),"available":True,"confidence_level":1-alpha,"bootstrap_replicates":replicates,"unit":"exercise_group"}
