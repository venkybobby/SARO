"""
AI Insights backend — SARO_AIInsights_Stories (STORY-001..005 server side).

Covers:
  - GET  /api/v1/insights                      — derived, tenant-scoped insights
  - POST /api/v1/insights/{id}/action          — accept / snooze / dismiss + audit event

Insights are derived read-only from Audit + ScanReport + AuditTrace + RiskMetadata
(never calls external AI models — SARO non-negotiable #1). Only the user's
decision is persisted (InsightAction) plus an immutable AuditEvent row.

All tests use in-memory SQLite — no live DB required.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── SQLite setup (mirrors tests/test_risk_register_audit_fixes.py) ──────────
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON as PG_JSON  # noqa: E402
import sqlalchemy.types as sa_types  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]
PG_JSON.none_as_null = False

from database import Base, get_db  # noqa: E402
from models import (  # noqa: E402
    Audit,
    AuditEvent,
    AuditTrace,
    InsightAction,
    RiskMetadata,
    ScanReport,
    Tenant,
    User,
)

Base.metadata.create_all(engine)

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from auth import get_current_user  # noqa: E402

TENANT_ID = uuid.uuid4()
OTHER_TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _add_audit(
    db,
    tenant_id,
    *,
    dataset="Quarterly fairness scan",
    score=0.82,
    confidence=0.87,
    traces=(),
    dismissed=False,
):
    audit = Audit(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        dataset_name=dataset,
        sample_count=50,
        status="completed",
    )
    db.add(audit)
    db.flush()
    db.add(
        ScanReport(
            audit_id=audit.id,
            overall_risk_score=score,
            confidence_score=confidence,
            engine_version="8.0.0",
            report_json={},
        )
    )
    for i, t in enumerate(traces):
        db.add(
            AuditTrace(
                audit_id=audit.id,
                gate_id=t.get("gate_id", i + 1),
                gate_name=t.get("gate_name", "Fairness Gate"),
                check_type=t.get("check_type", "gate_result"),
                check_name=t.get("check_name", "statistical_parity"),
                result=t.get("result", "fail"),
                reason=t.get("reason", "Parity gap exceeds threshold"),
                remediation_hint=t.get("remediation_hint"),
                event_hash="0" * 64,
            )
        )
    if dismissed:
        db.add(RiskMetadata(audit_id=audit.id, dismissed=True))
    return audit


def _seed():
    db = TestingSessionLocal()
    db.add(Tenant(id=TENANT_ID, name="Acme", slug="acme"))
    db.add(Tenant(id=OTHER_TENANT_ID, name="Rival", slug="rival"))

    flagged = _add_audit(
        db,
        TENANT_ID,
        traces=[
            {
                "result": "fail",
                "remediation_hint": "Re-balance the training sample.",
                "reason": "Statistical parity gap 0.31 exceeds 0.20 threshold.",
            },
            {
                "check_type": "compliance_rule",
                "gate_name": "Compliance Mapping",
                "check_name": "NIST AI RMF MEASURE 2.11 fairness evidence",
                "result": "triggered",
                "reason": "Mapped to NIST AI RMF Measure 2.11.",
            },
        ],
    )
    no_confidence = _add_audit(
        db,
        TENANT_ID,
        dataset="No-confidence scan",
        confidence=None,
        traces=[{"result": "fail"}],
    )
    clean = _add_audit(db, TENANT_ID, dataset="Clean scan", score=0.05, traces=())
    dismissed_risk = _add_audit(
        db,
        TENANT_ID,
        dataset="Dismissed scan",
        traces=[{"result": "fail"}],
        dismissed=True,
    )
    foreign = _add_audit(
        db,
        OTHER_TENANT_ID,
        dataset="Foreign scan",
        traces=[{"result": "fail"}],
    )
    # Two same-tenant audits sharing an 8-hex-char id prefix — actions against
    # INS-DEADBEEF are ambiguous and must be refused (security audit F-3).
    # Low score + no traces so they never derive into listed insights.
    for tail in ("0000-4000-8000-000000000001", "1111-4000-8000-000000000002"):
        db.add(
            Audit(
                id=uuid.UUID(f"deadbeef-{tail}"),
                tenant_id=TENANT_ID,
                dataset_name="Prefix twin",
                sample_count=50,
                status="completed",
            )
        )
    db.commit()
    ids = {
        "flagged": str(flagged.id),
        "no_confidence": str(no_confidence.id),
        "clean": str(clean.id),
        "dismissed": str(dismissed_risk.id),
        "foreign": str(foreign.id),
    }
    db.close()
    return ids


AUDIT_IDS = _seed()
INSIGHT_ID = f"INS-{AUDIT_IDS['flagged'][:8].upper()}"
FOREIGN_INSIGHT_ID = f"INS-{AUDIT_IDS['foreign'][:8].upper()}"
RISK_ID = f"R-{AUDIT_IDS['flagged'][:6].upper()}"


def _override_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_user(persona="compliance_lead"):
    return User(
        id=USER_ID,
        tenant_id=TENANT_ID,
        email="user@acme.test",
        hashed_password="x",
        role="admin",
        persona_role=persona,
        is_active=True,
    )


def _override_user():
    return _make_user()


def _override_auditor():
    return _make_user(persona="ai_auditor")


client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}


@pytest.fixture(autouse=True)
def _reset_overrides():
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    # Order-independence: insight decisions made by one test never leak into
    # another (statuses derive from InsightAction rows).
    db = TestingSessionLocal()
    db.query(InsightAction).delete()
    db.commit()
    db.close()
    yield


# ── GET /api/v1/insights ────────────────────────────────────────────────────


class TestListInsights:
    def test_returns_derived_insights_with_required_fields(self):
        """STORY-001 AC-2: real {title, description, confidence, framework, remediation}."""
        r = client.get("/api/v1/insights", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == len(body["insights"]) >= 1
        ins = next(i for i in body["insights"] if i["id"] == INSIGHT_ID)
        assert ins["risk_id"] == RISK_ID
        assert ins["title"]
        assert ins["description"]
        assert ins["confidence"] == 0.87
        assert ins["severity"] == "critical"
        assert ins["status"] == "active"
        assert ins["remediation_guidance"] == "Re-balance the training sample."
        assert ins["framework"] == "NIST AI RMF"
        assert ins["basis"]

    def test_traceability_metadata_present(self):
        """STORY-001 NFR: model version, assessment date, audit trail field."""
        r = client.get("/api/v1/insights", headers=AUTH)
        ins = next(i for i in r.json()["insights"] if i["id"] == INSIGHT_ID)
        tr = ins["_traceability"]
        assert tr["engine_version"] == "8.0.0"
        assert tr["audit_id"] == AUDIT_IDS["flagged"]
        assert tr["assessment_date"]

    def test_insight_without_confidence_excluded(self):
        """STORY-001 NFR compliance: no insight without confidence score context."""
        r = client.get("/api/v1/insights", headers=AUTH)
        ids = [i["id"] for i in r.json()["insights"]]
        assert f"INS-{AUDIT_IDS['no_confidence'][:8].upper()}" not in ids

    def test_clean_low_risk_audit_produces_no_insight(self):
        r = client.get("/api/v1/insights", headers=AUTH)
        ids = [i["id"] for i in r.json()["insights"]]
        assert f"INS-{AUDIT_IDS['clean'][:8].upper()}" not in ids

    def test_dismissed_risk_excluded(self):
        r = client.get("/api/v1/insights", headers=AUTH)
        ids = [i["id"] for i in r.json()["insights"]]
        assert f"INS-{AUDIT_IDS['dismissed'][:8].upper()}" not in ids

    def test_tenant_scoping(self):
        """Cross-tenant insights must never leak."""
        r = client.get("/api/v1/insights", headers=AUTH)
        ids = [i["id"] for i in r.json()["insights"]]
        assert FOREIGN_INSIGHT_ID not in ids

    def test_risk_id_filter(self):
        """STORY-001 AC-1: fetch carries the current risk context."""
        r = client.get(f"/api/v1/insights?risk_id={RISK_ID}", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["insights"][0]["id"] == INSIGHT_ID

    def test_unknown_risk_filter_returns_empty_not_error(self):
        """STORY-001 edge: empty array → empty state, not mock data."""
        r = client.get("/api/v1/insights?risk_id=R-FFFFFF", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == {"insights": [], "count": 0}


# ── POST /api/v1/insights/{id}/action ───────────────────────────────────────


class TestInsightAction:
    def test_apply_records_audit_event(self):
        """STORY-002 AC-3: audit event {user, applied_suggestion, insightId, riskId, ts}."""
        r = client.post(
            f"/api/v1/insights/{INSIGHT_ID}/action",
            json={"action": "accepted", "confirm_human_review": True},
            headers=AUTH,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == INSIGHT_ID
        assert body["status"] == "accepted"
        assert body["risk_id"] == RISK_ID

        db = TestingSessionLocal()
        evt = (
            db.query(AuditEvent)
            .filter(AuditEvent.event_type == "insight_suggestion_applied")
            .order_by(AuditEvent.created_at.desc())
            .first()
        )
        assert evt is not None
        assert str(evt.tenant_id) == str(TENANT_ID)
        assert str(evt.user_id) == str(USER_ID)
        data = (
            evt.event_data
            if isinstance(evt.event_data, dict)
            else __import__("json").loads(evt.event_data)
        )
        assert data["action"] == "applied_suggestion"
        assert data["insight_id"] == INSIGHT_ID
        assert data["risk_id"] == RISK_ID
        assert data["human_review_acknowledged"] is True
        assert evt.created_at is not None
        db.close()

    def test_apply_without_human_review_ack_rejected(self):
        """STORY-004 AC-3: applying requires explicit human-review confirmation."""
        r = client.post(
            f"/api/v1/insights/{INSIGHT_ID}/action",
            json={"action": "accepted"},
            headers=AUTH,
        )
        assert r.status_code == 422

    def test_status_persists_into_listing(self):
        """STORY-002 AC-4: insight status updates to accepted after apply."""
        client.post(
            f"/api/v1/insights/{INSIGHT_ID}/action",
            json={"action": "accepted", "confirm_human_review": True},
            headers=AUTH,
        )
        r = client.get("/api/v1/insights", headers=AUTH)
        ins = next(i for i in r.json()["insights"] if i["id"] == INSIGHT_ID)
        assert ins["status"] == "accepted"

    def test_repeat_action_last_write_wins(self):
        """STORY-002 edge: parallel/repeated applies handled gracefully."""
        for action in ("accepted", "snoozed"):
            payload = {"action": action}
            if action == "accepted":
                payload["confirm_human_review"] = True
            r = client.post(
                f"/api/v1/insights/{INSIGHT_ID}/action", json=payload, headers=AUTH
            )
            assert r.status_code == 200
        r = client.get("/api/v1/insights", headers=AUTH)
        ins = next(i for i in r.json()["insights"] if i["id"] == INSIGHT_ID)
        assert ins["status"] == "snoozed"

    def test_unknown_insight_404(self):
        """STORY-002 edge: risk deleted before action → error, no orphan."""
        r = client.post(
            "/api/v1/insights/INS-FFFFFFFF/action",
            json={"action": "dismissed"},
            headers=AUTH,
        )
        assert r.status_code == 404

    def test_cross_tenant_insight_404(self):
        r = client.post(
            f"/api/v1/insights/{FOREIGN_INSIGHT_ID}/action",
            json={"action": "dismissed"},
            headers=AUTH,
        )
        assert r.status_code == 404

    def test_invalid_action_422(self):
        r = client.post(
            f"/api/v1/insights/{INSIGHT_ID}/action",
            json={"action": "exploded"},
            headers=AUTH,
        )
        assert r.status_code == 422

    def test_like_wildcard_in_insight_id_rejected(self):
        """Security F-1: %/_ wildcards must never match an arbitrary audit."""
        for malicious in ("INS-%", "INS-_", "INS-%25", "INS-a%"):
            r = client.post(
                f"/api/v1/insights/{malicious}/action",
                json={"action": "dismissed"},
                headers=AUTH,
            )
            assert r.status_code == 404, malicious

    def test_like_wildcard_in_risk_filter_returns_empty(self):
        """Security F-1: wildcard risk_id filters match nothing."""
        r = client.get("/api/v1/insights?risk_id=R-%25", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == {"insights": [], "count": 0}

    def test_zero_or_negative_limit_rejected(self):
        """Security F-2: limit must not disable the scan bound."""
        for bad in (0, -1):
            r = client.get(f"/api/v1/insights?limit={bad}", headers=AUTH)
            assert r.status_code == 422, bad

    def test_ambiguous_prefix_conflict(self):
        """Security F-3: two audits sharing a prefix → 409, never wrong-row write."""
        r = client.post(
            "/api/v1/insights/INS-DEADBEEF/action",
            json={"action": "dismissed"},
            headers=AUTH,
        )
        assert r.status_code == 409

    def test_audit_event_records_previous_and_new_status(self):
        """STORY-002 NFR: audit trail carries risk state pre/post."""
        client.post(
            f"/api/v1/insights/{INSIGHT_ID}/action",
            json={"action": "accepted", "confirm_human_review": True},
            headers=AUTH,
        )
        client.post(
            f"/api/v1/insights/{INSIGHT_ID}/action",
            json={"action": "snoozed"},
            headers=AUTH,
        )
        db = TestingSessionLocal()
        evt = (
            db.query(AuditEvent)
            .filter(AuditEvent.event_type == "insight_snoozed")
            .order_by(AuditEvent.created_at.desc())
            .first()
        )
        data = (
            evt.event_data
            if isinstance(evt.event_data, dict)
            else __import__("json").loads(evt.event_data)
        )
        assert data["previous_status"] == "accepted"
        assert data["new_status"] == "snoozed"
        db.close()

    def test_read_only_persona_403(self):
        """STORY-002/004 edge: auditor view may look but not apply."""
        app.dependency_overrides[get_current_user] = _override_auditor
        r = client.post(
            f"/api/v1/insights/{INSIGHT_ID}/action",
            json={"action": "accepted", "confirm_human_review": True},
            headers=AUTH,
        )
        assert r.status_code == 403
        assert "read-only" in r.json()["detail"].lower()

    def test_auditor_can_still_list(self):
        app.dependency_overrides[get_current_user] = _override_auditor
        r = client.get("/api/v1/insights", headers=AUTH)
        assert r.status_code == 200


# ── Compliance posture ──────────────────────────────────────────────────────


class TestCompliancePosture:
    def test_router_has_no_forbidden_compliance_claims(self):
        """COMPLIANCE_CLAIMS_MATRIX: no compliant/passed claims in API surface."""
        content = (ROOT / "routers" / "insights.py").read_text(encoding="utf-8")
        for forbidden in (
            "nist_compliant",
            "compliance_score",
            "audit_passed",
            "compliance_fix",
        ):
            assert forbidden not in content

    def test_insights_response_carries_human_review_field(self):
        """STORY-004: API framing — guidance is advisory, human validation required."""
        r = client.get("/api/v1/insights", headers=AUTH)
        ins = next(i for i in r.json()["insights"] if i["id"] == INSIGHT_ID)
        assert ins["human_review_required"] is True
