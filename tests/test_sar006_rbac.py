"""
SAR-006 RBAC test suite — 10 tests covering persona_required, tab registry,
persona tab mapping, and PersonaPermission model fields.
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


# ── Helpers ───────────────────────────────────────────────────────────────────

_FRONTEND_APP = Path(__file__).parent.parent / "frontend" / "app.py"


def _load_app_vars():
    """
    Extract _TAB_REGISTRY keys and _PERSONA_TABS persona→tabs mapping from
    frontend/app.py using ast (handles both Assign and AnnAssign nodes).
    Returns (tab_registry_keys: set, persona_tabs: dict[str, list[str]]).
    """
    source = _FRONTEND_APP.read_text(encoding="utf-8")
    tree = ast.parse(source)

    tab_registry_node = None
    persona_tabs_node = None

    for node in ast.walk(tree):
        # Handle both `x = {...}` (Assign) and `x: T = {...}` (AnnAssign)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    if t.id == "_TAB_REGISTRY":
                        tab_registry_node = node.value
                    elif t.id == "_PERSONA_TABS":
                        persona_tabs_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_TAB_REGISTRY":
                tab_registry_node = node.value
            elif node.target.id == "_PERSONA_TABS":
                persona_tabs_node = node.value

    # Extract just the string keys from the dict nodes
    def _dict_str_keys(dict_node) -> set[str] | None:
        if dict_node is None or not isinstance(dict_node, ast.Dict):
            return None
        keys: set[str] = set()
        for k in dict_node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.add(k.value)
        return keys or None

    # Extract persona_tabs: dict[persona_str → list[str]]
    def _dict_str_list(dict_node) -> dict[str, list[str]] | None:
        if dict_node is None or not isinstance(dict_node, ast.Dict):
            return None
        result: dict[str, list[str]] = {}
        for k, v in zip(dict_node.keys, dict_node.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            if isinstance(v, ast.List):
                tabs = [
                    elt.value for elt in v.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
                result[k.value] = tabs
        return result or None

    return _dict_str_keys(tab_registry_node), _dict_str_list(persona_tabs_node)


# ── Test 1 ────────────────────────────────────────────────────────────────────

def test_persona_required_raises_403_for_wrong_persona():
    """persona_required should raise HTTPException 403 when persona does not match."""
    import asyncio
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from auth import persona_required

    mock_user = MagicMock()
    mock_user.persona_role = "ai_auditor"
    mock_user.is_active = True

    dep_fn = persona_required("compliance_lead", "admin")

    async def _run():
        # Patch get_current_user dependency by calling _check directly
        from fastapi import HTTPException as _HTTPException
        with pytest.raises(_HTTPException) as exc_info:
            await dep_fn(current_user=mock_user)
        assert exc_info.value.status_code == 403

    asyncio.run(_run())


# ── Test 2 ────────────────────────────────────────────────────────────────────

def test_persona_required_passes_for_correct_persona():
    """persona_required returns the user unchanged when persona matches."""
    import asyncio
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from auth import persona_required

    mock_user = MagicMock()
    mock_user.persona_role = "compliance_lead"
    mock_user.is_active = True

    dep_fn = persona_required("compliance_lead")

    async def _run():
        result = await dep_fn(current_user=mock_user)
        assert result is mock_user

    asyncio.run(_run())


# ── Test 3 ────────────────────────────────────────────────────────────────────

def test_tab_registry_has_required_keys():
    """_TAB_REGISTRY must contain the six core tab IDs."""
    tab_registry, _ = _load_app_vars()
    assert tab_registry is not None, "_TAB_REGISTRY could not be parsed from frontend/app.py"
    required = {"dashboard", "compliance_hub", "trace_view", "risk_summary", "rule_packs", "remediation"}
    missing = required - tab_registry  # tab_registry is already a set of key strings
    assert not missing, f"_TAB_REGISTRY is missing keys: {missing}"


# ── Test 4 ────────────────────────────────────────────────────────────────────

def test_compliance_lead_tabs_include_compliance_hub():
    """compliance_lead persona must have access to the compliance_hub tab."""
    _, persona_tabs = _load_app_vars()
    assert persona_tabs is not None, "_PERSONA_TABS could not be parsed from frontend/app.py"
    assert "compliance_hub" in persona_tabs["compliance_lead"], (
        "compliance_hub not found in compliance_lead tabs"
    )


# ── Test 5 ────────────────────────────────────────────────────────────────────

def test_risk_officer_tabs_do_not_include_rule_packs():
    """risk_officer persona must NOT have access to rule_packs."""
    _, persona_tabs = _load_app_vars()
    assert persona_tabs is not None
    assert "rule_packs" not in persona_tabs["risk_officer"], (
        "rule_packs should not be accessible to risk_officer"
    )


# ── Test 6 ────────────────────────────────────────────────────────────────────

def test_ai_auditor_tabs_include_rule_packs():
    """ai_auditor persona must have access to rule_packs."""
    _, persona_tabs = _load_app_vars()
    assert persona_tabs is not None
    assert "rule_packs" in persona_tabs["ai_auditor"], (
        "rule_packs not found in ai_auditor tabs"
    )


# ── Test 7 ────────────────────────────────────────────────────────────────────

def test_ai_auditor_tabs_do_not_include_claims_matrix():
    """ai_auditor persona must NOT have access to claims_matrix."""
    _, persona_tabs = _load_app_vars()
    assert persona_tabs is not None
    assert "claims_matrix" not in persona_tabs["ai_auditor"], (
        "claims_matrix should not be accessible to ai_auditor"
    )


# ── Test 8 ────────────────────────────────────────────────────────────────────

def test_persona_service_get_persona_permissions_returns_dict():
    """get_persona_role + PERSONA_PERMISSIONS lookup returns a dict with 'tabs' key."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from services.persona_service import get_persona_role, PERSONA_PERMISSIONS

    mock_user = MagicMock()
    mock_user.persona_role = "compliance_lead"
    mock_user.role = "operator"

    persona = get_persona_role(mock_user)
    perms = PERSONA_PERMISSIONS.get(persona)

    assert perms is not None, f"No permissions found for persona '{persona}'"
    assert "tabs" in perms, "Permissions dict must contain 'tabs' key"
    assert isinstance(perms["tabs"], list)


# ── Test 9 ────────────────────────────────────────────────────────────────────

def test_persona_permissions_model_has_required_fields():
    """PersonaPermission SQLAlchemy model must declare persona_role, allowed_tabs, allowed_actions."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import PersonaPermission

    mapper = PersonaPermission.__mapper__
    col_names = {c.key for c in mapper.columns}
    for field in ("persona_role", "allowed_tabs", "allowed_actions"):
        assert field in col_names, f"PersonaPermission is missing column: {field}"


# ── Test 10 ───────────────────────────────────────────────────────────────────

def test_require_role_raises_403_for_insufficient_role():
    """require_role should raise HTTPException 403 when user role doesn't match."""
    import asyncio
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
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
