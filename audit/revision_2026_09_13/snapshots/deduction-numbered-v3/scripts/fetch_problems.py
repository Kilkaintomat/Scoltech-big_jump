#!/usr/bin/env python3
"""Download theorem statements from the benchmarks of Section 5.1 and normalise them.

    uv run python scripts/fetch_problems.py minif2f --out data/raw/minif2f.jsonl
    uv run python scripts/fetch_problems.py --all

The three benchmarks disagree about almost everything: the field carrying the statement, the
split names, and how a statement ends. None of them ends the way the sampler needs, and left
alone each fails silently rather than loudly -- a finished declaration and an incomplete one both
produce garbage instead of an error. The per-benchmark quirks are recorded in `BENCHMARKS` and
applied here, once.

Which of these the paper finally uses is one of its own open placeholders (`[list final
benchmarks]`), so nothing downstream assumes any of them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


@dataclass(frozen=True)
class Benchmark:
    """One benchmark, and what has to be done to its rows."""

    key: str
    dataset: str
    splits: tuple[str, ...]
    statement_field: str
    id_field: str
    note: str = ""
    extra_directives: str = ""


BENCHMARKS: dict[str, Benchmark] = {
    "minif2f": Benchmark(
        key="minif2f",
        dataset="cat-searcher/minif2f-lean4",
        splits=("test", "validation"),
        statement_field="formal_statement",
        id_field="id",
        note="statements end `:= sorry`; each row also carries its own `split` column",
    ),
    "proofnet": Benchmark(
        key="proofnet",
        dataset="HaimingW/proofnet-lean4",
        splits=("test", "valid"),
        statement_field="formal_statement",
        id_field="name",
        note="statements end with a bare `:=`",
    ),
    "putnambench": Benchmark(
        key="putnambench",
        dataset="HaimingW/PutnamBench-lean4",
        splits=("test",),
        statement_field="lean4_statement",
        id_field="name",
        note=(
            "statements end `:=\\nsorry`; many also open with an `abbrev ..._solution := sorry` "
            "that the model must fill as well, so those cannot verify as pure proofs; the "
            "factorial and transpose notations need scopes the benchmark never opens"
        ),
        extra_directives="open scoped Nat Matrix",
    ),
}


def _lean_toolchain() -> str | None:
    """Which Lean the statements were checked against, if the workspace is present."""
    f = REPO / "lean_workspace" / "mathlib_project" / "lean-toolchain"
    return f.read_text(encoding="utf-8").strip() if f.is_file() else None


def dataset_revision(dataset: str) -> str | None:
    """The exact commit of a Hugging Face dataset repository.

    Without this the snapshot is not pinned: `load_dataset` serves whatever the hub holds today,
    so a benchmark can change under a published result with nothing in the artefacts to show it.
    Returns None when the hub cannot be reached, because a recorded `null` is honest and a missing
    field is not.
    """
    try:
        from huggingface_hub import HfApi

        return str(HfApi().dataset_info(dataset).sha)
    except Exception:  # pragma: no cover - depends on network and on the optional extra
        return None


def fetch(
    bench: Benchmark, split: str, limit: int | None = None, revision: str | None = None
) -> list[dict[str, Any]]:
    """Download one split and normalise it into the schema `load_problems` reads."""
    from datasets import load_dataset

    from onebigjump.lean.problems import (
        DEFAULT_HEADER,
        has_declaration,
        header_directives,
        modernise_binders,
        open_for_tactics,
    )

    # Pinned when a revision is known, so the same call fetches the same statements later.
    rows = load_dataset(bench.dataset, split=split, revision=revision)
    out: list[dict[str, Any]] = []
    skipped: list[str] = []
    for i, row in enumerate(rows):
        raw = str(row.get(bench.statement_field) or "").strip()
        if not raw:
            continue
        # The Lean 4 ports keep rows whose whole statement is commented out, with a note about
        # why porting failed. They carry no theorem and would show up as pipeline errors.
        if not has_declaration(raw):
            skipped.append(str(row.get(bench.id_field) or i))
            continue
        header = str(row.get("header") or "").strip() or DEFAULT_HEADER
        # A solution abbrev makes the task "find the answer and prove it", which is not the
        # theorem-plus-tactics shape the segmentation assumes. Flagged, not silently dropped.
        needs_solution = "_solution" in raw and ":= sorry" in raw.replace("\n", " ")
        modernised = raw != modernise_binders(raw)
        out.append(
            {
                "problem_id": str(row.get(bench.id_field) or f"{bench.key}-{i:05d}"),
                "formal_statement": modernise_binders(open_for_tactics(raw)),
                "header": header,
                "directives": header_directives(header, bench.extra_directives),
                "split": split,
                "source": bench.dataset,
                "benchmark": bench.key,
                "requires_solution_term": needs_solution,
                "binders_modernised": modernised,
                "informal_statement": str(
                    row.get("informal_stmt") or row.get("informal_statement") or ""
                ),
            }
        )
        if limit and len(out) >= limit:
            break
    if skipped:
        print(f"    dropped {len(skipped)} commented-out rows, e.g. {skipped[:3]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("benchmark", nargs="?", choices=sorted(BENCHMARKS), help="which benchmark")
    ap.add_argument("--all", action="store_true", help="fetch every benchmark")
    ap.add_argument("--split", default=None, help="a single split (default: all of them)")
    ap.add_argument("--limit", type=int, default=None, help="stop after this many rows")
    ap.add_argument("--out-dir", type=Path, default=REPO / "data" / "raw")
    args = ap.parse_args()

    if not args.all and not args.benchmark:
        ap.error("give a benchmark name or --all")
    chosen = list(BENCHMARKS.values()) if args.all else [BENCHMARKS[args.benchmark]]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, Any]] = []
    for bench in chosen:
        revision = dataset_revision(bench.dataset)
        if revision is None:
            print(f"  {bench.key}: could not read the dataset revision; the snapshot is unpinned")
        splits = (args.split,) if args.split else bench.splits
        for split in splits:
            try:
                records = fetch(bench, split, limit=args.limit, revision=revision)
            except Exception as exc:
                print(f"  {bench.key}/{split}: FAILED ({type(exc).__name__}: {exc})")
                continue
            path = args.out_dir / f"{bench.key}_{split}.jsonl"
            path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                encoding="utf-8",
            )
            flagged = sum(r["requires_solution_term"] for r in records)
            summary.append(
                {
                    "benchmark": bench.key,
                    "split": split,
                    # Everything needed to fetch exactly these statements again. Recording only
                    # the count and the byte size, as this used to, leaves a reviewer unable to
                    # tell whether the benchmark moved under the result.
                    "dataset": bench.dataset,
                    "revision": revision,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "lean_toolchain": _lean_toolchain(),
                    "problems": len(records),
                    "requires_solution_term": flagged,
                    "usable_without_solution_term": len(records) - flagged,
                    "bytes": path.stat().st_size,
                    "path": str(path.relative_to(REPO)),
                }
            )
            print(
                f"  {bench.key}/{split}: {len(records)} problems, "
                f"{path.stat().st_size / 1e3:.0f} kB -> {path.relative_to(REPO)}"
                + (f"  ({flagged} need a solution term)" if flagged else "")
            )

    if summary:
        (args.out_dir / "benchmarks.json").write_text(
            json.dumps({"benchmarks": summary, "notes": {b.key: b.note for b in chosen}}, indent=2),
            encoding="utf-8",
        )
        total = sum(s["bytes"] for s in summary)
        usable = sum(s["usable_without_solution_term"] for s in summary)
        n = sum(s["problems"] for s in summary)
        print(f"\ntotal {n} problems, {total / 1e6:.2f} MB")
        if usable != n:
            # PutnamBench opens many statements with `abbrev ..._solution := sorry`, which the
            # model must also fill; those cannot be verified by the current protocol. Quoting the
            # unqualified total overstates what the benchmark actually supplies.
            print(f"of which {usable} are usable without also supplying a solution term")
    return 0 if summary else 1


if __name__ == "__main__":
    raise SystemExit(main())
