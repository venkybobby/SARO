"""
SAR-006 RBAC test suite — persona_required, persona tab mapping, and
PersonaPermission model fields.

STORY-105: the persona→tab assertions were repointed from the (now-removed)
Streamlit frontend/app.py to services.persona_service.PERSONA_PERMISSIONS, the
authoritative source of truth, so the RBAC coverage survives the Streamlit removal.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))


def _persona_tabs() -> dict[str, list[str]]:
    from services.persona_service import PERSONA_PERMISSIONS

    return {role: perm.get("tabs", []) for role, perm in PERSONA_PERMISSIONS.items()}


# ── persona_required / require_role ──────────────────────────────────────────

def test_persona_required_raises_403_for_wrong_persona():
    """persona_required should raise HTTPException 403 when persona does not match."""
    import asyncio
    from auth import persona_required

    mock_user = MagicMock()
    mock_user.persona_role = "ai_auditor"
    mock_user.is_active = True

    dep_fn = persona_required("compliance_lead", "admin")

    async def _run():
        with pytest.raises(HTTPException) as exc_info:
            await dep_fn(current_user=mock_user)
        assert exc_info.value.status_code == 403

    asyncio.run(_run())


def test_persona_required_passes_for_correct_persona():
    """persona_required returns the user unchanged when persona matches."""
    import asyncio
    from auth import persona_required

    mock_user = MagicMock()
    mock_user.persona_role = "compliance_lead"
    mock_user.is_active = True

    dep_fn = persona_required("compliance_lead")

    async def _run():
        result = await dep_fn(current_user=mock_user)
        assert result is mock_user

    asyncio.run(_run())


# ── persona → tab mapping (source of truth: persona_service) ──────────────────

def test_core_tabs_are_covered_across_personas():
    """The union of persona tabs must include the six core tab IDs."""
    union = {t for tabs in _persona_tabs().values() for t in tabs}
    required = {"dashboard", "compliance_hub", "trace_view", "risk_summary", "rule_packs", "remediation"}
    missing = required - union
    assert not missing, f"core tabs missing from all persona mappings: {missing}"


def test_compliance_lead_tabs_include_compliance_hub():
    assert "compliance_hub" in _persona_tabs()["compliance_lead"]


def test_risk_officer_tabs_do_not_include_rule_packs():
    assert "rule_packs" not in _persona_tabs()["risk_officer"]


def test_ai_auditor_tabs_include_rule_packs():
    assert "rule_packs" in _persona_tabs()["ai_auditor"]


def test_ai_auditor_tabs_do_not_include_claims_matrix():
    assert "claims_matrix" not in _persona_tabs()["ai_auditor"]


# ── persona_service / model ───────────────────────────────────────────────────

def test_persona_service_get_persona_permissions_returns_dict():
    """get_persona_role + PERSONA_PERMISSIONS lookup returns a dict with 'tabs' key."""
    from services.persona_service import get_persona_role, PERSONA_PERMISSIONS

    mock_user = MagicMock()
    mock_user.persona_role = "compliance_lead"
    mock_user.role = "operator"

    persona = get_persona_role(mock_user)
    perms = PERSONA_PERMISSIONS.get(persona)

    assert perms is not None, f"No permissions found for persona '{persona}'"
    assert "tabs" in perms, "Permissions dict must contain 'tabs' key"
    assert isinstance(perms["tabs"], list)


def test_persona_permissions_model_has_required_fields():
    """PersonaPermission SQLAlchemy model must declare persona_role, allowed_tabs, allowed_actions."""
    from models import PersonaPermission

    mapper = PersonaPermission.__mapper__
    col_names = {c.key for c in mapper.columns}
    for field in ("persona_role", "allowed_tabs", "allowed_actions"):
        assert field in col_names, f"PersonaPermission is missing column: {field}"


def test_require_role_raises_403_for_insufficient_role():
    """require_role should raise HTTPException 403 when user role doesn't match."""
    import asyncio
    from auth import require_role

    mock_user = MagicMock()
    mock_user.role = "operator"
    mock_user.is_active = True

    dep_fn = require_role("super_admin")

    async def _run():
        with pytest.raises(HTTPException) as exc_info:
            await dep_fn(current_user=mock_user)
        assert exc_info.value.status_code == 403

    asyncio.run(_run())
