"""Shared fixtures and the toolchain gates for the optional markers."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip `lean` and `ml` tests when the toolchain they need is absent.

    They are skipped, never silently passed: a run that could not check the Lean labels must not
    look like a run that checked them.
    """
    from onebigjump.lean import discover

    lean_env = discover(REPO / "lean_workspace")
    lean_skip = pytest.mark.skip(reason=f"Lean unavailable: {'; '.join(lean_env.problems)}")

    try:
        import torch  # noqa: F401

        torch_ok = True
    except ImportError:  # pragma: no cover
        torch_ok = False
    ml_skip = pytest.mark.skip(reason="torch is not installed")

    for item in items:
        if "lean" in item.keywords and not lean_env.available:
            item.add_marker(lean_skip)
        if "ml" in item.keywords and not torch_ok:
            item.add_marker(ml_skip)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def lean_env():
    from onebigjump.lean import discover

    return discover(REPO / "lean_workspace")
