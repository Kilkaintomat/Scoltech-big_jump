"""A supported 64-bit experiment seed must allow deterministic Python children."""

import os
import subprocess
import sys

import pytest

from onebigjump.reproducibility import seed_everything


@pytest.mark.parametrize("seed", [0, 2**32, 2**63 - 1])
def test_large_experiment_seed_allows_python_children(seed, monkeypatch):
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    assert seed_everything(seed) == seed
    command = [sys.executable, "-c", "print(hash('onebigjump-child-check'))"]
    first = subprocess.run(command, env=dict(os.environ), capture_output=True, text=True)
    second = subprocess.run(command, env=dict(os.environ), capture_output=True, text=True)
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
