"""STORY-413 AC-4: CI guard fences hardcoded placeholder KPI tiles from
regenerating on the Dashboard.
"""
from pathlib import Path

import pytest

from scripts.check_no_placeholder_kpi_tiles import _PLACEHOLDER_FLAG, _STALE_CAPTION, main

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent


def test_guard_passes_on_current_dashboard():
    assert main() == 0


def test_dashboard_has_no_placeholder_flag():
    text = (ROOT / "frontend" / "src" / "pages" / "Dashboard.jsx").read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if _PLACEHOLDER_FLAG.search(line):
            pytest.fail(f"Dashboard.jsx:{i} still has a placeholder: true tile: {line.strip()}")


def test_dashboard_has_no_stale_caption():
    text = (ROOT / "frontend" / "src" / "pages" / "Dashboard.jsx").read_text(encoding="utf-8")
    assert _STALE_CAPTION not in text


def test_guard_fails_on_a_synthetic_regression(tmp_path, monkeypatch):
    """Red/green check on the guard itself: point it at a file that DOES
    contain a placeholder tile and confirm it fails."""
    import scripts.check_no_placeholder_kpi_tiles as guard

    fake = tmp_path / "Dashboard.jsx"
    fake.write_text('{ label: "Fake", value: 1, placeholder: true }', encoding="utf-8")
    monkeypatch.setattr(guard, "DASHBOARD", fake)
    assert guard.main() == 1
