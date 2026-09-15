def _finalise(seg: Segment) -> None:
    """Re-attach continuation lines, dedented to the segment's own indentation."""
    body = [ln for ln in seg.continuation_lines if ln.strip() or seg.continuation_lines]
    while body and not body[-1].strip():
        body.pop()
    if not body:
        seg.continuation_lines = []
        return
    seg.text = "\n".join(
        [seg.text, *(ln[min(seg.indent, len(ln) - len(ln.lstrip())) :] for ln in body)]
    )
    seg.continuation_lines = body
