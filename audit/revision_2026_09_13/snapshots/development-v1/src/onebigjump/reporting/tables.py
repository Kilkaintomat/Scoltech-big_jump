"""Tables 1 and 2, rendered from records. No number is typed by hand.

Both tables ship in Markdown, for the repository, and in LaTeX with `booktabs`, to be pasted into
the paper. A value the run did not produce is rendered as the paper's own placeholder `[x.xx]`
rather than as a blank or a zero, so an unfilled cell stays visibly unfilled.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "PLACEHOLDER",
    "collect_b3",
    "render_table1",
    "render_table2",
    "render_table_b3",
    "to_latex",
    "to_markdown",
    "write_table",
]

PLACEHOLDER = "[x.xx]"

SUBSET_LABELS = {
    "verified": "verified",
    "refuted_pre": r"refuted, $t<t^*$",
    "refuted_post": r"refuted, $t \geq t^*$",
    "refuted_all": "refuted, all",
}


def _num(value: Any, digits: int = 2) -> str:
    if value is None:
        return PLACEHOLDER
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f != f:  # NaN
        return PLACEHOLDER
    return f"{f:.{digits}f}"


def _ci(point: Any, low: Any, high: Any, digits: int = 2) -> str:
    if point is None:
        return PLACEHOLDER
    body = _num(point, digits)
    if low is None or high is None or float(low) != float(low):
        return body
    return f"{body} [{_num(low, digits)}, {_num(high, digits)}]"


def to_markdown(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    body = list(rows)
    widths = [len(h) for h in headers]
    for row in body:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    out = ["| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)) + " |"]
    out.append("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for row in body:
        out.append("| " + " | ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) + " |")
    return "\n".join(out) + "\n"


def to_latex(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    caption: str = "",
    label: str = "",
    group_column: int | None = None,
) -> str:
    """A `booktabs` table. `group_column` inserts a midrule whenever that column changes."""
    body = list(rows)
    spec = "l" * 1 + "r" * (len(headers) - 1)
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        rf"\begin{{tabular}}{{{spec}}}",
        r"\toprule",
        " & ".join(headers) + r" \\",
        r"\midrule",
    ]
    previous = None
    for row in body:
        if group_column is not None and previous is not None and row[group_column] != previous:
            lines.append(r"\midrule")
        if group_column is not None:
            previous = row[group_column]
        lines.append(" & ".join(row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    if caption:
        lines.append(rf"\caption{{{caption}}}")
    if label:
        lines.append(rf"\label{{{label}}}")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def render_table1(results: Iterable[Any], *, digits: int = 2) -> tuple[list[str], list[list[str]]]:
    """Table 1: tail index on proof traces, per model and subset.

    Columns follow the paper: model, subset, `m` traces, then Hill, moment and GPD each with a
    95% trace-bootstrap interval.
    """
    headers = [
        "Model",
        "Subset",
        "$m$ traces",
        r"$\hat{\gamma}^H$",
        r"$\hat{\gamma}^M$",
        r"$\hat{\gamma}^{GPD}$",
    ]
    rows: list[list[str]] = []
    for res in results:
        for row in res.rows():
            rows.append(
                [
                    f"{row['model']} (L{row['layer']}, {row['statistic']})",
                    SUBSET_LABELS.get(row["subset"], row["subset"]),
                    str(row.get("m_traces", PLACEHOLDER)),
                    _ci(row.get("hill"), row.get("hill_lo"), row.get("hill_hi"), digits),
                    _ci(row.get("moment"), row.get("moment_lo"), row.get("moment_hi"), digits),
                    _ci(row.get("gpd"), row.get("gpd_lo"), row.get("gpd_hi"), digits),
                ]
            )
    return headers, rows


def render_table2(results: Iterable[Any], *, digits: int = 2) -> tuple[list[str], list[list[str]]]:
    """Table 2: localisation of the first rejected step.

    The chance column is not decoration: a hit rate without `E[1/L]` beside it cannot be read,
    because a short trace has a high chance level.
    """
    headers = [
        "Model",
        "statistic",
        "top-1",
        "top-3",
        "chance",
        "surprisal top-1",
        "perm. null",
        "$p$",
    ]
    rows: list[list[str]] = []
    for res in results:
        row = res.row()
        perm_mean, perm_sd = row.get("perm_mean"), row.get("perm_sd")
        perm = (
            PLACEHOLDER
            if perm_mean is None
            else f"{_num(perm_mean, digits)} $\\pm$ {_num(perm_sd, digits)}"
        )
        rows.append(
            [
                str(row["model"]),
                f"$Z^{{{row['statistic']}}}$, $\\ell={row['layer']}$",
                _num(row.get("top1"), digits),
                _num(row.get("top3"), digits),
                _num(row.get("chance"), digits),
                _num(row.get("surprisal_top1"), digits),
                perm,
                _num(row.get("perm_p"), 3),
            ]
        )
    return headers, rows


def write_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    out_dir: Path | str,
    stem: str,
    *,
    caption: str = "",
    label: str = "",
    group_column: int | None = 0,
) -> list[Path]:
    """Write the same table as Markdown and as LaTeX."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"{stem}.md"
    tex = out / f"{stem}.tex"
    md.write_text(to_markdown(headers, rows), encoding="utf-8")
    tex.write_text(
        to_latex(headers, rows, caption=caption, label=label, group_column=group_column),
        encoding="utf-8",
    )
    return [md, tex]


