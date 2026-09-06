"""Sample whole proofs from a model, and write what `onebigjump lean-verify` reads.

Appendix B.3: sampling uses vLLM, while activations are recorded with the HuggingFace
implementation. Both backends are here behind one interface, because vLLM is Linux and CUDA only
and this repository has to remain runnable without it.

Two properties of the protocol are enforced here rather than left to the caller:

* **whole proofs, no verifier feedback.** Section 2 requires traces to be generated to their full
  length without the verifier in the loop, "as a prover emits a whole proof before compilation".
  If the sampler could see labels, the law of the step deviations would depend on them and the
  whole coupling argument would be circular.
* **one record per sample.** `N` samples per problem at each temperature, each carrying its own
  `trace_id`, so that a trace is the sampling unit the bootstrap later resamples.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

from ..lean.problems import Problem, build_prompt, extract_lean_block, header_directives
from ..logging import get_logger

__all__ = ["Backend", "HFBackend", "Sample", "VLLMBackend", "generate", "make_backend"]

log = get_logger(__name__)


@dataclass
class Sample:
    """One sampled proof, in the shape `lean-verify` consumes."""

    trace_id: str
    problem_id: str
    model_id: str
    temperature: float
    sample_index: int
    proof: str
    directives: str = ""
    prompt: str = ""
    completion: str = ""
    n_prompt_tokens: int = 0
    n_completion_tokens: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def as_record(self, keep_completion: bool = True) -> dict[str, Any]:
        record = asdict(self)
        if not keep_completion:
            record.pop("completion", None)
        return record


class Backend(Protocol):
    """What a sampler has to provide. Anything satisfying this can drive `generate`."""

    model_id: str

    def sample(
        self, prompts: Sequence[str], *, n: int, temperature: float, max_new_tokens: int
    ) -> list[list[str]]:
        """Return `n` completions for each prompt, in prompt order."""
        ...


@dataclass
class HFBackend:
    """`transformers.generate`. Works anywhere torch does, including CPU and MPS."""

    model_id: str
    device: str = "auto"
    dtype: str = "auto"
    trust_remote_code: bool = False
    batch_size: int = 1
    _model: Any = field(default=None, repr=False)
    _tokenizer: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if self.device == "auto":
            self.device = (
                "cuda"
                if torch.cuda.is_available()
                else "mps"
                if torch.backends.mps.is_available()
                else "cpu"
            )
        torch_dtype = {
            "auto": torch.bfloat16 if self.device != "cpu" else torch.float32,
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }[self.dtype]

        log.info("loading %s onto %s in %s", self.model_id, self.device, torch_dtype)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id, trust_remote_code=self.trust_remote_code
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._tokenizer.padding_side = "left"  # required for batched generation
        model = AutoModelForCausalLM.from_pretrained(
            self.model_id, dtype=torch_dtype, trust_remote_code=self.trust_remote_code
        )
        # The transformers stubs type `PreTrainedModel.to` against the wrong overload of
        # `nn.Module.to`, so a device string is rejected at type-check time but correct at run time.
        self._model = cast(Any, model).to(self.device)
        self._model.eval()

    def sample(
        self, prompts: Sequence[str], *, n: int, temperature: float, max_new_tokens: int
    ) -> list[list[str]]:
        import torch

        out: list[list[str]] = []
        for start in range(0, len(prompts), self.batch_size):
            chunk = list(prompts[start : start + self.batch_size])
            enc = self._tokenizer(chunk, return_tensors="pt", padding=True).to(self.device)
            with torch.no_grad():
                generated = self._model.generate(
                    **enc,
                    do_sample=temperature > 0,
                    temperature=temperature if temperature > 0 else None,
                    num_return_sequences=n,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=self._tokenizer.pad_token_id,
                )
            width = enc["input_ids"].shape[1]
            completions = self._tokenizer.batch_decode(
                generated[:, width:], skip_special_tokens=True
            )
            for i in range(len(chunk)):
                out.append(completions[i * n : (i + 1) * n])
        return out


@dataclass
class VLLMBackend:
    """vLLM. Linux and CUDA only, which is why it sits behind an optional extra."""

    model_id: str
    dtype: str = "bfloat16"
    gpu_memory_utilization: float = 0.90
    max_model_len: int | None = None
    trust_remote_code: bool = False
    _llm: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        try:
            from vllm import LLM
        except ImportError as exc:  # pragma: no cover - depends on the optional extra
            raise ImportError(
                "vLLM is not installed. It is Linux + CUDA only: "
                "uv sync --extra ml --extra inference"
            ) from exc
        log.info("loading %s into vLLM", self.model_id)
        self._llm = LLM(
            model=self.model_id,
            dtype=self.dtype,
            gpu_memory_utilization=self.gpu_memory_utilization,
            max_model_len=self.max_model_len,
            trust_remote_code=self.trust_remote_code,
        )

    def sample(
        self, prompts: Sequence[str], *, n: int, temperature: float, max_new_tokens: int
    ) -> list[list[str]]:
        from vllm import SamplingParams

        params = SamplingParams(n=n, temperature=temperature, max_tokens=max_new_tokens)
        results = self._llm.generate(list(prompts), params)
        return [[o.text for o in r.outputs] for r in results]


def make_backend(model_id: str, backend: str = "auto", **kwargs: Any) -> Backend:
    """Pick a backend. `auto` prefers vLLM where it is importable and falls back to HuggingFace."""
    if backend == "vllm":
        return VLLMBackend(model_id=model_id, **kwargs)
    if backend == "hf":
        return HFBackend(model_id=model_id, **kwargs)
    if backend != "auto":
        raise ValueError(f"unknown backend: {backend!r}")
    try:
        import vllm  # noqa: F401
    except ImportError:
        log.info("vLLM is not available; sampling with transformers")
        return HFBackend(model_id=model_id, **kwargs)
    return VLLMBackend(model_id=model_id, **kwargs)


def generate(
    problems: Sequence[Problem],
    backend: Backend,
    *,
    samples_per_problem: int = 4,
    temperatures: Sequence[float] = (0.6, 1.0),
    max_new_tokens: int = 512,
    keep_completion: bool = True,
) -> Iterator[Sample]:
    """Sample `samples_per_problem` whole proofs of each problem, at each temperature.

    No verifier is consulted: every proof is emitted to its full length and labelled afterwards.
    """
    model_id = backend.model_id
    prompts = [build_prompt(p, model_id) for p in problems]

    for temperature in temperatures:
        t0 = time.time()
        completions = backend.sample(
            prompts,
            n=samples_per_problem,
            temperature=float(temperature),
            max_new_tokens=max_new_tokens,
        )
        log.info(
            "sampled %d problems x %d at T=%.2f in %.0fs",
            len(problems),
            samples_per_problem,
            temperature,
            time.time() - t0,
        )
        for problem, per_problem in zip(problems, completions, strict=True):
            for index, completion in enumerate(per_problem):
                proof = extract_lean_block(completion, problem)
                yield Sample(
                    trace_id=f"{problem.problem_id}-T{temperature:g}-{index:03d}",
                    problem_id=problem.problem_id,
                    model_id=model_id,
                    temperature=float(temperature),
                    sample_index=index,
                    proof=proof,
                    # The `open` lines travel with the sample. `extract_lean_block` cuts
                    # everything before `theorem`, so without this they are gone by the time the
                    # kernel sees the proof -- and dropping `open Real` turns a valid miniF2F
                    # theorem into a parse error that reads as a failed proof.
                    directives=(
                        problem.meta.get("directives") or header_directives(problem.header)
                    ),
                    prompt=build_prompt(problem, model_id),
                    completion=completion if keep_completion else "",
                    meta={"split": problem.split, "source": problem.source},
                )


def write_samples(
    samples: Iterator[Sample], path: Path | str, *, keep_completion: bool = True
) -> tuple[Path, int]:
    """Write samples as JSONL, streaming, and report how many were written."""
    from ..lean.problems import write_jsonl

    count = 0

    def records() -> Iterator[dict[str, Any]]:
        nonlocal count
        for sample in samples:
            count += 1
            yield sample.as_record(keep_completion=keep_completion)

    target = write_jsonl(records(), path)
    return target, count
