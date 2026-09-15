"""Explicit compatibility checks for the immutable extraction repair."""
import numpy as np
from data import REPO,read,digest
HERE=REPO/"audit/segmentation_extraction_repair_20260914_v3"
OUT=REPO/"runs/segmentation_extraction_repair_20260914_v3"
def check_repair():
    manifest=HERE/"source-manifest.json"
    for p,h in read(manifest)["files"].items():
        if digest(p)!=h:raise ValueError("repair source changed: "+p)
    return manifest
def validate_architecture(model):
    names={"llama":"LlamaForCausalLM","qwen2":"Qwen2ForCausalLM","qwen3":"Qwen3ForCausalLM"}
    if names.get(model.config.model_type)!=type(model).__name__:
        raise ValueError("unvalidated output head architecture")
    for attr in ["logit_scale","final_logit_softcapping"]:
        if getattr(model.config,attr,None) is not None:raise ValueError("unvalidated logit transform")
def backend_comparison(sample,completion_lp):
    # Segmentation exports retain token IDs, but do not export generation logprobs.
    # This is an optional backend diagnostic, never the source of measured surprisal.
    if "generation_token_logprobs" not in sample:
        return {"backend_logprob_mean_abs_error":None,
                "backend_logprob_comparison":{"available":False,"reason":"generation logprobs absent from segmentation input export"}}
    original=np.asarray(sample["generation_token_logprobs"],dtype=float)
    if original.shape!=completion_lp.shape or not np.isfinite(original).all():
        raise ValueError("invalid generation logprobs")
    return {"backend_logprob_mean_abs_error":float(np.mean(np.abs(original-completion_lp))),
            "backend_logprob_comparison":{"available":True}}
