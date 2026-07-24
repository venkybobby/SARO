"""STORY-TAB-006: the rule-pack DETAIL endpoint must include the rules array.

Pre-fix, `get_pack_by_name` returned the same summary dict as the list
(rule_count but no rules), so GET /api/v1/rules/packs/{framework} could never
show an auditor which rules a pack applies — the transparency surface was
count-only.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from auth import get_current_user
from main import app
from services.rule_service import get_pack_by_name, list_rule_packs

pytestmark = [pytest.mark.unit]


def _user():
    class _U:
        pass

    u = _U()
    u.id = uuid.uuid4()
    u.role = "operator"
    u.persona_role = None
    u.tenant_id = uuid.uuid4()
    u.is_active = True
    u.read_only = False
    u.email = "u@t.test"
    return u


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def test_get_pack_by_name_includes_rules():
    """AC-2 (service): the detail lookup returns the full rules list."""
    packs = list_rule_packs()
    assert packs, "no rule packs on disk — fixture assumption broken"
    target = packs[0]
    detail = get_pack_by_name(target["framework"])
    assert detail is not None
    assert isinstance(detail.get("rules"), list)
    assert len(detail["rules"]) == target["rule_count"], (
        "detail rules must match the list's rule_count"
    )
    # summary fields still present (additive change, not a shape swap)
    for key in ("name", "version", "framework", "rule_count"):
        assert key in detail


def test_detail_endpoint_serves_rules():
    """AC-2 (HTTP): /api/v1/rules/packs/{framework} includes rules."""
    app.dependency_overrides[get_current_user] = lambda: _user()
    client = TestClient(app, raise_server_exceptions=False)
    framework = list_rule_packs()[0]["framework"]
    resp = client.get(f"/api/v1/rules/packs/{framework}")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("rules"), list) and body["rules"], (
        "detail endpoint must carry the pack's rules"
    )
    first = body["rules"][0]
    assert "id" in first or "description" in first or "name" in first


def test_list_endpoint_stays_light():
    """The LIST endpoint keeps rule_count without inlining rules (unchanged)."""
    app.dependency_overrides[get_current_user] = lambda: _user()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/rules/packs")
    assert resp.status_code == 200
    for pack in resp.json()["packs"]:
        assert "rule_count" in pack
        assert "rules" not in pack
