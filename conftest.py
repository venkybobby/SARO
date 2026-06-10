"""Root conftest — project-wide pytest hooks."""
from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config, items) -> None:
    """Tag every test under tests/ as part of the regression baseline.

    Lets future CI/local runs target the full functional+critical suite via
    `pytest -m regression` without having to hand-annotate each test function.
    New tests are covered automatically as soon as they're added under tests/.
    """
    rootdir = config.rootpath.as_posix()
    for item in items:
        rel = item.fspath.strpath.replace("\\", "/")
        if rel.startswith(rootdir):
            rel = rel[len(rootdir):].lstrip("/")
        if rel.startswith("tests/"):
            item.add_marker(pytest.mark.regression)


def pytest_sessionfinish(session, exitstatus: int) -> None:
    """Treat 'no tests collected' (exit 5) as success.

    The CI runs pytest with marker filters (-m unit, -m integration) before
    tests have all been explicitly marked.  Exit code 5 would fail those CI
    steps even though the full suite passes.  This hook downgrades 5 → 0 so
    marker-filtered runs that collect nothing still exit cleanly.
    """
    if exitstatus == 5:
        session.exitstatus = 0
