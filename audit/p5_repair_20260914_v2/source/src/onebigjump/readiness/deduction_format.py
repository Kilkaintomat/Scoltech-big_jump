"""Syntax-only fixed-length output; deliberately blind to rules, facts and target."""

from numbers import Integral


def grammar_for_length(length: int) -> str:
    if isinstance(length, bool) or not isinstance(length, Integral) or not 3 <= length <= 12:
        raise ValueError("assigned length must be an integer in 3..12")
    body = ' "\\n" '.join(["line"] * length)
    return f'root ::= {body} "\\nAnswer: true"\nline ::= "Mira is p" [0-9] [0-9] [0-9] [0-9] "."\n'


def regex_for_length(length: int) -> str:
    grammar_for_length(length)
    return r"(?:Mira is p[0-9]{4}\.\n){" + str(length) + r"}Answer: true"


# V1's explicit xgrammar backend validates without falling back to guidance.
# V1 rejects request-level backend changes and does not support "no-fallback"
# as an engine backend option. The engine selection is pinned in the launcher.
DECODING_BACKEND = "xgrammar"


def guided_decoding_for_length(length: int):
    from vllm.sampling_params import GuidedDecodingParams

    return GuidedDecodingParams(grammar=grammar_for_length(length))
