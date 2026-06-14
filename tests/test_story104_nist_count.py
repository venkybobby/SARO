"""STORY-104: the NIST coverage map's asserted count must match its real size.

The code claimed "All 72 NIST AI RMF 1.0 subcategory IDs" while the map defines
68. SARO maps a subset; it must not overstate coverage. Pin the actual size and
that no "72" overclaim remains.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent


@pytest.mark.unit
def test_nist_coverage_map_has_68_entries():
    from routers.reports import _NIST_COVERAGE_MAP

    assert len(_NIST_COVERAGE_MAP) == 68, (
        f"expected SARO to map 68 NIST subcategories, found {len(_NIST_COVERAGE_MAP)} — "
        "update the comment/docstring count if this intentionally changed"
    )


@pytest.mark.unit
def test_reports_source_does_not_overclaim_72():
    src = (_ROOT / "routers" / "reports.py").read_text(encoding="utf-8")
    assert "72 NIST AI RMF" not in src, "must not claim 72 NIST subcategories (map has 68)"
    assert "all 72" not in src.lower(), "must not claim 'all 72' NIST subcategory outcomes"
