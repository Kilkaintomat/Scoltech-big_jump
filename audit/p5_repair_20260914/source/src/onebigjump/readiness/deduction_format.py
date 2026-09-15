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
