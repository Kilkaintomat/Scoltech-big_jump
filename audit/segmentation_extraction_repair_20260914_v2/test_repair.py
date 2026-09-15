"""Regression tests for the two observed failures and independent forward equivalence."""
import types,unittest
import numpy as np
import torch
from transformers import LlamaConfig,LlamaForCausalLM,Qwen2Config,Qwen2ForCausalLM,Qwen3Config,Qwen3ForCausalLM
from extract import check_forward,token_logprobs
from repair_support import validate_architecture,backend_comparison
class CompatibilityTests(unittest.TestCase):
    def test_missing_backend_probabilities_are_explicitly_unavailable(self):
        r=backend_comparison({"completion_token_ids":[2,3]},np.array([-.5,-.2]))
        self.assertIsNone(r["backend_logprob_mean_abs_error"])
        self.assertFalse(r["backend_logprob_comparison"]["available"])
    def test_present_backend_probabilities_are_compared(self):
        r=backend_comparison({"generation_token_logprobs":[-.5,-.2]},np.array([-.4,-.3]))
        self.assertAlmostEqual(r["backend_logprob_mean_abs_error"],.1)
    def test_bad_backend_shape_rejected(self):
        with self.assertRaises(ValueError):backend_comparison({"generation_token_logprobs":[-.5]},np.array([-.4,-.3]))
    def test_bad_backend_values_rejected(self):
        with self.assertRaises(ValueError):backend_comparison({"generation_token_logprobs":[float("nan")]},np.array([-.4]))
    def test_unknown_architecture_rejected(self):
        m=types.SimpleNamespace(config=types.SimpleNamespace(model_type="qwen3"))
        with self.assertRaises(ValueError):validate_architecture(m)
    def test_full_forward_equivalence_supported_architectures(self):
        torch.manual_seed(20260914)
        for Config,Model in [(LlamaConfig,LlamaForCausalLM),(Qwen2Config,Qwen2ForCausalLM),(Qwen3Config,Qwen3ForCausalLM)]:
            with self.subTest(architecture=Model.__name__):
                c=Config(vocab_size=67,hidden_size=32,intermediate_size=64,num_hidden_layers=3,
                         num_attention_heads=4,num_key_value_heads=2,head_dim=8)
                c._attn_implementation="sdpa";m=Model(c).eval();validate_architecture(m)
                ids=torch.tensor([[1,7,3,4,2,18,66,13,22,11,9,31,48,10,2]])
                checks=check_forward(m,ids,[0,1]);self.assertTrue(all(r["passed"] for r in checks.values()))
                with torch.inference_mode():
                    h=m.model(input_ids=ids,use_cache=False).last_hidden_state
                    ref=m(input_ids=ids,use_cache=False).logits[0,:-1].float()
                    expected=(ref.gather(1,ids[0,1:,None]).squeeze(1)-ref.logsumexp(-1)).numpy()
                    for chunk in [1,4,128]:
                        np.testing.assert_allclose(token_logprobs(m,h,ids,chunk),expected,atol=1e-5,rtol=1e-5)
    def test_unvalidated_logit_transform_rejected(self):
        c=Qwen3Config(vocab_size=67,hidden_size=32,intermediate_size=64,num_hidden_layers=1,num_attention_heads=4,num_key_value_heads=2,head_dim=8)
        m=Qwen3ForCausalLM(c);m.config.logit_scale=2
        with self.assertRaises(ValueError):validate_architecture(m)
