"""STORY-110: Compliance Lead can access Reports, and backend authz agrees with the nav.

Backend Reports endpoints historically gated on require_role("super_admin","operator")
(the `role` axis), while the React nav gates on `persona_role`. compliance_lead had
neither the tab nor backend access. The fix introduces a single Reports allow-list
admitting the super_admin/operator roles (legacy, unchanged) AND the
compliance_lead/risk_officer/admin/super_admin personas that surface the Reports tab,
so the two sides agree without removing anyone's existing access.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

_ROOT = Path(__file__).parent.parent


def _user(role: str, persona: str | None):
    return SimpleNamespace(role=role, persona_role=persona)


@pytest.mark.unit
def test_compliance_lead_persona_is_allowed_reports():
    from routers.reports import _require_reports_access

    user = _user(role="viewer", persona="compliance_lead")
    assert asyncio.run(_require_reports_access(user)) is user


@pytest.mark.unit
def test_legacy_roles_still_allowed():
    from routers.reports import _require_reports_access

    for role in ("super_admin", "operator"):
        u = _user(role=role, persona=None)
        assert asyncio.run(_require_reports_access(u)) is u, f"{role} must keep Reports access"


@pytest.mark.unit
def test_unprivileged_persona_and_role_is_denied():
    from routers.reports import _require_reports_access

    u = _user(role="viewer", persona="operator")  # operator persona has no Reports tab
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_require_reports_access(u))
    assert exc.value.status_code == 403


@pytest.mark.unit
def test_frontend_nav_grants_compliance_lead_reports():
    src = (_ROOT / "frontend" / "src" / "components" / "Sidebar.jsx").read_text(encoding="utf-8")
    # crude block extraction: compliance_lead: [ ... ] up to the closing bracket
    start = src.index("compliance_lead:")
    block = src[start : src.index("]", start)]
    assert '"reports"' in block, "compliance_lead PERSONA_TABS must include the reports tab"


@pytest.mark.unit
def test_reports_persona_allowlist_matches_frontend_tab_personas():
    """AC-4: the backend persona allow-list equals the personas whose nav shows Reports."""
    from routers.reports import _REPORTS_PERSONAS

    src = (_ROOT / "frontend" / "src" / "components" / "Sidebar.jsx").read_text(encoding="utf-8")
    # personas (keys of PERSONA_TABS) whose array contains "reports"
    import re

    fe_personas = set()
    for m in re.finditer(r"(\w+):\s*\[(.*?)\]", src, re.S):
        if '"reports"' in m.group(2):
            fe_personas.add(m.group(1))
    # operator/super_admin may also reach Reports via the role axis; compare the persona set.
    assert set(_REPORTS_PERSONAS) == fe_personas, (
        f"backend Reports personas {set(_REPORTS_PERSONAS)} must match nav personas {fe_personas}"
    )
