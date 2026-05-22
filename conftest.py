"""Root conftest — project-wide pytest hooks."""
from __future__ import annotations


def pytest_sessionfinish(session, exitstatus: int) -> None:
    """Treat 'no tests collected' (exit 5) as success.

    The CI runs pytest with marker filters (-m unit, -m integration) before
    tests have all been explicitly marked.  Exit code 5 would fail those CI
    steps even though the full suite passes.  This hook downgrades 5 → 0 so
    marker-filtered runs that collect nothing still exit cleanly.
    """
    if exitstatus == 5:
        session.exitstatus = 0
