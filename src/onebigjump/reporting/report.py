"""Assemble the reproducible report from whatever metrics files exist.

The report is generated, never written by hand, and it is generated from the same files the
figures are drawn from. Two consequences are deliberate:

* a section whose run has not happened says so, with the reason, instead of being omitted -- a
  reader must be able to tell "not run" from "run and found nothing";
* every number carries its provenance, because each run wrote a manifest recording the commit,
  whether the tree was dirty, and a digest of every file. A figure produced from a dirty tree is
  flagged in the report rather than silently shipped.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..manifests import find_manifests

__all__ = ["Section", "build_report", "write_report"]


@dataclass
class Section:
    """One part of the report: a heading, prose, and whatever tables it managed to build."""

    title: str
    body: list[str] = field(default_factory=list)
    status: str = "ok"

    def line(self, text: str = "") -> Section:
        self.body.append(text)
        return self

    def render(self) -> str:
        return f"## {self.title}\n\n" + "\n".join(self.body).rstrip() + "\n"


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None


def _load_manifest(directory: Path) -> dict[str, Any]:
    """The newest manifest in a directory.

    Manifests are per run, not per directory -- several seeds legitimately share an output
    directory -- so there is no single `manifest.json` to open. The newest is the right default
    for a provenance line; a reader wanting all of them has `find_manifests`.
    """
    found = find_manifests(directory)
    return _load(found[-1]) or {} if found else {}


def _provenance(manifest: dict[str, Any] | None) -> str:
    if manifest is None:
        return "_No manifest found for this run._"
    git = manifest.get("environment", {}).get("git", {})
    commit = (git.get("commit") or "unknown")[:8]
    dirty = git.get("dirty")
    if dirty is True:
        state = "**dirty working tree -- not reproducible from any commit**"
    elif git.get("commit") and dirty is False:
        state = "clean"
    else:
        state = "**unknown provenance -- reproducibility unverified**"
    return (
        f"Run `{manifest.get('name')}` at commit `{commit}` ({state}), "
        f"{manifest.get('duration_s', 0):.0f}s, status `{manifest.get('status')}`."
    )


def _missing(title: str, reason: str) -> Section:
    return Section(title, [f"**Not run.** {reason}"], status="missing")


def _figure_one(results: Path) -> Section:
    payload = _load(results / "simulations" / "kesten" / "figure1_metrics.json")
    if payload is None:
        return _missing(
            "Figure 1 -- the dichotomy on the heuristic mixture",
            "`results/simulations/kesten/figure1_metrics.json` is absent; run "
            "`uv run onebigjump run configs/simulation/figure1.yaml`.",
        )
    sec = Section("Figure 1 -- the dichotomy on the heuristic mixture")
    cap = payload["caption_setting"]
    sec.line(
        f"Setting from the caption: `rho = {cap['rho']}`, `kappa = {cap['kappa']}`, "
        f"`d = {cap['d']}`, {cap['n_traces']} traces of {cap['n_steps']} steps, "
        f"tolerance at the {cap['tolerance_quantile']:.1%} quantile. "
        f"`p_c = {cap['p_critical']:.4f}`."
    ).line()
    sec.line(
        "| `p` | `alpha` theory | `xi` theory | Hill [95% CI] | moment | GPD | refuted | top-1 | chance |"
    )
    sec.line("|---|---|---|---|---|---|---|---|---|")
    for s in payload["settings"]:
        boot = s["tail"]["bootstrap"]["hill"]
        alpha = s["alpha_theory"]
        sec.line(
            f"| {s['p']:.2f} | {'inf' if alpha is None else f'{alpha:.4f}'} "
            f"| {s['xi_theory']:.4f} "
            f"| {s['tail']['hill']:.4f} [{boot['ci_low']:.4f}, {boot['ci_high']:.4f}] "
            f"| {s['tail']['moment']:+.4f} | {s['tail']['gpd']:+.4f} "
            f"| {s['n_refuted']} | {s['top1']:.3f} | {s['chance']:.4f} |"
        )
    sec.line()
    sec.line(_provenance(_load_manifest(results / "simulations" / "kesten")))
    return sec


def _lean(results: Path) -> Section:
    candidates = sorted(results.glob("pilot/*/summary.json"))
    if not candidates:
        return _missing(
            "Lean 4 verification -- exact step labels",
            "no `results/pilot/*/summary.json`; run `make lean-verify`.",
        )
    sec = Section("Lean 4 verification -- exact step labels")
    for path in candidates:
        summary = _load(path)
        manifest = _load_manifest(path.parent)
        if summary is None:
            continue
        env = (manifest or {}).get("metrics", {}).get("lean_environment", {})
        sec.line(f"### `{path.parent.name}`").line()
        if env:
            sec.line(
                f"Toolchain `{env.get('toolchain')}`, Mathlib `{str(env.get('mathlib_rev'))[:8]}`."
            ).line()
        sec.line("| category | count |").line("|---|---|")
        for key, value in summary.items():
            shown = f"{value:.3f}" if isinstance(value, float) else str(value)
            sec.line(f"| {key} | {shown} |")
        disagreements = (
            (manifest or {}).get("metrics", {}).get("whole_proof_vs_replay_disagreements")
        )
        sec.line()
        if disagreements is not None:
            sec.line(
                f"Whole-proof compilation and step replay disagree on **{disagreements}** traces. "
                "Appendix B.2 requires them to agree by construction; `sorry` is the one "
                "documented exception and is excluded from the count."
            ).line()
        sec.line(_provenance(manifest))
        sec.line()
    return sec


def _p4(results: Path) -> Section:
    files = sorted(results.glob("full/grokking*/p4_grokking*.json"))
    if not files:
        return _missing(
            "P4 -- the order parameter across the grokking transition",
            "no P4 checkpoint metrics; run `make p4`.",
        )
    sec = Section("P4 -- the order parameter across the grokking transition")
    sec.line(
        "Signed gamma is the moment estimate; xi = max(gamma, 0). Hill is a diagnostic."
    ).line()
    sec.line(
        "Archived gamma_* summaries may use Hill and are not used below. "
        "The presence of training metrics does not establish P4 or certify their provenance."
    ).line()
    for path in files:
        payload = _load(path)
        if payload is None or not payload.get("checkpoints"):
            continue
        cps = payload["checkpoints"]
        sec.line(f"### `{path.parent.name}/{path.name}`").line()
        sec.line(
            "| seed | grokking step | final test acc | moment first | moment last | Hill last |"
        ).line("|---|---|---|---|---|---|")
        grok = payload.get("grokking_step")
        sec.line(
            f"| {payload['seed']} | {grok if grok is not None else '**never**'} "
            f"| {cps[-1]['test_acc']:.3f} "
            f"| {cps[0].get('moment', float('nan')):+.4f} "
            f"| {cps[-1].get('moment', float('nan')):+.4f} | {cps[-1]['hill']:.4f} |"
        ).line()
        if all(c.get("moment") is not None for c in cps):
            xi = [max(float(c["moment"]), 0.0) for c in cps]
            sec.line(
                f"Maximum estimated xi: {max(xi):.4f}. "
                f"Positive at {sum(x > 0 for x in xi)}/{len(xi)} checkpoints."
            ).line()
        else:
            sec.line(
                "Signed moment estimates are missing; xi cannot be recovered from Hill."
            ).line()
        protocol = payload.get("meta", {}).get("progress_measure_protocol")
        sec.line(
            f"Progress-measure protocol: {protocol}."
            if protocol
            else "Legacy progress losses: require recomputation after the Fourier-mask correction."
        ).line()
        manifests = [_load(p) for p in find_manifests(path.parent)]
        matched = next(
            (
                m
                for m in manifests
                if m and any(Path(o["path"]).name == path.name for o in m.get("outputs", []))
            ),
            None,
        )
        sec.line(_provenance(matched)).line()
    return sec


def _feasibility(root: Path, results: Path) -> Section:
    """What this machine can run, derived from what is on disk rather than asserted."""
    sec = Section("What could not be run here, and why")
    sec.line(
        "Run availability below is inferred from saved artifacts. Hardware must be read from "
        "each run manifest; a local machine report does not describe the cluster."
    ).line()

    def ran(pattern: str) -> str:
        return "run" if any(results.glob(pattern)) else "**not run**"

    rows = [
        ("Kesten simulation, Figure 1", ran("simulations/kesten/figure1_metrics.json")),
        (
            "Estimators, bootstrap, tests",
            "test suite present; execution requires test logs"
            if (root / "tests").is_dir()
            else "**not run**",
        ),
        ("Lean 4 + Mathlib step replay", ran("pilot/*/summary.json")),
        ("Modular-addition grokking (P4)", ran("full/grokking*/p4_grokking*.json")),
        (
            "Prover traces from DeepSeek-Prover-V2-7B, Goedel-8B, Kimina-8B",
            ran("full/activations/deviations.parquet"),
        ),
        (
            "Synthetic deduction on 7-8B general models",
            "**not run**: the synthetic deduction pipeline is not implemented",
        ),
    ]
    sec.line("| Stage | Status |").line("|---|---|")
    for name, status in rows:
        sec.line(f"| {name} | {status} |")
    sec.line()
    sec.line(
        "No result from those stages is estimated, extrapolated or filled in. "
        "The placeholders in `docs/experimental_specification.md` section 7 that they would have "
        "filled remain placeholders."
    )
    return sec


def build_report(repo: Path | str = ".", *, results_dir: str = "results") -> str:
    """Assemble the report from the metrics files present in the tree."""
    root = Path(repo)
    results = root / results_dir
    stamp = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())

    head = [
        "# Experimental report",
        "",
        f"Generated {stamp} by `uv run onebigjump report`. Every number below is read from a "
        "metrics file written by a run; none is entered by hand.",
        "",
        "A negative or inconclusive result is reported as one. Sections whose run has not "
        "happened say so rather than being omitted.",
        "",
    ]
    sections = [
        _figure_one(results),
        _lean(results),
        _p4(results),
        _feasibility(root, results),
    ]
    return "\n".join(head) + "\n" + "\n".join(s.render() for s in sections)


def write_report(
    repo: Path | str = ".", out: Path | str = "reports/experimental_report.md"
) -> Path:
    target = Path(repo) / out
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_report(repo), encoding="utf-8")
    return target
