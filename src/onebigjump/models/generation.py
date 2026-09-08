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

import shutil
import time
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Protocol, cast

from ..lean.problems import Problem, build_prompt, extract_lean_block, header_directives
from ..logging import get_logger

__all__ = [
    "Backend",
    "HFBackend",
    "Sample",
    "VLLMBackend",
    "assert_tokenizer_roundtrips",
    "generate",
    "make_backend",
]

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
    # The token ids the model actually saw and produced. Extraction has to align residual-stream
    # positions to proof steps, and re-tokenising decoded text is not guaranteed to reproduce the
    # sequence that generated it -- byte-level BPE in particular can retokenise a decoded string
    # differently. Storing the ids removes the guess. Empty when the backend cannot supply them.
    prompt_token_ids: list[int] = field(default_factory=list)
    completion_token_ids: list[int] = field(default_factory=list)
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


#: What a backend returns when it can also report tokens: per prompt, per sample, a
#: `(text, prompt_ids, completion_ids)` triple.
Detailed = list[list[tuple[str, list[int], list[int]]]]


#: A probe with the three things a Lean proof cannot survive losing: indentation, newlines, and
#: the Unicode Mathlib is written in.
_ROUNDTRIP_PROBE = "theorem foo (x : \u211d) : 1 = 1 := by\n  norm_num\n"


def assert_tokenizer_roundtrips(tokenizer: Any, model_id: str) -> None:
    """Refuse to sample with a tokenizer that cannot decode what it encodes.

    `transformers` 5.16.1 loads the DeepSeek-Prover tokenizer without a byte-level decoder, so
    `decode(encode(x))` silently returns `x` with every space, newline and non-ASCII character
    deleted: `theorem foo (x : \u211d) : 1 = 1 := by\n  norm_num` comes back as
    `theoremfoo(x:)... :=bynorm_num`. Nothing downstream can notice -- the text is still a string,
    still contains `theorem`, and only the Lean kernel eventually calls it a parse error, by which
    point a GPU-day has been spent. So the round trip is checked once, before the weights load.
    """
    decoded = tokenizer.decode(tokenizer(_ROUNDTRIP_PROBE)["input_ids"], skip_special_tokens=True)
    if _ROUNDTRIP_PROBE.strip() not in decoded:
        raise RuntimeError(
            f"the tokenizer for {model_id} does not round-trip: "
            f"{_ROUNDTRIP_PROBE.strip()!r} decodes to {decoded.strip()!r}. "
            "Whitespace and Unicode are being dropped, so every sampled proof would be "
            "unparseable. Known cause: transformers >= 5 with a byte-level BPE tokenizer; "
            "pin transformers < 5 (4.51.3 is verified) and re-run."
        )


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
        assert_tokenizer_roundtrips(self._tokenizer, self.model_id)
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
        return [
            [t for t, _, _ in per]
            for per in self.sample_detailed(
                prompts, n=n, temperature=temperature, max_new_tokens=max_new_tokens
            )
        ]

    def sample_detailed(
        self, prompts: Sequence[str], *, n: int, temperature: float, max_new_tokens: int
    ) -> Detailed:
        import torch

        pad = self._tokenizer.pad_token_id
        out: Detailed = []
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
                    pad_token_id=pad,
                )
            width = enc["input_ids"].shape[1]
            tail = generated[:, width:]
            completions = self._tokenizer.batch_decode(tail, skip_special_tokens=True)
            for i in range(len(chunk)):
                # Padding is on the left for batched generation, so the prompt ids for this row
                # are the non-pad suffix of its input row.
                row = enc["input_ids"][i].tolist()
                prompt_ids = [t for t in row if t != pad] if pad is not None else row
                per: list[tuple[str, list[int], list[int]]] = []
                for j in range(n):
                    ids = (
                        [t for t in tail[i * n + j].tolist() if t != pad]
                        if pad is not None
                        else tail[i * n + j].tolist()
                    )
                    per.append((completions[i * n + j], prompt_ids, ids))
                out.append(per)
        return out


def _has_c_compiler() -> bool:
    """Can torch.compile actually build anything here?

    vLLM's default compilation level runs inductor, which shells out to a C compiler. The
    Singularity image on the cluster ships CUDA and torch but no toolchain, so the engine dies
    during startup with `Failed to find C compiler` wrapped in `Engine core initialization
    failed` -- three frames away from anything that names the cause.
    """
    return any(shutil.which(cc) for cc in ("gcc", "cc", "clang"))


