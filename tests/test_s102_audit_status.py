"""
S-102: GET /api/v1/ingest/{audit_id} — audit status polling tests.

Tests that:
  1. The route exists in the ingest router.
     (Renamed from /audits/{audit_id} to /ingest/{audit_id} to resolve the
     route collision with routers/scan.py's GET /api/v1/audits/{audit_id}.)
  2. AuditStatusResponse has the expected fields.
  3. Background audit task helper has the correct signature.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestAuditStatusRoute:
    def test_route_exists(self):
        from routers.ingest import router
        route_paths = [r.path for r in router.routes]
        assert any("ingest" in p and "audit_id" in p for p in route_paths), \
            f"No ingest/{{audit_id}} route in {route_paths}"

    def test_route_is_get(self):
        from routers.ingest import router
        for r in router.routes:
            if "ingest" in r.path and "audit_id" in r.path:
                assert "GET" in r.methods
                break

    def test_background_helper_importable(self):
        from routers.ingest import _run_audit_background
        import inspect
        sig = inspect.signature(_run_audit_background)
        params = list(sig.parameters.keys())
        assert "audit_id" in params
        assert "prompt" in params
        assert "raw_output" in params
        assert "source_model" in params


class TestAuditStatusResponseShape:
    def test_running_status_nulls(self):
        """A 'running' audit should have null risk metrics."""
        from routers.ingest import AuditStatusResponse
        now = datetime.now(tz=timezone.utc)
        resp = AuditStatusResponse(
            audit_id=uuid.uuid4(),
            status="running",
            trace_url="http://localhost/trace",
            created_at=now,
        )
        assert resp.status == "running"
        assert resp.risk_score is None
        assert resp.mit_coverage_pct is None
        assert resp.confidence_score is None
        assert resp.exceptions_count is None
        assert resp.completed_at is None

    def test_completed_status_with_metrics(self):
        """A 'completed' audit can carry all metric fields."""
        from routers.ingest import AuditStatusResponse
        now = datetime.now(tz=timezone.utc)
        resp = AuditStatusResponse(
            audit_id=uuid.uuid4(),
            status="completed",
            risk_score=73.5,
            mit_coverage_pct=62.3,
            confidence_score=0.91,
            exceptions_count=3,
            trace_url="http://localhost/trace",
            created_at=now,
            completed_at=now,
        )
        assert resp.risk_score == 73.5
        assert resp.mit_coverage_pct == 62.3
        assert resp.confidence_score == 0.91
        assert resp.exceptions_count == 3
        assert resp.completed_at is not None

    def test_failed_status(self):
        from routers.ingest import AuditStatusResponse
        now = datetime.now(tz=timezone.utc)
        resp = AuditStatusResponse(
            audit_id=uuid.uuid4(),
            status="failed",
            trace_url="http://localhost/trace",
            created_at=now,
        )
        assert resp.status == "failed"

    def test_trace_url_is_required(self):
        """trace_url is a required string field in the response."""
        from routers.ingest import AuditStatusResponse
        field = AuditStatusResponse.model_fields["trace_url"]
        assert field.is_required()

    def test_audit_id_in_trace_url(self):
        from routers.ingest import AuditStatusResponse
        now = datetime.now(tz=timezone.utc)
        audit_id = uuid.uuid4()
        resp = AuditStatusResponse(
            audit_id=audit_id,
            status="running",
            trace_url=f"http://localhost/api/v1/audit/{audit_id}/trace",
            created_at=now,
        )
        assert str(audit_id) in resp.trace_url
