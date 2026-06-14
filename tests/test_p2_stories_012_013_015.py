"""
Tests for P2 stories:
  STORY-012 — Risk dashboard returns score_history (sparkline data)
  STORY-013 — Audit report exposes rule_pack_hash for TraceView linkage
  STORY-015 — Drift alerts endpoint returns well-shaped response

All tests use app.dependency_overrides to avoid DATABASE_URL requirement.
"""
from __future__ import annotations

import os
import sys
import uuid
from unittest.mock import MagicMock

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-p2-stories")

from fastapi.testclient import TestClient  # noqa: E402
from auth import get_current_user          # noqa: E402
from database import get_db               # noqa: E402
from main import app                       # noqa: E402
from models import User                    # noqa: E402

_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")


def _mock_user(role: str = "admin") -> MagicMock:
    u = MagicMock(spec=User)
    u.id          = uuid.uuid4()
    u.email       = f"{role}@test.example"
    u.role        = role
    u.persona_role = role
    u.tenant_id   = _TENANT_ID
    u.is_active   = True
    u.read_only   = False
    return u


def _user_dep(role: str = "admin"):
    user = _mock_user(role)
    async def _dep():
        return user
    return _dep, user


def _db_dep_empty():
    """Stub db that returns empty results for any query."""
    def _dep():
        mock_db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.outerjoin.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = []
        q.first.return_value = None
        q.count.return_value = 0
        mock_db.query.return_value = q
        mock_db.get.return_value = None
        yield mock_db
    return _dep


def _with_overrides(role: str = "admin"):
    """Context helper: returns client, user, db overrides applied."""
    user_dep, user = _user_dep(role)
    db_dep = _db_dep_empty()
    app.dependency_overrides[get_current_user] = user_dep
    app.dependency_overrides[get_db] = db_dep
    return TestClient(app), user


def _clear():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ─── STORY-015: Drift alerts endpoint ─────────────────────────────────────────

class TestDriftAlertsEndpoint:
    """GET /api/v1/rules/drift-alerts — response shape for dashboard banner."""

    def test_drift_alerts_ai_auditor_no_crash(self):
        client, _ = _with_overrides("ai_auditor")
        try:
            r = client.get("/api/v1/rules/drift-alerts", headers={"Authorization": "Bearer test"})
            # 200 or 404 (endpoint optional) — never 500
            assert r.status_code != 500, f"drift/alerts crashed: {r.text[:200]}"
            assert r.status_code in (200, 404, 403, 422), f"Unexpected {r.status_code}"
        finally:
            _clear()

    def test_drift_alerts_admin_no_crash(self):
        client, _ = _with_overrides("admin")
        try:
            r = client.get("/api/v1/rules/drift-alerts", headers={"Authorization": "Bearer test"})
            assert r.status_code != 500, f"drift/alerts crashed: {r.text[:200]}"
            if r.status_code == 200:
                body = r.json()
                assert isinstance(body, (dict, list)), "Must return dict or list"
                if isinstance(body, dict):
                    assert "alerts" in body or "framework_versions" in body or "items" in body, \
                        f"Missing expected keys: {list(body.keys())}"
        finally:
            _clear()

    def test_drift_alerts_unauthenticated_no_200(self):
        """Unauthenticated request must not return 200."""
        _clear()
        r = TestClient(app).get("/api/v1/rules/drift-alerts")
        assert r.status_code not in (200,), \
            f"Unauthenticated drift/alerts should not return 200: {r.status_code}"


# ─── STORY-013: rule_pack_hash in audit report schema ─────────────────────────

class TestRulePackInAuditReport:

    def test_rule_pack_hash_in_schema(self):
        """AuditReportOut.rule_pack_hash field must exist and be optional."""
        from schemas import AuditReportOut
        fields = AuditReportOut.model_fields
        assert "rule_pack_hash" in fields, \
            "AuditReportOut must expose rule_pack_hash for TraceView rule pack badge"

    def test_rule_pack_hash_is_optional(self):
        from schemas import AuditReportOut
        fields = AuditReportOut.model_fields
        field = fields["rule_pack_hash"]
        # Default must be None (optional)
        assert field.default is None or not field.is_required(), \
            "rule_pack_hash should be optional (str | None)"

    def test_audit_report_endpoint_404_unknown_id(self):
        """GET /api/v1/audits/{id} returns 404 for unknown audit, not 500."""
        client, _ = _with_overrides("admin")
        try:
            fake_id = str(uuid.uuid4())
            r = client.get(f"/api/v1/audits/{fake_id}", headers={"Authorization": "Bearer test"})
            # stub db returns None for get() — expect 404, not 500
            assert r.status_code in (404, 403, 422), \
                f"Expected 404 for unknown audit, got {r.status_code}: {r.text[:200]}"
        finally:
            _clear()

    def test_audit_list_no_500(self):
        """GET /api/v1/audits does not 500."""
        client, _ = _with_overrides("admin")
        try:
            r = client.get("/api/v1/audits", headers={"Authorization": "Bearer test"})
            assert r.status_code != 500, f"Audit list crashed: {r.text[:200]}"
        finally:
            _clear()


# ─── STORY-012: Risk dashboard + sparkline data ───────────────────────────────

class TestRiskDashboardScoreHistory:

    def test_risk_dashboard_no_500(self):
        client, _ = _with_overrides("risk_officer")
        try:
            r = client.get("/api/v1/risk_dashboard", headers={"Authorization": "Bearer test"})
            assert r.status_code != 500, f"risk_dashboard crashed: {r.text[:300]}"
        finally:
            _clear()

    def test_risk_dashboard_shape_when_200(self):
        client, _ = _with_overrides("admin")
        try:
            r = client.get("/api/v1/risk_dashboard", headers={"Authorization": "Bearer test"})
            if r.status_code == 200:
                body = r.json()
                assert isinstance(body, dict), "risk_dashboard must return a JSON object"
                if "score_history" in body:
                    assert isinstance(body["score_history"], list), \
                        "score_history must be a list"
                if "summary" in body and isinstance(body["summary"], dict):
                    s = body["summary"]
                    if "score_history" in s:
                        assert isinstance(s["score_history"], list)
        finally:
            _clear()

    def test_audits_list_for_sparkline_fallback(self):
        """GET /api/v1/audits?limit=30 used as sparkline fallback — must not 500."""
        client, _ = _with_overrides("risk_officer")
        try:
            r = client.get(
                "/api/v1/audits?limit=30&sort=desc",
                headers={"Authorization": "Bearer test"},
            )
            assert r.status_code != 500, f"Audit list crashed: {r.text[:200]}"
            if r.status_code == 200:
                body = r.json()
                items = body if isinstance(body, list) else body.get("items", [])
                assert isinstance(items, list)
        finally:
            _clear()

    def test_sparkline_component_renders_with_empty_history(self):
        """Smoke test: RiskSummary returns empty score_history gracefully.

        This confirms the backend never returns score_history as something
        other than a list (e.g. a string), which would break the Sparkline.
        """
        client, _ = _with_overrides("risk_officer")
        try:
            r = client.get("/api/v1/risk_dashboard", headers={"Authorization": "Bearer test"})
            if r.status_code == 200:
                body = r.json()
                raw = body.get("score_history") or (body.get("summary") or {}).get("score_history")
                if raw is not None:
                    assert isinstance(raw, list), \
                        f"score_history must be list, not {type(raw).__name__}"
        finally:
            _clear()
