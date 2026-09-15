import collections,itertools
from stage_support import *
from analysis_math import *
def main():
 start("p2_pipeline");rng=np.random.default_rng(128)
 checks={}
 for n,d in [(35,7),(7,35)]:
  x=rng.normal(size=(n,d));test=rng.normal(size=(19,d));f=fit(x);cov=np.cov(x,rowvar=False)
  for shrink in [.1,.5,1.]:
   c=(1-shrink)*cov+shrink*np.trace(cov)/d*np.eye(d)
   direct=np.sqrt(np.einsum("ij,ji->i",test-x.mean(0),np.linalg.solve(c,(test-x.mean(0)).T)))
   assert np.allclose(direct,values(test,f,shrink),rtol=1e-8,atol=1e-8)
 checks["full_and_rank_deficient_covariance"]=True
 for n in range(1,8):
  group=[{"j":int(rng.integers(0,3)),"f":int(rng.integers(0,3))} for _ in range(n)]
  brute=collections.Counter(sum(group[i]["j"]==group[k]["f"] for i,k in enumerate(order)) for order in itertools.permutations(range(n)))
  assert np.allclose(exact_distribution(group),[brute[k]/math.factorial(n) for k in range(n+1)])
 assert np.isclose(exact_distribution([{"j":0,"f":0}]*100)[100],1)
 checks["exact_permutation_against_enumeration_and_large_stratum"]=True
 # Distinct tasks within one exercise remain one resampling unit.
 rows=[{"problem_id":"a","exercise_group":"g","jump_hit":1,"surprisal_hit":0}]*9+[{"problem_id":"b","exercise_group":"g","jump_hit":0,"surprisal_hit":1}]
 assert equal_group(rows)=={"g":0.}
 checks["hierarchical_equal_group_weighting"]=True
 import torch
 from transformers import Qwen2Config,Qwen2ForCausalLM,LlamaConfig,LlamaForCausalLM
 from extract import check_forward
 torch.manual_seed(128)
 for cls,conf in [(Qwen2ForCausalLM,Qwen2Config),(LlamaForCausalLM,LlamaConfig)]:
  model=cls(conf(vocab_size=101,hidden_size=32,intermediate_size=64,num_hidden_layers=4,num_attention_heads=4,num_key_value_heads=2)).eval()
  check_forward(model,torch.randint(0,101,(1,257)),[0,1,2])
 checks["independent_Qwen2_and_Llama_hooks_and_logprobs"]=True
 atomic(OUT/"p2_pipeline/math-checks.json",checks);print("P2 CPU CHECKS PASSED",checks,flush=True)
if __name__=="__main__":main()
