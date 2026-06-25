"""STORY-TRACE-003: AI Auditor / Compliance Lead read access to TRACE evidence.

The TRACE View is the AI Auditor's primary screen, yet the endpoints it needs were
gated to roles those personas don't hold:
  - `/api/v1/audits/{id}` (audit detail)   → require_role("super_admin","operator")
  - `/api/v1/audits`      (recent list)     → + "demo_viewer"
  - `/api/v1/audit/{id}/trace` (timeline)   → ungated (any authenticated user)

An `ai_auditor` / `compliance_lead` persona on a non-operator role got 403 on detail
and list. This pins the fix: a reusable role-OR-persona allow-list grants those
personas read access to the timeline, audit detail and audit list — read-only,
tenant-scoped — while denying unrelated roles/personas and leaving mutation routes
(e.g. POST /traces/{id}/remediate) denied.

Reconciliation note (owner decision, FND-025 vs FND-028): a later story (CHUB-002 /
FND-025) granted the Compliance Hub buyer personas (`risk_officer`, `admin`) read
access to the audits *LIST* only. They remain denied on the TRACE detail/timeline
endpoints (least privilege), so `risk_officer` is no longer a blanket-denied case
here — see ``test_buyer_personas_list_only`` below.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Base, get_db
from main import app
from models import Audit, Tenant

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
AUDIT_A = uuid.uuid4()
AUDIT_B = uuid.uuid4()


def _seed() -> None:
    db = _Session()
    db.add(Tenant(id=TENANT_A, name="A", slug="trace003-a"))
    db.add(Tenant(id=TENANT_B, name="B", slug="trace003-b"))
    for aid, tid in ((AUDIT_A, TENANT_A), (AUDIT_B, TENANT_B)):
        db.add(
            Audit(
                id=aid,
                tenant_id=tid,
                dataset_name="scan",
                sample_count=50,
                status="completed",
            )
        )
    db.commit()
    db.close()


_seed()


def _user(role, persona, tenant_id=TENANT_A, read_only=False):
    class _U:
        pass

    u = _U()
    u.id = uuid.uuid4()
    u.role = role
    u.persona_role = persona
    u.tenant_id = tenant_id
    u.is_active = True
    u.read_only = read_only
    u.email = "u@t.test"
    return u


def _client_as(user) -> TestClient:
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


# Personas whose JOB is trace inspection — granted read access by this story.
# role is deliberately NOT in {super_admin, operator} so the test proves the
# *persona* grants access, not a privileged role.
_PERMITTED = [
    ("viewer", "ai_auditor"),
    ("viewer", "compliance_lead"),
]
# Neither a trace-read role nor any audit-reader persona — denied on ALL three.
_DENIED = [
    ("viewer", None),
]
# FND-025 reconciliation: buyer personas read the audits LIST but stay denied on
# the TRACE detail/timeline endpoints (least privilege).
_LIST_ONLY = [
    ("viewer", "risk_officer"),
    ("viewer", "admin"),
]


@pytest.mark.parametrize("role,persona", _PERMITTED)
def test_permitted_personas_read_timeline(role, persona):
    """AC-1: ai_auditor / compliance_lead can read the timeline endpoint."""
    resp = _client_as(_user(role, persona)).get(f"/api/v1/audit/{AUDIT_A}/trace")
    assert resp.status_code == 200, (
        f"{persona} blocked from timeline: {resp.status_code}"
    )


@pytest.mark.parametrize("role,persona", _PERMITTED)
def test_permitted_personas_read_audit_detail(role, persona):
    """AC-2: permitted personas pass the audit-detail gate (404 for missing report is fine)."""
    resp = _client_as(_user(role, persona)).get(f"/api/v1/audits/{AUDIT_A}")
    assert resp.status_code != 403, f"{persona} blocked from audit detail (403)"
    assert resp.status_code != 401


@pytest.mark.parametrize("role,persona", _PERMITTED)
def test_permitted_personas_read_audits_list(role, persona):
    """AC-3: permitted personas can list audits (own tenant)."""
    resp = _client_as(_user(role, persona)).get("/api/v1/audits")
    assert resp.status_code == 200, (
        f"{persona} blocked from audits list: {resp.status_code}"
    )


@pytest.mark.parametrize("role,persona", _DENIED)
def test_unprivileged_role_and_persona_denied(role, persona):
    """AC-5: a role not in the permitted set still receives 403 on all three."""
    client = _client_as(_user(role, persona))
    assert client.get(f"/api/v1/audit/{AUDIT_A}/trace").status_code == 403
    assert client.get(f"/api/v1/audits/{AUDIT_A}").status_code == 403
    assert client.get("/api/v1/audits").status_code == 403


@pytest.mark.parametrize("role,persona", _LIST_ONLY)
def test_buyer_personas_list_only(role, persona):
    """FND-025 reconciliation: risk_officer/admin read the audits LIST (CHUB-002)
    but stay denied on the TRACE detail + timeline endpoints (least privilege)."""
    client = _client_as(_user(role, persona))
    assert client.get("/api/v1/audits").status_code == 200
    assert client.get(f"/api/v1/audit/{AUDIT_A}/trace").status_code == 403
    assert client.get(f"/api/v1/audits/{AUDIT_A}").status_code == 403


def test_legacy_roles_and_demo_viewer_preserved():
    """AC-3 / regression: operator and demo_viewer keep audits-list access."""
    assert _client_as(_user("operator", None)).get("/api/v1/audits").status_code == 200
    assert (
        _client_as(_user("demo_viewer", "compliance_lead", read_only=True))
        .get("/api/v1/audits")
        .status_code
        == 200
    )


def test_read_only_persona_cannot_remediate():
    """Edge: trace read access must NOT grant the remediation mutation route."""
    resp = _client_as(_user("viewer", "ai_auditor")).post(
        f"/api/v1/traces/{AUDIT_A}/{uuid.uuid4()}/remediate",
        json={"notes": "x"},
    )
    assert resp.status_code == 403, (
        f"read-only ai_auditor reached the remediate mutation route: {resp.status_code}"
    )


def test_permitted_persona_stays_tenant_scoped():
    """AC-4: an auditor of tenant A cannot read tenant B's trace."""
    resp = _client_as(_user("viewer", "ai_auditor", tenant_id=TENANT_A)).get(
        f"/api/v1/audit/{AUDIT_B}/trace"
    )
    assert resp.status_code == 404