@dataclass
class VLLMBackend:
    """vLLM. Linux and CUDA only, which is why it sits behind an optional extra."""

    model_id: str
    dtype: str = "bfloat16"
    gpu_memory_utilization: float = 0.90
    max_model_len: int | None = None
    trust_remote_code: bool = False
    #: None means "decide by whether a compiler exists". True skips torch.compile and CUDA graphs.
    enforce_eager: bool | None = None
    _llm: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        try:
            from vllm import LLM
        except ImportError as exc:  # pragma: no cover - depends on the optional extra
            raise ImportError(
                "vLLM is not installed. It is Linux + CUDA only: "
                "uv sync --extra ml --extra inference"
            ) from exc
        # vLLM decodes with the same `transformers` tokenizer, so it has the same failure mode.
        # Checking before `LLM(...)` keeps the message cheap: loading weights takes minutes.
        from transformers import AutoTokenizer

        assert_tokenizer_roundtrips(
            AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=self.trust_remote_code),
            self.model_id,
        )
        eager = self.enforce_eager
        if eager is None:
            eager = not _has_c_compiler()
            if eager:
                log.info("no C compiler found; running vLLM eagerly (no torch.compile)")
        log.info("loading %s into vLLM", self.model_id)
        self._llm = LLM(
            model=self.model_id,
            dtype=self.dtype,
            gpu_memory_utilization=self.gpu_memory_utilization,
            max_model_len=self.max_model_len,
            trust_remote_code=self.trust_remote_code,
            enforce_eager=eager,
        )

    def sample(
        self, prompts: Sequence[str], *, n: int, temperature: float, max_new_tokens: int
    ) -> list[list[str]]:
        return [
            [t for t, _, _ in per]
            for per in self.sample_detailed(
                prompts, n=n, temperature=temperature, max_new_tokens=max_new_tokens
            )
        ]

    def sample_detailed(
        self, prompts: Sequence[str], *, n: int, temperature: float, max_new_tokens: int
    ) -> Detailed:
        from vllm import SamplingParams

        params = SamplingParams(n=n, temperature=temperature, max_tokens=max_new_tokens)
        results = self._llm.generate(list(prompts), params)
        return [
            [(o.text, list(r.prompt_token_ids or []), list(o.token_ids or [])) for o in r.outputs]
            for r in results
        ]


def make_backend(model_id: str, backend: str = "auto", **kwargs: Any) -> Backend:
    """Pick a backend. `auto` prefers vLLM where it is importable and falls back to HuggingFace.

    Keyword arguments are filtered to what the chosen backend actually accepts. The two do not
    take the same ones -- vLLM places the model itself and has no `device` -- and with
    `backend="auto"` the caller cannot know in advance which it is configuring, so passing a
    `device` used to fail at construction after the config had already been validated.
    """
    if backend not in {"auto", "vllm", "hf"}:
        raise ValueError(f"unknown backend: {backend!r}")

    chosen: type[HFBackend] | type[VLLMBackend]
    if backend == "hf":
        chosen = HFBackend
    elif backend == "vllm":
        chosen = VLLMBackend
    else:
        try:
            import vllm  # noqa: F401

            chosen = VLLMBackend
        except ImportError:
            log.info("vLLM is not available; sampling with transformers")
            chosen = HFBackend

    accepted = {f.name for f in fields(chosen) if not f.name.startswith("_")}
    dropped = sorted(set(kwargs) - accepted)
    if dropped:
        log.info("%s does not take %s; ignored", chosen.__name__, ", ".join(dropped))
    return chosen(model_id=model_id, **{k: v for k, v in kwargs.items() if k in accepted})


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
        # Prefer the variant that reports tokens. A backend that cannot is still usable; its
        # samples simply carry empty id lists, which extraction can detect rather than guess at.
        if hasattr(backend, "sample_detailed"):
            detailed = backend.sample_detailed(
                prompts,
                n=samples_per_problem,
                temperature=float(temperature),
                max_new_tokens=max_new_tokens,
            )
        else:
            detailed = [
                [(text, [], []) for text in per]
                for per in backend.sample(
                    prompts,
                    n=samples_per_problem,
                    temperature=float(temperature),
                    max_new_tokens=max_new_tokens,
                )
            ]
        log.info(
            "sampled %d problems x %d at T=%.2f in %.0fs",
            len(problems),
            samples_per_problem,
            temperature,
            time.time() - t0,
        )
        for problem, per_problem in zip(problems, detailed, strict=True):
            for index, (completion, prompt_ids, completion_ids) in enumerate(per_problem):
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
                    n_prompt_tokens=len(prompt_ids),
                    n_completion_tokens=len(completion_ids),
                    prompt_token_ids=list(prompt_ids),
                    completion_token_ids=list(completion_ids),
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