def render_table_b3(runs: Iterable[dict[str, Any]]) -> tuple[list[str], list[list[str]]]:
    """Table B.3: what was sampled, from what, and what came back.

    Appendix B.3 asks for "model, parameter count, number of blocks Lambda, d, benchmark, number
    of problems, samples per problem, temperature, maximum tokens, number of verified/refuted
    traces, mean trace length". Without it the tail indices in Table 1 cannot be read: a
    `gamma_hat` from forty refuted traces and one from four thousand are not the same claim.
    """
    headers = [
        "Model",
        r"$\Lambda$",
        "$d$",
        "Benchmark",
        "problems",
        "$N$",
        "$T$",
        "max tok.",
        "verified",
        "refuted",
        r"mean $L$",
    ]
    rows: list[list[str]] = []
    for run in runs:
        temps = run.get("temperatures") or []
        rows.append(
            [
                str(run.get("model_id", PLACEHOLDER)),
                str(run.get("n_layers", PLACEHOLDER)),
                str(run.get("d_model", PLACEHOLDER)),
                str(run.get("benchmark", PLACEHOLDER)),
                str(run.get("n_problems", PLACEHOLDER)),
                str(run.get("samples_per_problem", PLACEHOLDER)),
                ", ".join(f"{t:g}" for t in temps) if temps else PLACEHOLDER,
                str(run.get("max_new_tokens", PLACEHOLDER)),
                str(run.get("verified", PLACEHOLDER)),
                str(run.get("refuted", PLACEHOLDER)),
                _num(run.get("mean_trace_length"), 1),
            ]
        )
    return headers, rows


def collect_b3(
    generation_manifest: dict[str, Any] | None,
    verification_summary: dict[str, Any] | None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble one Table B.3 row from the manifests the stages already write.

    Nothing here is re-derived: the sampling settings come from the generation manifest and the
    outcome counts from the verification summary, so the row cannot drift from the run.
    """
    gen = (generation_manifest or {}).get("config", {})
    ver = verification_summary or {}
    cfg = model_config or {}
    benchmark = str(gen.get("problems_source") or cfg.get("problems") or "")
    return {
        "model_id": gen.get("model_id") or cfg.get("model_id"),
        "benchmark": Path(benchmark).stem if benchmark else None,
        "n_problems": gen.get("n_problems"),
        "samples_per_problem": gen.get("samples_per_problem") or cfg.get("samples_per_problem"),
        "temperatures": gen.get("temperatures") or cfg.get("temperatures"),
        "max_new_tokens": gen.get("max_new_tokens") or cfg.get("max_new_tokens"),
        "verified": ver.get("verified"),
        "refuted": ver.get("refuted"),
        "mean_trace_length": ver.get("mean_trace_length"),
        "n_layers": cfg.get("n_layers"),
        "d_model": cfg.get("d_model"),
    }
