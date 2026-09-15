#!/usr/bin/env python3
"""Regenerate docs/system_report.md from the live machine.

    uv run python scripts/doctor.py            # print
    uv run python scripts/doctor.py --write    # rewrite docs/system_report.md

The verdict section is derived, not hand-written: what the machine lacks determines which parts
of the paper's protocol can run here, and `docs/experimental_specification.md` section 8 reads
from this file.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

TOOLS = [
    "python3",
    "git",
    "uv",
    "cmake",
    "ninja",
    "gh",
    "elan",
    "lean",
    "lake",
    "sbatch",
    "srun",
    "sinfo",
    "docker",
    "apptainer",
    "singularity",
    "nvidia-smi",
    "nvcc",
]


def _cmd(args: list[str]) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=20, check=False)
        return (out.stdout or out.stderr).strip().splitlines()[0] if out.returncode == 0 else "-"
    except (OSError, subprocess.SubprocessError, IndexError):
        return "-"


def build_report() -> str:
    from onebigjump.reproducibility import hardware_info, package_versions

    hw = hardware_info()
    found = {t: shutil.which(t) for t in TOOLS}
    pkgs = package_versions()

    lines = [
        "# System report",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} on `{platform.node()}`.",
        "Regenerate with `uv run python scripts/doctor.py --write`.",
        "",
        "## Platform",
        "",
        "```",
        f"platform       : {hw['platform']}",
        f"machine        : {hw['machine']}",
        f"cpu cores      : {hw['cpu_count']}",
        f"RAM (GB)       : {hw.get('ram_gb', '?')}",
        f"python         : {hw['python']}",
        "```",
        "",
        "## Toolchain",
        "",
        "```",
    ]
    for tool, path in found.items():
        lines.append(f"{tool:<14} {path or 'NOT FOUND'}")
    lines += [
        "```",
        "",
        "## Project Python environment",
        "",
        "```",
        *(f"{name:<14} {ver}" for name, ver in sorted(pkgs.items())),
        "",
        f"torch.cuda.is_available        : {hw.get('cuda_available')}",
        f"torch.backends.mps.is_available: {hw.get('mps_available')}",
        f"GPUs                           : {hw.get('gpus')}",
        "```",
        "",
        "## Credentials",
        "",
        "```",
        f"gh auth status : {_cmd(['gh', 'auth', 'status'])}",
        f"HF token file  : {'present' if (Path.home() / '.cache/huggingface/token').is_file() else 'absent'}",
        "```",
        "",
        "## Verdict",
        "",
    ]

    cuda = bool(hw.get("cuda_available"))
    lean = found["lake"] is not None
    slurm = found["sbatch"] is not None
    ram = float(hw.get("ram_gb", 0))

    lines += [
        "| Resource | Status |",
        "|---|---|",
        f"| OS | {hw['platform']} |",
        f"| CPU | {hw['cpu_count']} cores |",
        f"| RAM | {ram:.1f} GB |",
        f"| GPU / CUDA | {'CUDA available' if cuda else '**no CUDA**'} |",
        f"| MPS | {hw.get('mps_available')} |",
        f"| Slurm | {'present' if slurm else '**absent**'} |",
        f"| Lean | {'present' if lean else '**absent**'} |",
        f"| GitHub CLI | {'present' if found['gh'] else 'absent'} |",
        "",
        "### What this machine can run",
        "",
    ]
    verdicts = [
        ("Kesten simulation and Figure 1", True, "pure NumPy"),
        ("Tail estimators, bootstrap, tests", True, "CPU"),
        ("Lean 4 + Mathlib step replay", lean, "install elan in user space" if not lean else ""),
        ("Modular-addition grokking (P4)", True, "small model; MPS or CPU"),
        ("Synthetic deduction on 7-8B models", ram >= 32 or cuda, "16 GB is marginal for bf16"),
        ("Lean prover traces from 7-8B provers", cuda, "needs CUDA at the paper's scale"),
        ("Slurm dispatch", slurm, ""),
    ]
    lines += ["| Stage | Feasible | Note |", "|---|---|---|"]
    for name, ok, note in verdicts:
        lines.append(f"| {name} | {'yes' if ok else '**no**'} | {note} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="rewrite docs/system_report.md")
    args = ap.parse_args()
    report = build_report()
    if args.write:
        target = REPO / "docs" / "system_report.md"
        target.write_text(report, encoding="utf-8")
        print(f"wrote {target}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
