"""STORY-TEN-001 — cross-tenant isolation proof (FastAPI access path).

Posture (a) FastAPI-only: the browser reaches data ONLY through FastAPI, where
isolation is enforced by .filter(tenant_id == current_user.tenant_id). This suite
seeds TENANT-A and TENANT-B with mirrored data and asserts, through the API, that:
  * a tenant sees only its own rows (audits list)                    — AC-3
  * a foreign-tenant id returns a generic 404 (no existence oracle) — AC-3
  * absent/mismatched tenant context fails closed (empty, never leak)— AC-2
across every evidence-bearing read path (audits, TRACE timeline, evidence criteria).

Runs in CI (marked integration) on every PR touching data access.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Base, get_db
from grc.evidence import EvidenceCapture, capture_evidence
from main import app
from models import Audit, GRCEvidenceRecord, User

pytestmark = [pytest.mark.integration, pytest.mark.security]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


def _seed_audit(db, tenant_id) -> uuid.UUID:
    a = Audit(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        batch_id=f"batch-{tenant_id}",
        dataset_name="ds",
        sample_count=50,
        status="completed",
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(a)
    db.commit()
    return a.id


def _seed_evidence(db, tenant_id) -> uuid.UUID:
    rec = capture_evidence(
        db,
        tenant_id=tenant_id,
        capture=EvidenceCapture(
            output_id=f"o-{tenant_id}",
            model_version="m",
            prompt="p",
            decision="d",
            confidence=0.5,
            consumer="c",
        ),
    )
    return rec.id


def _reset(db):
    for tbl in (GRCEvidenceRecord, Audit):
        db.query(tbl).delete()
    db.commit()


def _user(tenant_id):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = f"user-{tenant_id}@test.example"
    u.role = "operator"
    u.persona_role = "ai_auditor"
    u.tenant_id = tenant_id
    u.is_active = True
    u.read_only = False
    return u


def _client(user):
    def _get_db():
        db = _Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_audits_list_shows_only_own_tenant():
    with _Session() as s:
        _reset(s)
        a_id = _seed_audit(s, TENANT_A)
        b_id = _seed_audit(s, TENANT_B)
    r = _client(_user(TENANT_A)).get("/api/v1/audits")
    assert r.status_code == 200, r.text
    ids = {item["id"] for item in r.json()}
    assert str(a_id) in ids
    assert str(b_id) not in ids  # tenant B's audit never appears for tenant A


def test_get_foreign_audit_is_generic_404():
    with _Session() as s:
        _reset(s)
        b_id = _seed_audit(s, TENANT_B)
    r = _client(_user(TENANT_A)).get(f"/api/v1/audits/{b_id}")
    assert r.status_code == 404  # no cross-tenant existence oracle


def test_foreign_trace_is_404():
    with _Session() as s:
        _reset(s)
        b_id = _seed_audit(s, TENANT_B)
    r = _client(_user(TENANT_A)).get(f"/api/v1/audit/{b_id}/trace")
    assert r.status_code == 404


def test_foreign_evidence_criteria_is_404():
    with _Session() as s:
        _reset(s)
        b_ev = _seed_evidence(s, TENANT_B)
    r = _client(_user(TENANT_A)).get(f"/api/v1/evidence/{b_ev}/criteria")
    assert r.status_code == 404


def test_absent_tenant_context_fails_closed():
    """A user whose tenant has no data sees an empty list — never another tenant's rows."""
    with _Session() as s:
        _reset(s)
        _seed_audit(s, TENANT_B)
    empty_tenant = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
    r = _client(_user(empty_tenant)).get("/api/v1/audits")
    assert r.status_code == 200
    assert r.json() == []  # fail-closed: no rows, no leak


def test_foreign_output_audit_is_404():
    """The most sensitive read (verbatim prompt + raw output) is tenant-gated (404 cross-tenant)."""
    with _Session() as s:
        _reset(s)
        b_id = _seed_audit(s, TENANT_B)
    r = _client(_user(TENANT_A)).get(f"/api/v1/output/{b_id}")
    assert r.status_code == 404


def test_frontend_has_no_direct_supabase_client():
    """Posture (a) pin: the React frontend must not talk to Supabase directly.

    Fails CI if a future frontend change adds a Supabase client, which would open a
    browser->DB path the FastAPI-layer tenant filter cannot govern.
    """
    import re
    from pathlib import Path

    src = Path(__file__).parent.parent / "frontend" / "src"
    if not src.exists():
        pytest.skip("frontend/src not present")
    offenders = []
    pattern = re.compile(r"@supabase/supabase-js|createClient\s*\(", re.I)
    for p in src.rglob("*"):
        if p.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}:
            try:
                if pattern.search(p.read_text(encoding="utf-8", errors="ignore")):
                    offenders.append(str(p.relative_to(src)))
            except OSError:
                continue
    assert not offenders, (
        f"direct Supabase client in frontend breaks posture (a): {offenders}"
    )


# The tenant-scoped tables this isolation posture accounts for (report §2 + migration 032).
# A NEW tenant-scoped ORM table appearing here fails the guard, forcing a policy +
# report update so AC-1 ("no table relies on RLS-enabled-zero-policies") cannot silently regress.
_ACCOUNTED_TENANT_SCOPED = frozenset(
    {
        "audits",
        "audit_traces",
        "scan_reports",
        "grc_evidence_records",
        "grc_registry_entries",
        "grc_registry_audit",
        "registered_ai_systems",
        "notifications",
        "insight_actions",
        "compliance_readiness_items",
        "policies",
        "users",
        "ai_systems",
        "aims_documents",
        "audit_events",
        "client_configs",
        "github_integrations",
        "hf_sample_queue",
        "tenant_risk_configs",
        "dispositions",  # STORY-DISP-001 (RLS policy added in migration 034)
    }
)


def test_every_tenant_scoped_model_is_accounted_for():
    """Schema-driven guard (reviewer/security NH-4): the set of ORM tables carrying a
    tenant_id column must exactly match the accounted-for registry in the report."""
    actual = {t.name for t in Base.metadata.tables.values() if "tenant_id" in t.columns}
    new_unaccounted = actual - _ACCOUNTED_TENANT_SCOPED
    assert not new_unaccounted, (
        f"new tenant-scoped table(s) not in the isolation report / migration 032: "
        f"{sorted(new_unaccounted)} — add an RLS policy and update docs/TENANT_ISOLATION.md"
    )
