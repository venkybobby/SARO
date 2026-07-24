"""FND-084: CI must install the validated, pinned ruff version.

Unpinned `pip install ruff` in three workflows meant a new ruff release
changed rule behavior overnight: PR #128's Lint job reported 1491 errors in
files the PR never touched, and the quality ratchet's ruff-count gate
(baseline 0) failed with the same number — while the locally validated ruff
(0.15.15) reported zero. Same failure class as FND-069 (unpinned
fastapi/starlette). CI must install the exact version the repo is validated
against; bumping it is a deliberate commit that revalidates the tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.unit]

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _ruff_install_lines():
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for i, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            if "pip install" in line and re.search(r"\bruff\b", line):
                yield wf.name, i, line


def test_every_ci_ruff_install_is_pinned():
    offenders = [
        f"{name}:{lineno}: {line.strip()}"
        for name, lineno, line in _ruff_install_lines()
        if not re.search(r"ruff==\d+\.\d+\.\d+", line)
    ]
    assert not offenders, (
        "unpinned ruff install(s) in CI — a new ruff release will diverge from "
        "the locally validated version (FND-084):\n" + "\n".join(offenders)
    )


def test_ci_actually_installs_ruff_somewhere():
    """Guard the guard: if the install lines vanish entirely, the pin test
    above would pass vacuously while CI silently stopped linting."""
    assert list(_ruff_install_lines()), "expected CI workflows to install ruff"
