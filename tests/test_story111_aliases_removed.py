"""STORY-111: duplicate nav/route aliases are removed in favour of one canonical path.

Backend: the rule_packs _alias_router (/api/v1/rule-packs, /api/v1/drift/alerts) and
the Streamlit-only /drift-check are gone; the React client uses the canonical
/api/v1/rules/* paths. Frontend: the evidence_export nav alias (rendered TraceView)
is removed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent


@pytest.mark.unit
def test_backend_alias_router_removed():
    src = (_ROOT / "routers" / "rule_packs.py").read_text(encoding="utf-8")
    assert "_alias_router" not in src, "rule_packs _alias_router must be removed"
    assert "drift-check" not in src, "the Streamlit-only /drift-check alias must be removed"


@pytest.mark.unit
def test_main_no_longer_registers_alias_router():
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    assert "rule_packs_alias_router" not in src, "main.py must not import/register the alias router"


@pytest.mark.unit
def test_evidence_export_nav_alias_removed():
    src = (_ROOT / "frontend" / "src" / "components" / "Sidebar.jsx").read_text(encoding="utf-8")
    assert "evidence_export" not in src, "evidence_export nav alias must be removed"


@pytest.mark.unit
def test_react_client_uses_canonical_rule_paths():
    pages = _ROOT / "frontend" / "src" / "pages"
    rule_packs = (pages / "RulePacks.jsx").read_text(encoding="utf-8")
    drift = (pages / "DriftAlerts.jsx").read_text(encoding="utf-8")
    dash = (pages / "Dashboard.jsx").read_text(encoding="utf-8")

    assert "/api/v1/rule-packs" not in rule_packs and "/api/v1/rules/packs" in rule_packs
    for f in (drift, dash):
        assert "/api/v1/drift/alerts" not in f, "must not call the /drift/alerts alias"
        assert "/api/v1/rules/drift-alerts" in f, "must call the canonical drift path"
