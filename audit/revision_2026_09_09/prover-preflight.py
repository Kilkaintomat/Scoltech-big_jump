"""Two-token engine check, never an experimental proof or a benchmark measurement."""
import os
from pathlib import Path
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from onebigjump.e1.artifacts import finish, read_json, write_once
from onebigjump.e1.stages import check_model

root = Path("/beegfs/home/denis.rakhmankin/onebigjump/runs/e1_20260908T171727Z")
config = read_json(root / "pilot/protocol.json")
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
check_model(root, config)
tokenizer = AutoTokenizer.from_pretrained(config["model_path"], local_files_only=True)
ids = tokenizer.apply_chat_template([{"role":"user","content":"Reply with the word ready."}],
                                    tokenize=True, add_generation_prompt=True)
engine = LLM(model=config["model_path"], tokenizer=config["model_path"], dtype="bfloat16",
             trust_remote_code=False, enforce_eager=True, gpu_memory_utilization=0.85,
             max_model_len=12288, max_num_seqs=12, seed=config["seed"])
output = engine.generate([{"prompt_token_ids":ids}],
                         [SamplingParams(n=1,temperature=0.6,max_tokens=2,seed=123,
                                         logprobs=1,skip_special_tokens=False)])[0]
assert output.prompt_token_ids == ids
answer = output.outputs[0]
assert answer.token_ids and answer.logprobs and len(answer.token_ids)==len(answer.logprobs)
for token, probabilities in zip(answer.token_ids, answer.logprobs, strict=True):
    assert token in probabilities
directory = root / "checks" / ("prover-preflight-" + os.environ["SLURM_JOB_ID"])
result = {"passed":True,"benchmark":False,"purpose":"engine/API check only",
          "tokens":list(answer.token_ids),"finish_reason":answer.finish_reason}
artifact = write_once(directory / "result.json", result)
finish(directory, stage="prover-engine-preflight", context={},
       inputs=[source,root/"pilot/protocol.json",root/"checks/model-digests.json",
               root/"checks/container-digest.json"], outputs=[artifact], metrics=result)
print("REAL PROVER ENGINE PREFLIGHT PASSED",flush=True)
