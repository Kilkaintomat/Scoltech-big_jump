"""Offset-preserving Lean comment lexer shared by replay and token alignment."""


def mask_comments(text: str, *, mask_strings: bool = False) -> str:
    """Keep character offsets/newlines, including nested comments and escaped strings."""
    out = list(text)
    i = 0
    depth = 0
    string = False
    escaped = False
    quoted_id = False
    while i < len(text):
        c, two = text[i], text[i : i + 2]
        if depth:
            if c != "\n":
                out[i] = " "
            if two in ("/-", "-/"):
                out[i : i + 2] = [" ", " "]
                depth += 1 if two == "/-" else -1
                i += 2
                continue
        elif string:
            if mask_strings and c != "\n":
                out[i] = " "
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                string = False
        elif quoted_id:
            if c == "»":
                quoted_id = False
        elif c == "«":
            quoted_id = True
        elif c == '"':
            string = True
            if mask_strings:
                out[i] = " "
        elif two == "--":
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            out[i:end] = [" "] * (end - i)
            i = end
            continue
        elif two == "/-":
            depth = 1
            out[i : i + 2] = [" ", " "]
            i += 2
            continue
        i += 1
    if depth or string or quoted_id:
        raise ValueError("unterminated comment, string or quoted identifier")
    return "".join(out)
