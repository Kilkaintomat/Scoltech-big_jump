"""Command line entry point. Every experiment is launched from a YAML config, never from flags.

    onebigjump doctor                       # what this machine can and cannot run
    onebigjump run configs/simulation/figure1.yaml
    onebigjump figure1 --quick              # the Figure 1 reproduction, small

A config is validated against `onebigjump.config` before anything runs, and the resolved config
is copied into the run manifest, so an artifact always carries the settings that produced it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .config import KestenConfig, RunConfig, load_config
from .logging import setup_logging

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Heavy tails in residual-stream reasoning trajectories.",
)
console = Console()


@app.callback()
def _main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG logging")] = False,
    log_file: Annotated[Path | None, typer.Option(help="also write logs here")] = None,
) -> None:
    setup_logging("DEBUG" if verbose else "INFO", log_file=log_file)


@app.command()
def doctor(
    write_report: Annotated[
        bool, typer.Option("--write-report", help="refresh docs/system_report.md")
    ] = False,
) -> None:
    """Report what this machine can run, and what it cannot."""
    from .reproducibility import git_info, hardware_info, package_versions

    hw = hardware_info()
    table = Table(title="onebigjump doctor", show_header=True, header_style="bold")
    table.add_column("check")
    table.add_column("value")
    table.add_column("verdict")

    def row(name: str, value: object, ok: bool, note: str = "") -> None:
        mark = "[green]ok[/green]" if ok else "[yellow]absent[/yellow]"
        table.add_row(name, str(value), f"{mark} {note}".strip())

    row("platform", hw["platform"], True)
    row("python", hw["python"], sys.version_info[:2] >= (3, 11))
    row("cpu cores", hw["cpu_count"], True)
    row("RAM (GB)", hw.get("ram_gb", "?"), float(hw.get("ram_gb", 0)) >= 8)
    row("torch", hw.get("torch") or "-", hw.get("torch") is not None)
    row(
        "CUDA", hw.get("cuda_version") or "-", bool(hw.get("cuda_available")), "prover runs need it"
    )
    row("MPS", hw.get("mps_available", False), bool(hw.get("mps_available")))

    import shutil

    for tool, why in (
        ("git", ""),
        ("gh", "needed to push"),
        ("elan", "needed for Lean 4"),
        ("lake", "needed for Mathlib"),
        ("sbatch", "Slurm; optional"),
    ):
        path = shutil.which(tool)
        row(tool, path or "-", path is not None, why)

    console.print(table)

    git = git_info(Path.cwd())
    if git["commit"]:
        state = "[yellow]dirty[/yellow]" if git["dirty"] else "[green]clean[/green]"
        console.print(f"repository {git['commit'][:8]} on {git['branch']}, working tree {state}")
    console.print(f"tracked packages: {len(package_versions())}")

    if write_report:
        console.print(
            "[yellow]--write-report regenerates docs/system_report.md via scripts/doctor.py[/yellow]"
        )


@app.command()
def run(
    config: Annotated[Path, typer.Argument(help="YAML config file")],
    out_dir: Annotated[
        Path | None, typer.Option(help="override the config's output directory")
    ] = None,
) -> None:
    """Run the experiment described by a config file."""
    cfg = load_config(config)
    console.print(f"[bold]{cfg.name}[/bold] ({cfg.kind}) - {cfg.description or 'no description'}")
    dispatch = {"kesten": _run_kesten, "grokking": _run_grokking, "lean": _run_lean}
    if cfg.kind not in dispatch:
        console.print(f"[red]kind '{cfg.kind}' is not implemented yet[/red]")
        raise typer.Exit(code=2)
    dispatch[cfg.kind](cfg, out_dir)


def _run_kesten(cfg: RunConfig, out_dir: Path | None) -> None:
    from .simulation.figure1 import run_figure_one

    section = cfg.kesten or KestenConfig()
    payload = run_figure_one(section, out_dir=out_dir or section.out_dir)
    _print_kesten_summary(payload)


def _run_grokking(cfg: RunConfig, out_dir: Path | None) -> None:
    from .config import GrokkingConfig
    from .experiments.p4_grokking import run_p4

    section = cfg.grokking or GrokkingConfig()
    for seed in section.seeds:
        payload = run_p4(section, out_dir=out_dir or section.out_dir, seed=seed)
        console.print(
            f"seed {seed}: grokking at step {payload['grokking_step']}, "
            f"gamma_hat {payload['checkpoints'][0]['hill']:.4f} -> "
            f"{payload['checkpoints'][-1]['hill']:.4f}"
        )


def _run_lean(cfg: RunConfig, out_dir: Path | None) -> None:
    from .config import LeanConfig
    from .lean.batch import read_requests, verify_batch

    section = cfg.lean or LeanConfig()
    if section.input_traces is None:
        console.print("[red]lean.input_traces is not set in the config[/red]")
        raise typer.Exit(code=2)
    _, summary = verify_batch(
        read_requests(section.input_traces),
        out_dir or section.out_dir,
        workspace=section.workspace,
        max_traces=section.max_traces,
        per_step_timeout_s=float(section.per_step_timeout_s),
        whole_proof_timeout_s=float(section.timeout_s),
        name=cfg.name,
    )
    console.print(summary.model_dump())


@app.command()
def figure1(
    quick: Annotated[bool, typer.Option("--quick", help="small run for a smoke test")] = False,
    out_dir: Annotated[Path | None, typer.Option()] = None,
    hill_bands: Annotated[int, typer.Option(help="bootstrap resamples for Hill-plot bands")] = 0,
) -> None:
    """Reproduce Figure 1: the dichotomy on the heuristic-mixture model of Theorem 5."""
    from .config import TailEstimationConfig
    from .simulation.figure1 import run_figure_one

    cfg = (
        KestenConfig(
            n_traces=400,
            n_steps=32,
            burn_in=50,
            p_values=[0.0, 0.05],
            tail=TailEstimationConfig(bootstrap_resamples=50, double_bootstrap_resamples=50),
        )
        if quick
        else KestenConfig()
    )
    payload = run_figure_one(cfg, out_dir=out_dir or cfg.out_dir, bootstrap_hill_plot=hill_bands)
    _print_kesten_summary(payload)


def _print_kesten_summary(payload: dict) -> None:
    table = Table(title="Figure 1: order parameter against off-support rate", header_style="bold")
    for col in (
        "p",
        "alpha theory",
        "xi theory",
        "Hill [95% CI]",
        "moment",
        "GPD",
        "refuted",
        "top-1",
    ):
        table.add_column(col)
    for s in payload["settings"]:
        b = s["tail"]["bootstrap"]
        a = s["alpha_theory"]
        table.add_row(
            f"{s['p']:.2f}",
            "inf" if a is None else f"{a:.2f}",
            f"{s['xi_theory']:.4f}",
            f"{s['tail']['hill']:.4f} [{b['hill']['ci_low']:.4f}, {b['hill']['ci_high']:.4f}]",
            f"{s['tail']['moment']:+.4f}",
            f"{s['tail']['gpd']:+.4f}",
            str(s["n_refuted"]),
            f"{s['top1']:.3f}",
        )
    console.print(table)
    console.print(f"chance level for localisation: {payload['settings'][0]['chance']:.4f} = 1/L")


@app.command("lean-doctor")
def lean_doctor(
    workspace: Annotated[Path, typer.Option(help="the Lean workspace")] = Path("lean_workspace"),
) -> None:
    """Report whether the Lean toolchain, Mathlib and the REPL are usable."""
    from .lean import discover

    env = discover(workspace)
    table = Table(title="Lean toolchain", header_style="bold")
    table.add_column("item")
    table.add_column("value")
    for key, value in env.as_dict().items():
        if key == "problems":
            continue
        table.add_row(key, str(value))
    console.print(table)
    if env.available:
        console.print("[green]Lean is usable.[/green]")
    else:
        for problem in env.problems:
            console.print(f"[yellow]- {problem}[/yellow]")
        console.print("Run [bold]scripts/setup_lean.sh[/bold] to install it in user space.")
        raise typer.Exit(code=1)


@app.command("lean-verify")
def lean_verify(
    proofs: Annotated[Path, typer.Argument(help="JSONL of sampled proofs")],
    out_dir: Annotated[Path, typer.Option()] = Path("results/pilot/lean"),
    workspace: Annotated[Path, typer.Option()] = Path("lean_workspace"),
    max_traces: Annotated[int | None, typer.Option(help="verify at most this many")] = None,
    per_step_timeout: Annotated[float, typer.Option(help="seconds per tactic")] = 60.0,
) -> None:
    """Label every tactic of every sampled proof with the Lean 4 kernel (Appendix B.2)."""
    from .lean.batch import read_requests, verify_batch

    _, summary = verify_batch(
        read_requests(proofs),
        out_dir,
        workspace=workspace,
        max_traces=max_traces,
        per_step_timeout_s=per_step_timeout,
    )
    table = Table(title="Verification", header_style="bold")
    table.add_column("category")
    table.add_column("count", justify="right")
    for key, value in summary.model_dump().items():
        table.add_row(key, f"{value:.3f}" if isinstance(value, float) else str(value))
    console.print(table)


@app.command()
def report(
    out: Annotated[Path, typer.Option(help="where to write the report")] = Path(
        "reports/experimental_report.md"
    ),
) -> None:
    """Assemble the reproducible report from the metrics files present in the tree."""
    from .reporting.report import write_report

    path = write_report(".", out)
    console.print(f"wrote {path} ({path.stat().st_size} bytes)")


@app.command()
def show(
    metrics: Annotated[Path, typer.Argument(help="a metrics JSON written by a run")],
    key: Annotated[str | None, typer.Option(help="dotted path into the document")] = None,
) -> None:
    """Print a metrics file, or one key of it."""
    doc = json.loads(Path(metrics).read_text(encoding="utf-8"))
    if key:
        for part in key.split("."):
            doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    console.print_json(data=doc)


if __name__ == "__main__":  # pragma: no cover
    app()
